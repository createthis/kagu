#!/usr/bin/env python

import os, gobject, pango, pygtk, gtk, random, urllib, thread
from manager import manager as manager
import globals

PLAYLIST = os.path.expanduser("~/.kagu/playlist.m3u")


#
#  Provides a playlist store to queue player jobs.
#
class Playlist:
  
  list, unshuffled_list, current, history = [], [], None, []
  continuous, random, repeat, repeat_one = True, False, False, False
  loadcount, loadcur = 0, 0
  autoplay = True
  lock = None
  
  #
  #  Creates the playlist widgets and adds them to vbox.
  #
  def __init__(self):
    self.continuous = manager.prefs.getBool("continuous")
    self.random = manager.prefs.getBool("random")
    self.autoplay = manager.prefs.getBool("autoplay")
    self.repeat = manager.prefs.getBool("repeat")
    self.repeat_one = manager.prefs.getBool("repeat_one")
    self.lock = thread.allocate_lock()

    from m3u     import m3u     as m3u
    from db      import db      as db
    path_list = m3u.load(filename=PLAYLIST)
    if not path_list: return
    song_list = db.songs_of_paths(path_list) # get rid of the paths that don't exist in the DB
    for song in song_list:
      self.add(song['path'],autoplay=False)

    #Save unshuffled list
    self.unshuffled_list = self.list[:]
    
    #Randomize playlist for shuffle mode
    if self.random:
        self.lock.acquire()
        self.shuffle()
        self.lock.release()

    
  #
  #  Update
  #
  def update(self):
    # update nowplaying indicator
    if manager.nowplaying_view: manager.nowplaying_view.update_selection()
    if manager.play_button: manager.play_button.update()
    return True

  #
  #  Plays the specified target from the playlist.
  #
  def play(self, index, log=True, event=None):
    if log and not self.is_empty():  #append current target to history
      self.history.append(self.current)
    
    #if event:  #clear selection, select target, show info
   
    print "index=%s" % (index,)
    if self.is_empty() or (index >= len(self.list)): return True
    self.current = index
    self.update()
    if manager.scrobbler: manager.scrobbler.play()
    if manager.dbusapi:   manager.dbusapi.update_play()
    if manager.player:    manager.player.play(self.status())  #begin playing target
    return True

  def pause(self):
    print "current=%s,empty=%s" % (self.current,self.is_empty())
    if self.current == None and not self.is_empty():
      print "playing %s" % (self.list[0],)
      self.play(0)
    else: manager.player.pause()


  def is_paused(self):
    return manager.player.paused
    
  #
  #  Plays a target step rows from the currently active target.
  #
  def jump(self, step, log=True, event=None):
    print "jump: len='%d',current='%s',random='%s'" % (len(self.list),self.current,self.random)
    
    if not self.list:  #empty list
      return True
    
    # Using playlist shuffling instead
    #if self.random:  #disregard step, use random
    #  i = random.randint(0, len(self.list) - 1)
    #elif not self.is_empty():
    if not self.is_empty():
      i = self.current + step
    else:
      i = step
   
    print "jump: step='%s'" % (step,)

    if i > len(self.list) - 1: i = 0
    if i < 0: i = len(self.list) + i
   
    print "step=%d,i=%d,len=%d,current=%d" % (step,i,len(self.list),self.current)
    return self.play(i, log, event)
    
  #
  #  Stops the current player job and prevents a jump.
  #
  def stop(self, widget=None, event=None):
    if manager.scrobbler: manager.scrobbler.stop()
    if manager.dbusapi:   manager.dbusapi.stopped()
    manager.player.close()
    return True
    
  #
  #  Returns True if the playlist has been exhausted, False otherwise.
  #
  def exhausted(self):
    if self.repeat:  #never exhausted
      return False
   
    if self.current >= len(self.list) - 1:
      return True
    return False
  
  #
  #  Plays a previously played target if available, jumps otherwise.
  #
  def prev(self, widget, event):
    index = None
    while index == None and len(self.history):
      index = self.history.pop()
    
    if index != None:  #play target from history
      return self.play(index, False, event)
    
    if self.current == None and not self.is_empty():
      print "prev: playing %s" % (self.list[0],)
      self.play(0)
    else: return self.jump(-1, False, event)
    
  #
  #  Plays the next available target.
  #
  def next(self, widget, event, force=False):
    if not event and self.exhausted():  #exhausted list, return
      return self.stop()
    elif self.repeat_one and not force:
      return self.jump(0, True, event)
    if self.current == None and not self.is_empty():
      print "next: playing %s" % (self.list[0],)
      self.play(0)
    else: return self.jump(1, True, event)
    
  #
  #  Returns the title of the current target, or None.
  #
  def status(self):
    current_title = None

    self.lock.acquire()
    if not (self.is_empty() or self.current==None):
      try:
        current_title = self.list[self.current]
      except:
        self.current = None # prevent crash elsewhere
    self.lock.release()

    return current_title
  
  #
  #  Saves playlist to the specified file, defaulting to PLAYLIST.
  #
  def save(self, filename=PLAYLIST):
    from m3u     import m3u     as m3u

    self.lock.acquire()
    m3u.save(self.list,filename=filename)
    self.lock.release()

    return True
  
  #
  #  Loads the specified targets (lazily) to the playlist.
  #
  def load(self, targets):
    self.lock.acquire()
    self.loadcount += len(targets)

    isem = self.is_empty()

    #load to unshuffled list first, then reshuffle list
    self.list = self.unshuffled_list[:]
    
    for t in targets:
      target = urllib.unquote(t).replace("file://", "")
      
    self.lock.release()
    self.add(target, False)
    self.lock.acquire()

    self.unshuffled_list = self.list[:]

    # Shuffle the new playlist
    if self.random:
        self.shuffle()
    self.lock.release()

    self.update()
    if manager.nowplaying_view: manager.nowplaying_view.dirty = True

    if isem and self.autoplay:
        self.play(0)
    return True
  
  #
  #  Adds the specified target to the playlist.
  #
  def add(self, target, autoplay=None):
    self.lock.acquire()
    self.loadcur += 1
    
    if target.find("://") > -1:  #locations, http://, dvd://
      name = target
    else:  #normal files
      name = target

    isem = self.is_empty()
    
    self.list.append(name)
    self.unshuffled_list.append(name)
    self.lock.release()

    if manager.nowplaying_view: manager.nowplaying_view.dirty = True

    effective_autoplay = self.autoplay
    # override class autoplay setting
    if autoplay != None: effective_autoplay = autoplay

    if isem and effective_autoplay: self.play(0)

    return False  #cancel idle callback
    
  #
  #  Stops playback and removes all targets from playlist.
  #
  def clear(self):
    self.lock.acquire()
    if self.current!=None:  #stop if necessary
      self.stop(None, None)
      self.current = None
      self.history = []

    self.list = []
    self.unshuffled_list = []
    manager.nowplaying_view.dirty = True
    self.lock.release()

    return True

  #
  #  Is the playlist empty?
  #
  def is_empty(self):
    return not self.list

  #
  #  Swap two items
  #
  def swap_items(self, item1, item2):
    self.lock.acquire()
    tmp = self.list[item1]
    self.list[item1] = self.list[item2]
    self.list[item2] = tmp
    if self.current == item1:
      self.current = item2
    elif self.current == item2:
      self.current = item1
    self.lock.release()

  #
  #  Remove item
  #
  def remove_item(self, item):
    if self.current==item:
      if item == len(self.list) - 1:
        self.prev(None,None)
      else:
        self.next(None,None)
        self.current-=1
    elif self.current > item:
      self.current-=1
    self.lock.acquire()
    self.history = []
    del self.list[item]
    self.lock.release()
    if self.is_empty(): self.stop()


  #
  #  Save as
  #
  def save_as_dlg(self):
    from db      import db      as db
    dialog = gtk.Dialog("Save Playlist As", None, gtk.DIALOG_MODAL, (gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT, gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT))
    dialog.set_default_response(gtk.RESPONSE_ACCEPT)

    label = gtk.Label("Enter a name for the playlist:")
    dialog.vbox.pack_start(label, False, True, 15)

    basepath = os.path.expanduser("~/MyDocs/.sounds")
    if not os.path.exists(basepath):
      basepath = os.path.expanduser("~")

    base="Playlist"
    extra=""

    while os.path.exists(basepath+"/"+base+str(extra)+".m3u"):
      if extra=="":
        extra=1
      else:
        extra=extra+1

    e = gtk.combo_box_entry_new_text()
    map(lambda row: e.append_text(row['name']), db.get_m3us())
    e.prepend_text(base+str(extra))
    e.set_active(0)
    
    dialog.vbox.pack_start(e, False, True, 0)

    label = gtk.Label(" ")
    dialog.vbox.pack_start(label, False, True, 0)

    dialog.vbox.show_all()
    while True:
      resp = dialog.run()
      if resp == gtk.RESPONSE_ACCEPT:
        plname = e.get_active_text()
        plname_clean = plname.replace("/", "").replace("`", "").replace("\\", "").replace("~", "").replace("?", "").strip()
        if plname == plname_clean and plname!="":
          break
        label.set_text("Please enter a valid name")
        e.set_text(plname_clean)
      else:
        dialog.destroy()
        return

    filename = basepath+"/"+plname+".m3u"
    print "playlist name = ",filename

    from m3u     import m3u     as m3u
    from m3u     import FN      as FN
    self.lock.acquire()
    if m3u.save(self.list, filename=filename):
      exis = db.m3u_exists(filename)
      if filename!=FN and not db.m3u_exists(filename):
        (rootfn,ext) = os.path.splitext(filename)
        name = os.path.basename(rootfn)
        db.insert_m3u(name,filename)
        print "here3",name,"/",filename
      globals.infobanner("Saved")
    else:
      globals.infobanner("Error saving")
    self.lock.release()

    dialog.destroy()

  def delete_playlist(self, filename):
    from db      import db      as db
    try:
      os.unlink(filename)
      db.remove_m3u(filename)
    except:
      globals.infobanner("Error deleting")

  #
  #  Shuffle playlist
  #
  def shuffle(self):
    print 'Shuffling list'
    random.shuffle(self.list)

  def get_autoplay(self):
    return self.autoplay

  def set_autoplay(self, value):
    self.autoplay = value

  #
  # Accessor for random flag
  #
  def get_random(self):
    return self.random

  #
  # Setter for random flag
  #
  def set_random(self, value):
    if self.random != value:
      self.lock.acquire()
      #Shuffled state is changing
      if value: # Unshuffled => Shuffled
        self.unshuffled_list = self.list[:]  # Back up unshuffled list
        self.shuffle()
      else: # Shuffled => Unshuffled
        self.list = self.unshuffled_list[:]    # Restore unshuffled list
      self.lock.release()

      # Reload playlist and jump to first item
      self.update()
      manager.nowplaying_view.dirty = True
      if self.autoplay: self.play(0)
        
    self.random = value
