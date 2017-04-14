#!/usr/bin/env python
#
#
#   Copyright (c) 2007 Jesse Guardiani <jesse@guardiani.us>
#
#   This program is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License as
#   published by the Free Software Foundation; either version 2 of the
#   License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful, but
#   WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
#   General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
#   02111-1307, USA.
#

import math, os, pygame, gc, time, sys
from pygame.locals import *
import gtk
import globals
from db      import db      as db
from theme   import theme   as theme


def which (filename):
  if not os.environ.has_key('PATH') or os.environ['PATH'] == '':
      p = os.defpath
  else:
      p = os.environ['PATH']
  pathlist = p.split (os.pathsep)
  for path in pathlist:
      f = os.path.join(path, filename)
      if os.access(f, os.X_OK):
          return f
  return None

class Manager():
  def __init__(self):
    ''' This is the brain of the application. It handles keeping track of all the widgets,
    knowing when to draw and when not to draw a given widget, feeding the widgets with event
    data, and much more. '''
    self.screen     = None
    self.background = None
    self.db         = None
    self.view       = None
    self.dirty      = False
    self.scrobbler  = None
    self.player     = None
    self.has_mplayer     = which('mplayer')
    self.has_a2dp        = which('a2dpd') and self.has_mplayer
    self.nowplaying_view = None
    self.volume_view     = None
    self.songposition_view = None
    self.cover_view  = None
    self.play_button     = None
    self.screen_status   = "on" # is our display screen on, off, or dimmed?
    self.screen_manually_blanked  = False # have we manually blanked the screen? This is a forced state and tracked seperately.
    self.on_battery      = False # are we running on battery power or plugged in?
    self.has_focus       = True  # does our window have focus?
    self.idle_start      = 0
    self.idle_seconds    = 0
    self.first_time      = True
    self.enqueue_mode    = True # False = old (weird) functionality
    self.view_history    = []
    self.sleep_timer     = 0    # >0 = sleep timer enabled, time of last activity
    self.sleep_timer_dur = 3600 # sleep timer duration (seconds)
    self.ignore_keypad_till = 0
    self.default_player  = None
    self.scrollbar_state = False
    self.nowplayingbuttonimage = ""
    self.headphone_sense = True
    self.sort_albums_by_year = True
    self.delayed_info_message = ""
    self.delayed_info_type    = ""
    self.dbusapi = None

  def __load_scrobbler(self):
    if globals.ISMAEMO:
      import maemoscrobbler
      self.scrobbler = maemoscrobbler.MaemoScrobbler()

  def __load_maemo(self):
    if globals.ISMAEMO:
      import widgets
      self.clear()
      status_area = widgets.Text("CONNECTING TO DBUS")
      status_area.rect.topleft = (130,200)
      status_area.update()
      status_area.draw(self.screen)
      pygame.display.flip()
      import maemo

  def __load_dbusapi(self):
    import dbusapi
    api = dbusapi.DBusApi()
    if api.init_ok:
      self.dbusapi = api

  def _get_player(self, player_name=None):
    import widgets
    self.clear()
    if player_name==None:
      player_name=self.default_player
    if player_name=="ossoplayer":
      status_area = widgets.Text("INITIALIZING OSSO PLAYER")
      status_area.rect.topleft = (130,200)
      status_area.update()
      status_area.draw(self.screen)
      pygame.display.flip()
      import ossoplayer
      self.player = ossoplayer.OSSOPlayer(self.first_time)
    elif player_name=="gstplayer":
      status_area = widgets.Text("INITIALIZING GSTREAMER")
      status_area.rect.topleft = (130,200)
      status_area.update()
      status_area.draw(self.screen)
      pygame.display.flip()
      try:
        import gstplayer
        self.player = gstplayer.GSTPlayer()
      except: #fallback to mplayer
        player_name = "mplayer"
        self.default_player = "mplayer"

    if player_name!="ossoplayer" and player_name!="gstplayer":
      status_area = widgets.Text("INITIALIZING MPLAYER")
      status_area.rect.topleft = (130,200)
      status_area.update()
      status_area.draw(self.screen)
      pygame.display.flip()
      import mplayer
      self.player = mplayer.Mplayer()

    self.first_time=False

  def _load_cache_images(self):
    import widgets
    status_area = widgets.Text("LOADING COVER ART")
    status_area.rect.topleft = (130,200)
    status_area.update()
    status_area.draw(self.screen)
    pygame.display.flip()

#    globals.timer_init()
    globals.albumcache  = pygame.image.load(os.path.join(db.get_db_dir(),"album_cache.tga"))
#    globals.timer_check("albcacload")
#    globals.albumcache = globals.albumcache.convert()
#    globals.timer_check("albcacload-convert")
    globals.artistcache = pygame.image.load(os.path.join(db.get_db_dir(),"artist_cache.tga"))
#    globals.timer_check("artcacload")
#    globals.artistcache = globals.artistcache.convert()
#    globals.timer_check("artcacload-convert")


  #
  # Public Methods
  #

  def set_display_mode(self,fullscreen = True):
    SCREENRECT = Rect(0, 0, 800, 480)
    # set the display mode
    if fullscreen:
      winstyle = FULLSCREEN
      if not globals.ISMAEMO: winstyle = 1
    else: winstyle = 1

    if not globals.ISMAEMO:
      bestdepth = pygame.display.mode_ok(SCREENRECT.size, winstyle, 32)
    else:
      bestdepth = pygame.display.mode_ok(SCREENRECT.size, winstyle, 16)

    screen = pygame.display.set_mode(SCREENRECT.size, winstyle, bestdepth)
    if globals.ISMAEMO: pygame.mouse.set_visible(False)
    self.screen = screen

  def is_fullscreen(self):
    if self.screen.get_flags() & FULLSCREEN == FULLSCREEN:
      return True
    return False

  def init_pygame(self):
    os.environ["SDL_VIDEO_X11_WMCLASS"]="kagu"

    pygame.init()
    pygame.display.set_caption('kagu')
    pygame.mixer.quit() # we don't want pygame hogging the audio device
    self.set_display_mode()

  def start(self):
    import views,widgets,prefs,remote,playlist
    self.prefs    = prefs.Prefs()
    self.remote   = remote.Remote()
    self.playlist = playlist.Playlist()
    self.init_pygame()
    
    theme.set_theme(self.prefs.get('theme'))
    st = manager.prefs.get("sleep_timer")
    if st == "True":
      st = 3600
    else:
      try:
        st = int(st)
      except:
        st = 0
    if st>0:
      self.sleep_timer = 1
    self.sleep_timer_dur = st

    self.default_player = manager.prefs.get("player")
    if not self.has_mplayer and self.default_player=="mplayer":
      self.default_player = "ossoplayer"
    if not globals.ISMAEMO and self.default_player=="ossoplayer":
      self.default_player = "mplayer" # FIXME: we don't check for self.has_mplayer here

    self.scrollbar_state = manager.prefs.getBool("scrollbars")
    self.nowplayingbuttonimage = manager.prefs.get("now_playing_button_image")
    if self.nowplayingbuttonimage!="artist" and self.nowplayingbuttonimage!="album":
      self.nowplayingbuttonimage="album"
    self.headphone_sense = manager.prefs.getBool("headphone_sense")
    self.sort_albums_by_year = manager.prefs.getBool("sort_albums_by_year")

    globals.MAINFONTCOLOR   = theme.surface.get_at((93,512))
    globals.MAINFONTBGCOLOR = theme.surface.get_at((40,582))
    
    self.background = theme.get_image('background')

    self.screen.blit(self.background,(0,0))
    pygame.display.flip()
    self._load_cache_images()
    self.__load_dbusapi()
    self._get_player()
    
    self.__load_scrobbler()
    self.__load_maemo()
    self.nowplaying_button = widgets.NowPlayingButton()
    self.play_button       = widgets.PlayButton()
    self.a2dp_button       = widgets.A2DPButton()
    self.next_button       = widgets.NextButton()
    self.prev_button       = widgets.PrevButton()
    self.repeat_button     = widgets.RepeatButton()
    self.nowplaying_view   = views.NowPlayingView()
    self.volume_view       = views.VolumeView()
    self.show_menu()
    if self.dbusapi: self.dbusapi.state_changed("ready")

  def handle_event(self,event):
    if self.view.handle_event(event):
      return

    # global events
    self.nowplaying_button.handle_event(event)
    self.a2dp_button.handle_event(event)
    self.play_button.handle_event(event)
    self.next_button.handle_event(event)
    self.prev_button.handle_event(event)
    self.repeat_button.handle_event(event)
    if event.type == KEYDOWN and (event.mod&128)==0:
      if time.time()<=self.ignore_keypad_till:
        return
      if event.key == K_F7:    self.player.volume_increase()
      if event.key == K_F8:    self.player.volume_decrease()
      if event.key == K_LEFT:  self.prev_track()
      if event.key == K_RIGHT: self.next_track()
      if event.key == K_ESCAPE:self.back()
      if event.key == K_F4:    self.show_menu()

      # pause on fullscreen or headset button - headset button won't work yet (SDL's fault)
      # "X11: Unknown xsym, sym = 0x1008ff6e"
      if (event.key == K_F6 and (event.mod&128)==0) or (event.key == 0x1008ff6e): self.playlist.pause()
    if event.type == ACTIVEEVENT:
      self.has_focus = event.gain


  def view_history_pop(self):
    if not self.view_history:
      print "2 view_history=%s,view=%s" % (self.view_history,self.view)
      return None

    old_view = self.view
    new_view = self.view_history.pop()
    if old_view and old_view.is_temporary and not old_view in self.view_history: old_view.close()
    gc.collect(1)
    #print "here comes the garbage:\n\n"
    #print gc.garbage
    print "3 view_history=%s,view=%s" % (self.view_history,self.view)
    return new_view


  def back_by_one(self):
    new_view = self.view_history_pop()
    if not new_view: self.show_exit_confirm()
    else: self.view = new_view
    pygame.event.clear()


  def back(self,index=None):
    if index == None or index > len(self.view_history):
      self.back_by_one()
    else:
      while len(self.view_history) - 1 >= index:
        self.back_by_one()

  def loading_sign(self):
    import widgets
    status_area = widgets.Text("LOADING")
    status_area.set_selected(True)
    status_area.rect.topleft = (130,200)
    status_area.update()
    status_area.draw(manager.screen)
    pygame.display.flip()

  def update(self):
    if self.is_idle():
      if not self.idle_start: self.idle_start = time.time()
      self.idle_seconds=time.time()-self.idle_start
    else: self.idle_start = 0

    self.view.update()
    self.nowplaying_button.update()

  def draw(self):
    for widget in self.view.get_widgets(): widget.draw(self.screen)
    self.nowplaying_button.draw(self.screen)
    self.a2dp_button.draw(self.screen)
    self.play_button.draw(self.screen)
    self.next_button.draw(self.screen)
    self.prev_button.draw(self.screen)
    self.repeat_button.draw(self.screen)
    self.dirty = False

  def wake_up(self,blind_action=False):
    if not blind_action:
      manager.has_focus = True
      self.screen_manually_blanked = False
      self.idle_start   = 0
      self.idle_seconds = 0
    if self.sleep_timer>1:
      self.sleep_timer=1

  def is_idle(self):
    if self.screen_status == "off" or self.screen_manually_blanked: return True
    if self.dirty: return False
    for widget in self.view.get_widgets():
      if not widget.is_idle():
        return False
    return True

  def is_extended_idle(self):
    if globals.ISMAEMO:
      if self.screen_status == "off" or not self.has_focus or self.screen_manually_blanked:
        return True
    else:
      if self.idle_seconds > 5: return True
    return False

  def check_sleep_timer(self):
    if self.screen_status == "off" and self.player and not self.player.paused:
      if self.sleep_timer==1:
        self.clear_delayed_message("timer")
        self.sleep_timer = time.time()
      elif self.sleep_timer>1 and time.time() - self.sleep_timer >= self.sleep_timer_dur:
        print "sleep timer active!"
        self.player.set_pause(True)
        self.sleep_timer = 1    # in case of a remote unpause prevent immediate reactivation
        self.set_delayed_message("timer", "Sleep timer active")

  def set_screen_status(self,new_status):
    if self.screen_status == "dimmed": pygame.event.clear() # ignore taps on dimmed screen
    self.screen_status = new_status
    if new_status == "on" and self.delayed_info_message != "":
      globals.infobanner(self.delayed_info_message)
      self.clear_delayed_message()

  def set_scrollbar_state(self, value):
    self.scrollbar_state = value

  def get_scrollbar_state(self):
    return self.scrollbar_state

  def set_headphone_sense(self, value):
    self.headphone_sense = value

  def get_headphone_sense(self):
    return self.headphone_sense

  def set_sort_albums_by_year(self, value):
    self.sort_albums_by_year = value

  def get_sort_albums_by_year(self):
    return self.sort_albums_by_year

  def set_delayed_message(self, type, message):
    self.delayed_info_type=type
    self.delayed_info_message=message

  def clear_delayed_message(self, type=""):
    if self.delayed_info_type==type or type=="":
      self.delayed_info_message=""

  def update_powersave(self):
    gc.collect(1) # probably a good opportunity to run the GC as screen mode changes mess up the frame rate anyway.
    if self.screen_manually_blanked:
      if self.screen_status == "dimmed": globals.blank_screen()
      if self.screen_status == "on":
        print "screen on. disabling manual screen blank"
        self.screen_manually_blanked = False
    if self.player:
      if self.screen_status == "off" and self.on_battery: self.player.set_powersave(True)
      else: self.player.set_powersave(False)

  def quit(self):
    self.playlist.stop()
    self.remote.close()
    self.playlist.save()
    self.prefs.save()
    if self.dbusapi: self.dbusapi.state_changed("exit")

  def cleanup_views(self):
    if self.view and self.view.is_temporary and self.view: self.view.close()

  def show_menu(self):
    import views
    new_view = views.MenuView()
    new_view.show()

  # FIXME: manager.show_* methods are deprecated!
  #        Any necessary logic should go in the appropriate view.show() method.
  def show_artist_albums(self,selected_artist):
    if not selected_artist: return
    self.show_artist_albums_ext(selected_artist.artist_art.id,selected_artist.artist.name)

  def show_artist_albums_ext(self,artist_id,artist_name):
    import views
    print "showing songs for artist=" + artist_name
    new_view = views.ArtistAlbumView(artist_id,artist_name)
    if new_view.empty_view:
      views.ArtistSongsView(artist_id,artist_name).show()
      return
    new_view.show()

  def show_songs(self,selected_album):
    if not selected_album: return
    self.show_songs_ext(selected_album.album.id,selected_album.album.name)

  def show_songs_ext(self,album_id,album_name):
    import views
    print "showing songs for album=" + album_name
    new_view = views.SongView(album_id,album_name)
    new_view.show()

  def show_nowplaying(self,force=False):
    if not manager.playlist.list: return
    # This is a tri-mode button
    if force or self.view not in [self.nowplaying_view,self.cover_view]:
      print "showing nowplaying"
      self.nowplaying_view.show()
    elif self.view == self.nowplaying_view:
      self.show_cover_view()
    else:
      self.show_songposition_view()

  def show_cover_view(self):
    if self.playlist.current == None: return
    print "showing cover view"
    if self.cover_view == None:
      import views
      self.cover_view = views.SyncCoverView()
    self.cover_view.show()
    self.cover_view.update_image()

  def show_albumcover_view(self,album_id=None):
    print "showing albumcover view"
    import views
    new_view = views.AlbumCoverView()
    new_view.show()
    self.view.update_image(album_id)

  def show_artistcover_view(self,artist_id):
    print "showing artistcover view"
    import views
    new_view = views.ArtistCoverView()
    new_view.show()
    self.view.update_image(artist_id)

  def show_songposition_view(self):
    if not self.songposition_view:
      import views
      self.songposition_view = views.SongPositionView()
    if not self.songposition_view or not self.player.length: return # protect against calling before initialized
    print "showing song position view"
    self.songposition_view.show()
    self.view.update_selection()

  def show_volume(self):
    if not self.volume_view: return # protect against calling before initialized
    print "showing volume"
    if self.view == self.nowplaying_view: 
      self.view.scroll_widget.stop_animation()
    self.volume_view.show()
    self.view.update_selection()

  def show_exit_confirm(self):
#    import views
#    print "showing exit confirm"
#    new_view = views.ExitConfirmView()
#    new_view.show()
    if (not globals.confirm_dlg("Quit Kagu?", gtk.STOCK_QUIT)): return
    self.quit()
    sys.exit(0)

  def clear(self):
    self.screen.blit(self.background,(0,0))

  def prev_track(self):
    if self.player.seconds >= 5:
      print "prev: seeking to beginning"
      self.player.seek(0, 2)
      return
    self.playlist.prev(None,None)

  def next_track(self):
    if self.playlist.exhausted():
      print "no next track, ignored request"
      return
    self.playlist.next(None,None,force=True)

  def switch_player(self, player_name=None, skip_if_a2dp=True, set_a2dp=False):
    import mplayer
    if skip_if_a2dp and isinstance(self.player, mplayer.Mplayer):
      if self.player.get_a2dpd():
        return False
    self.clear()
    import widgets
    status_area = widgets.Text("PLEASE WAIT...")
    status_area.rect.topleft = (130,200)
    status_area.update()
    status_area.draw(self.screen)
    pygame.display.flip()
      
    target = self.player.target
    paused = self.player.paused
    volume = self.player.volume
    seconds = self.player.seconds
    self.player.close()
    self._get_player(player_name=player_name)
    if set_a2dp and isinstance(self.player, mplayer.Mplayer):
      self.player.set_a2dpd(True)
    self.player.ignore_next_interruption_till = time.time() + 8
    if target:
      self.player.play(target)
      self.player.set_volume(volume,show_volumeview=False)
      self.player.seek(seconds,2,True)
      if paused: self.player.pause(True)
      if seconds: # make sure we're currently listening to something
        waited = 0
        while not self.player.seconds and waited<10:
          self.player._query_status()
          time.sleep(0.1)
          waited = waited + 0.1
        if waited>=10:
          print "oops, _query_status failed for 10 secs"
    return True
      

manager = Manager()
