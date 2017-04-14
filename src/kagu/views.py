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

import pygame, time, gc, gobject, sys, os
from pygame.locals import *
import globals,widgets
from db import db as db
from manager import manager as manager
from theme   import theme   as theme


class BaseView():
  def __init__(self, caption=None, show_clear_playlist=True):
    ''' This class defines a basic interface for a view (or in web programming terms, a page).
    If Manager is the brain of the app, then each View is the brain of that screen or page. '''
    manager.loading_sign()
    self.widgets = [] # all widgets for a view are stored within that view
    self.scroll_widget = None
    self.is_temporary = False # can this view be garbage collected?
    self.back_button  = None
    self.add_to_history = True
    self._load_back_button()
    self.base_combo_timeout_start = 0
    self.empty_view = False
    self.title_label = None
    self.caption     = caption
    if caption!=None:
      self.title_label = widgets.Label(caption, Rect(0,0,125,26), 4, 4, 22)
      self.widgets.append(self.title_label)
    if show_clear_playlist: self.widgets.append(widgets.ClearPlaylistButton())

  def _load_back_button(self):
    if self.back_button or self.back_button in self.widgets: return False
    self.back_button = widgets.BackButton()
    self.widgets.append(self.back_button)

  def get_widgets(self):
    return self.widgets
    
  def is_combo(self, event=None):
    if self.scroll_widget!=None and manager.nowplaying_button!=None and manager.nowplaying_button.is_pressed():
        return True
    if event!=None and event.type==KEYDOWN and ((event.mod&128)>0):
        return True
    return False
  
  def can_handle_combo(self, event=None, is_base=False):
    if event!=None and event.type==KEYDOWN and ((event.mod&128)>0):
        return True
    if is_base==True and (time.time()-self.base_combo_timeout_start > 0.1):
        return True
    if is_base==False and (time.time()-self.combo_timeout_start > 0.1):
        return True
    return False
  
  def handle_event(self,event):
    if self.is_combo(event):
      if event.type == KEYDOWN and (event.key == K_LEFT or event.key == K_RIGHT or event.key == K_RETURN):
        can_handle = self.can_handle_combo(event, True)
        if can_handle==True and event.key == K_LEFT:
          self.scroll_widget.move_home()
        elif can_handle==True and event.key == K_RIGHT:
          self.scroll_widget.move_end()
        elif can_handle==True and event.key in [K_RETURN, K_s]:
          manager.playlist.save_as_dlg()

        manager.nowplaying_button.set_ignore_next_mouseup(True)
        self.base_combo_timeout_start = time.time()
        return True

    for widget in self.widgets:
      if widget.handle_event(event): return True
    return False

  def show(self):
    if manager.view != self:
      manager.loading_sign()

      if manager.view:
        if self not in manager.view_history:
          if manager.view.add_to_history:
            manager.view_history.append(manager.view)
        else:
          # roll back history to this view before this view
          index = manager.view_history.index(self)
          print "rolling back view history to %s,index=%s" % (self,index)
          manager.back(index)
          #manager.view_history = manager.view_history[:index]
      manager.view  = self
      manager.dirty = True
      self.back_button._load_image()
#      print "view_history=%s,view=%s" % (manager.view_history,manager.view)
      pygame.event.clear()
      if self.scroll_widget:
        self.scroll_widget.snap_selected()
        self.scroll_widget.set_scrollbar(manager.get_scrollbar_state())

  def update(self):
    for widget in self.widgets: widget.update()

  def close(self):
    self.scroll_widget = None
    for widget in self.widgets: widget.close()
    self.widgets = None


class TimerView(BaseView):
  def __init__(self,timeout=3000,caption=None):
    ''' This is the Zoomed Album Cover view '''
    BaseView.__init__(self,caption)
    self.timeout        = timeout # jump to last_view after timeout milliseconds
    self.timeout_cb     = None
    self.add_to_history = False # TimerViews don't show up in the view history

  def show(self):
    BaseView.show(self)
    self.reset_timeout()

  def reset_timeout(self):
    if self.timeout_cb: gobject.source_remove(self.timeout_cb)
    self.timeout_cb = gobject.timeout_add(self.timeout, self.show_last_view)

  def stop_timeout(self):
    if self.timeout_cb: gobject.source_remove(self.timeout_cb)
    self.timeout_cb = None

  def show_last_view(self):
    self.stop_timeout()

    if manager.view != self:
      return False # timeout invalid when we aren't the current view

    manager.back()


class AlbumView(BaseView):
  def __init__(self):
    ''' This is the album selection view '''
    BaseView.__init__(self, 'Albums')
    self.combo_timeout_start = 0
    self.album_widget = None
    self._load_album_widget()
    self.scroll_widget = self.album_widget
    self.widgets.append(widgets.VolumeButton())

  def _load_album_widget(self):
    if self.album_widget: return

    widget = widgets.ScrollWidget(Rect(
      130,
      manager.screen.get_rect().top,
      545,
      manager.screen.get_rect().bottom
    ),self._make_ok_button_callback(),
    self._get_album_list(),
    self.albumartist_generator_callback,
    filterable=True)
    
    self.album_widget = widget
    self.widgets.append(widget)

  def _get_album_list(self):
    processtart=time.time()
    sort_by = 'name'
    if manager.get_sort_albums_by_year(): sort_by = 'year'
    list =  db.get_albums(sort_by = sort_by)
    print "album query took:" + str(time.time()-processtart)
    return list

  def albumartist_generator_callback(self,id,row,get_name=False):
    if get_name:
        return row['album']
    return widgets.AlbumArtist(row['album_id'],row['album'],row['artist_id'],row['artist'])

  def _make_ok_button_callback(self):
    def _ok_button_callback():
      sel_sprite = manager.view.scroll_widget.get_focused_sprite()
      return manager.show_songs(sel_sprite)
    return _ok_button_callback

  def handle_event(self,event):
    if self.is_combo(event):
     if event.type == KEYDOWN and event.key==K_F4:
        can_handle = self.can_handle_combo(event)

        if can_handle==True and event.key == K_F4 and self.scroll_widget.has_focused():
          i = self.scroll_widget.get_focused_sprite_index()
          sel_albumartist = self.scroll_widget.visible_sprites[i]['sprite']
          print "artist = ",sel_albumartist.artist.name
          manager.ignore_keypad_till = time.time() + 2
          manager.nowplaying_button.set_pressed(False) # will change views below
          ArtistSongsView(sel_albumartist.artist_id,sel_albumartist.artist.name).show()

        manager.nowplaying_button.set_ignore_next_mouseup(True)
        self.combo_timeout_start = time.time()
        return True

    return BaseView.handle_event(self,event)


class ArtistView(BaseView):
  def __init__(self):
    ''' This is the artist selection view '''
    BaseView.__init__(self, 'Artists')
    self.combo_timeout_start = 0
    self.album_widget = None
    self._load_album_widget()
    self.scroll_widget = self.album_widget
    self.widgets.append(widgets.VolumeButton())

  def _load_album_widget(self):
    if self.album_widget: return

    widget = widgets.ScrollWidget(Rect(
      130,
      manager.screen.get_rect().top,
      545,
      manager.screen.get_rect().bottom
    ),self._make_ok_button_callback(),
    self._get_artist_list(),
    self.artist_generator_callback,
    filterable=True)
    
    self.album_widget = widget
    self.widgets.append(widget)

  def _get_artist_list(self):
    processtart=time.time()
    list =  db.get_artists()
    print "artist query took:" + str(time.time()-processtart)
    return list

  def artist_generator_callback(self,id,row,get_name=False):
    if get_name:
        return row['artist']
    return widgets.Artist(row['artist_id'],row['artist'])

  def _make_ok_button_callback(self):
    def _ok_button_callback():
      sel_sprite = manager.view.scroll_widget.get_focused_sprite()
      return manager.show_artist_albums(sel_sprite)
    return _ok_button_callback

  def handle_event(self,event):
    if self.is_combo(event):
      if event.type == KEYDOWN and (event.key==K_F4):
        can_handle = self.can_handle_combo(event)

        if can_handle==True and event.key == K_F4 and self.scroll_widget.has_focused():
          i = self.scroll_widget.get_focused_sprite_index()
          sel_artist = self.scroll_widget.visible_sprites[i]['sprite']
          print "artist = ",sel_artist.artist.name
          manager.ignore_keypad_till = time.time() + 2
          manager.nowplaying_button.set_pressed(False) # will change views below
          ArtistSongsView(sel_artist.artist_art.id,sel_artist.artist.name).show()

        manager.nowplaying_button.set_ignore_next_mouseup(True)
        self.combo_timeout_start = time.time()
        return True

    return BaseView.handle_event(self,event)


class PlaylistView(BaseView):
  def __init__(self):
    ''' This is the playlist selection view '''
    BaseView.__init__(self, 'Playlists')
    self.scroll_widget = None
    self._load_scroll_widget()
    self.widgets.append(widgets.VolumeButton())
    self.widgets.append(widgets.DeletePlaylistFileButton())

  def _load_scroll_widget(self):
    manager.clear()

    if self.scroll_widget != None:
      self.widgets.remove(self.scroll_widget)
      self.scroll_widget = None
      gc.collect(1)

    widget = widgets.ScrollWidget(Rect(
      130,
      manager.screen.get_rect().top,
      545,
      manager.screen.get_rect().bottom
    ),self._callback,
    self._get_playlist_list(),
    self.playlist_generator_callback)
    self.scroll_widget = widget
    self.widgets.append(widget)

  def _get_playlist_list(self):
    processtart=time.time()
    list = db.get_m3us()
    print "m3u query took:" + str(time.time()-processtart)
    return list

  def playlist_generator_callback(self,id,row,get_name=False):
    if get_name:
        return row['name']
    return widgets.M3U(row['id'],row['name'],row['path'])

  def _callback(self):
    sel_sprite = manager.view.scroll_widget.get_focused_sprite()
    if not sel_sprite: return
    M3UView(sel_sprite.id,sel_sprite.name,sel_sprite.path).show()


class GenreView(BaseView):
  def __init__(self):
    ''' This is the genre selection view '''
    BaseView.__init__(self, 'Genres')
    self.scroll_widget = None
    self._load_scroll_widget()
    self.widgets.append(widgets.VolumeButton())

  def _load_scroll_widget(self):
    manager.clear()

    if self.scroll_widget != None:
      self.widgets.remove(self.scroll_widget)
      self.scroll_widget = None
      gc.collect(1)

    widget = widgets.ScrollWidget(Rect(
      130,
      manager.screen.get_rect().top,
      545,
      manager.screen.get_rect().bottom
    ),self._callback,
    self._get_genre_list(),
    self.genre_generator_callback,
    wrap=False,
    filterable=True)
    self.scroll_widget = widget
    self.widgets.append(widget)

  def _get_genre_list(self):
    processtart=time.time()
    list = db.get_genres()
    final_list = []
    for row in list:
      artist_list = db.get_artists(genre_id=row['id'])
      if artist_list: final_list.append(row)
    print "genre query took:" + str(time.time()-processtart)
    return final_list

  def genre_generator_callback(self,id,row,get_name=False):
    if get_name:
        return row['name']
    return widgets.Genre(row['id'],row['name'])

  def _callback(self):
    sel_sprite = manager.view.scroll_widget.get_focused_sprite()
    GenreArtistView(sel_sprite.id,sel_sprite.name).show()


class SongView(BaseView):
  def __init__(self,album_id,album):
    ''' This is the song selection view '''
    BaseView.__init__(self, 'Tracks',show_clear_playlist=False)
    self.is_temporary = True # can this view be garbage collected?
    self.combo_timeout_start = 0
    self.album       = album
    self.album_id    = album_id
    self._load_songalbum_button()
    self._load_song_widget()
    self.widgets.append(widgets.AddAlbumButton())

  def _load_song_widget(self):
    if self.scroll_widget != None:
      self.widgets.append(self.scroll_widget)
      return

    widget = widgets.ScrollWidget(Rect(
      130,
      manager.screen.get_rect().top,
      545,
      manager.screen.get_rect().bottom
    ),self._make_ok_button_callback(),
    self._get_song_list(),
    self.song_generator_callback,
    filterable=True)

    self.scroll_widget = widget
    self.widgets.append(widget)

  def _get_song_list(self):
    processtart=time.time()
    list = db.get_songs(album_id=self.album_id)
    print "song query took:" + str(time.time()-processtart)
    return list

  def song_generator_callback(self,id,song,get_name=False):
    if get_name:
        return song['title']
    return widgets.Song(song['track'],song['title'],song['path'],flags=song['flags'],artist=song['artist'],artist_id=song['artist_id'])

  def _play_continuous(self):
    manager.playlist.clear()
    for row in manager.view.scroll_widget.get_list():
      manager.playlist.add(row['path'])
    if manager.view.scroll_widget.has_focused(): # paranoia
      manager.playlist.play(manager.view.scroll_widget.get_focused_sprite_index())
      manager.show_nowplaying()

  def _make_ok_button_callback(self):
    def _ok_button_callback():
      sel_spr = manager.view.scroll_widget.get_focused_sprite()
      if not sel_spr: return
      if not manager.enqueue_mode:
        self._play_continuous()
      else:
        print "adding "+sel_spr.path
        manager.playlist.add(sel_spr.path)
        manager.playlist.update()
    return _ok_button_callback

  def _load_songalbum_button(self):
    ''' This is the album picture in the upper left.
    Clicking it should (eventually) bring up a hi res version of
    the album art. '''
    image = theme.get_surface((125,160))
    print "songalbum: " + self.album
    sprite = widgets.Album(self.album_id, self.album)
    sprite.draw(image,(0,0))

    artist = db.artist_of_album(self.album_id)
    globals.gprint(artist,image,(2,132),16)
    button = widgets.Button(image,self._make_songalbum_button_callback())
    button.rect.left = 0
    button.rect.top  = 26
    self.widgets.append(button)

  def _make_songalbum_button_callback(self):
    def _songalbum_button_callback():
      print "show AlbumCoverView"
      return manager.show_albumcover_view(album_id=self.album_id)
    return _songalbum_button_callback

  def handle_event(self,event):
    if self.is_combo(event):
      if event.type == KEYDOWN and (event.key==K_F4):
        can_handle = self.can_handle_combo(event)

        if can_handle==True and event.key == K_F4 and self.scroll_widget.has_focused():
          i = self.scroll_widget.get_focused_sprite_index()
          sel_song = self.scroll_widget.visible_sprites[i]['sprite']
          print "artist = ",sel_song.artist
          manager.ignore_keypad_till = time.time() + 2
          manager.nowplaying_button.set_pressed(False) # will change views below
          manager.show_artist_albums_ext(sel_song.artist_id,sel_song.artist)

        manager.nowplaying_button.set_ignore_next_mouseup(True)
        self.combo_timeout_start = time.time()
        return True

    return BaseView.handle_event(self,event)


class M3UView(BaseView):
  def __init__(self,m3u_id,m3u,m3u_path):
    ''' This is the song selection view '''
    BaseView.__init__(self, 'Playlist Tracks',show_clear_playlist=False)
    self.is_temporary = True # can this view be garbage collected?
    self.combo_timeout_start = 0
    self.m3u       = m3u
    self.m3u_id    = m3u_id
    self.m3u_path  = m3u_path
    self._load_song_widget()
    if len(self.songlist)>0:
      self.widgets.append(widgets.AddAlbumButton())

  def _load_song_widget(self):
    if self.scroll_widget != None:
      self.widgets.append(self.scroll_widget)
      return

    self.songlist  = self.load_songs()

    widget = widgets.ScrollWidget(Rect(
      130,
      manager.screen.get_rect().top,
      545,
      manager.screen.get_rect().bottom
    ),self._callback,
    self._get_song_list(),
    self.song_generator_callback)

    self.scroll_widget = widget
    self.widgets.append(widget)

  def _get_song_list(self):
    return self.songlist

  def load_songs(self):
    from m3u     import m3u     as m3u
    processtart=time.time()
    list = m3u.songs_of_path(self.m3u_path)
    print "m3u load took:" + str(time.time()-processtart)
    return list

  def song_generator_callback(self,id,song,get_name=False):
    if get_name:
        return song['title']
    return widgets.Song(song['track'],song['title'],song['path'],flags=song['flags'],artist=song['artist'],artist_id=song['artist_id'])

  def _play_continuous(self):
    manager.playlist.clear()
    for path in manager.view.scroll_widget.get_list():
      manager.playlist.add(path)
    if manager.view.scroll_widget.has_focused(): # paranoia
      manager.playlist.play(manager.view.scroll_widget.get_focused_sprite_index())
      manager.show_nowplaying()

  def _callback(self):
    sel_spr = manager.view.scroll_widget.get_focused_sprite()
    if not sel_spr: return
    if not manager.enqueue_mode:
      self._play_continuous()
    else:
      print "adding "+sel_spr.path
      manager.playlist.add(sel_spr.path)
      manager.playlist.update()

  def handle_event(self,event):
    if self.is_combo(event):
      if event.type == KEYDOWN and event.key==K_F4:
        can_handle = self.can_handle_combo(event)

        if can_handle==True and event.key == K_F4 and self.scroll_widget.has_focused():
          i = self.scroll_widget.get_focused_sprite_index()
          sel_song = self.scroll_widget.visible_sprites[i]['sprite']
          print "artist = ",sel_song.artist
          manager.ignore_keypad_till = time.time() + 2
          manager.nowplaying_button.set_pressed(False) # will change views below
          manager.show_artist_albums_ext(sel_song.artist_id,sel_song.artist)

        manager.nowplaying_button.set_ignore_next_mouseup(True)
        self.combo_timeout_start = time.time()
        return True

    return BaseView.handle_event(self,event)


class AllSongsView(BaseView):
  def __init__(self):
    ''' This is the all songs view '''
    BaseView.__init__(self, 'All Tracks',show_clear_playlist=False)
    self.album_widget = None
    self._load_album_widget()
    self.scroll_widget = self.album_widget
    self.widgets.append(widgets.VolumeButton())
    self.widgets.append(widgets.AddAlbumButton())
    self.is_temporary = True
    self.combo_timeout_start = 0

  def _load_album_widget(self):
    if self.album_widget: return

    widget = widgets.ScrollWidget(Rect(
      130,
      manager.screen.get_rect().top,
      545,
      manager.screen.get_rect().bottom
    ),self._make_ok_button_callback(),
    self._get_all_songs_list(),
    self.song_generator_callback,
    filterable=True)
    
    self.album_widget = widget
    self.widgets.append(widget)

  def _get_all_songs_list(self):
    processtart=time.time()
    list = db.get_songs()
    print "all songs query took:" + str(time.time()-processtart)
    return list

  def song_generator_callback(self,id,song,get_name=False):
    if get_name:
        return song['title']
    track=''
    if song['track']: track = "[%s] " % (song['track'],)
    return widgets.Song(id+1,track + song['title'],song['path'],artist=song['artist'],flags=song['flags'],artist_id=song['artist_id'])

  def _make_ok_button_callback(self):
    def _ok_button_callback():
      sel_spr = manager.view.scroll_widget.get_focused_sprite()
      if not sel_spr: return
      if not manager.enqueue_mode:
        self._play_continuous()
      else:
        print "adding "+sel_spr.path
        manager.playlist.add(sel_spr.path)
        manager.playlist.update()
    return _ok_button_callback

  def handle_event(self,event):
    if self.is_combo(event):
      if event.type == KEYDOWN and event.key==K_F4:
        can_handle = self.can_handle_combo(event)

        if can_handle==True and event.key == K_F4 and self.scroll_widget.has_focused():
          i = self.scroll_widget.get_focused_sprite_index()
          song = self.scroll_widget.visible_sprites[i]['sprite']
          print "artist = ",song.artist
          manager.ignore_keypad_till = time.time() + 2
          manager.nowplaying_button.set_pressed(False) # will change views below
          manager.show_artist_albums_ext(song.artist_id,song.artist)

        manager.nowplaying_button.set_ignore_next_mouseup(True)
        self.combo_timeout_start = time.time()
        return True

    return BaseView.handle_event(self,event)


class ArtistSongsView(BaseView):
  def __init__(self,artist_id,artist):
    ''' This is the artist songs view '''
    BaseView.__init__(self, 'Tracks of Artist',show_clear_playlist=False)
    self.artist = artist
    self.artist_id = artist_id
    self.album_widget = None
    self._load_album_widget()
    self._load_songartist_button()
    self.scroll_widget = self.album_widget
    self.widgets.append(widgets.AddAlbumButton())
    self.is_temporary = True
    self.combo_timeout_start = 0

  def _load_album_widget(self):
    if self.album_widget: return

    widget = widgets.ScrollWidget(Rect(
      130,
      manager.screen.get_rect().top,
      545,
      manager.screen.get_rect().bottom
    ),self._make_ok_button_callback(),
    self._get_artist_songs_list(),
    self.song_generator_callback,
    filterable=True)
    
    self.album_widget = widget
    self.widgets.append(widget)

  def _get_artist_songs_list(self):
    processtart=time.time()
    list = db.get_songs(artist_id=self.artist_id)
    print "artist songs query took:" + str(time.time()-processtart)
    return list

  def song_generator_callback(self,id,song,get_name=False):
    if get_name:
        return song['title']
    track=''
    if song['track']: track = "[%s] " % (song['track'],)
    return widgets.Song(id+1,track + song['title'],song['path'],artist=song['artist'],flags=song['flags'],artist_id=song['artist_id'],album=song['album'],album_id=song['album_id'],subtext_album=True)

  def _make_ok_button_callback(self):
    def _ok_button_callback():
      sel_spr = manager.view.scroll_widget.get_focused_sprite()
      if not sel_spr: return
      if not manager.enqueue_mode:
        self._play_continuous()
      else:
        print "adding "+sel_spr.path
        manager.playlist.add(sel_spr.path)
        manager.playlist.update()
    return _ok_button_callback

  def _load_songartist_button(self):
    ''' This is the artist picture in the upper left.
    Clicking it should bring up a hi res version of
    the album art. '''
    image = theme.get_surface((125,160))
    print "songartist: " + self.artist
    sprite = widgets.ArtistArt(self.artist_id, self.artist)
    sprite.draw(image,(0,0))

    globals.gprint(self.artist,image,(2,132),16)
    button = widgets.Button(image,self._songartist_button_callback)
    button.rect.left = 0
    button.rect.top  = 26
    self.widgets.append(button)

  def _songartist_button_callback(self):
      print "show ArtistCoverView"
      return manager.show_artistcover_view(self.artist_id)

  def handle_event(self,event):
    if self.is_combo(event):
      if event.type == KEYDOWN and event.key==K_F4:
        can_handle = self.can_handle_combo(event)

        if can_handle==True and event.key == K_F4 and self.scroll_widget.has_focused():
          i = self.scroll_widget.get_focused_sprite_index()
          song = self.scroll_widget.visible_sprites[i]['sprite']
          print "album = ",song.album
          manager.ignore_keypad_till = time.time() + 2
          manager.nowplaying_button.set_pressed(False) # will change views below
          manager.show_songs_ext(song.album_id,song.album)

        manager.nowplaying_button.set_ignore_next_mouseup(True)
        self.combo_timeout_start = time.time()
        return True

    return BaseView.handle_event(self,event)


class ArtistAlbumView(BaseView):
  def __init__(self,artist_id,artist_name):
    ''' This is the artist songs view '''
    BaseView.__init__(self, 'Albums of Artist',show_clear_playlist=False)
    self.artist       = artist_name
    self.artist_id    = artist_id
    self.list         = []
    processtart=time.time()
    sort_by = 'name'
    if manager.get_sort_albums_by_year(): sort_by = 'year'
    self.list =  db.get_albums(artist_id=self.artist_id,sort_by = sort_by)
    print "album query took:" + str(time.time()-processtart)
    self.empty_view = (len(self.list)==0)
    if self.empty_view:
      return
    self.album_widget = None
    self._load_songartist_button()
    self._load_album_widget()
    self.scroll_widget = self.album_widget
    self.widgets.append(widgets.AddAlbumButton())
    self.is_temporary = True
    self.combo_timeout_start = 0

  def _load_album_widget(self):
    if self.album_widget: return

    widget = widgets.ScrollWidget(Rect(
      130,
      manager.screen.get_rect().top,
      545,
      manager.screen.get_rect().bottom
    ),self._ok_button_callback,
    self._get_artist_album_list(),
    self.album_generator_callback,
    filterable=True)
    
    self.album_widget = widget
    self.widgets.append(widget)

  def _get_artist_album_list(self):
#    processtart=time.time()
#    list =  db.get_albums(artist_id=self.artist_id)
#    print "album query took:" + str(time.time()-processtart)
    return self.list

  def album_generator_callback(self,id,row,get_name=False):
    if get_name:
        return row['artist']
    return widgets.AlbumArtist(row['album_id'],row['album'],row['artist_id'],row['artist'])

  def _ok_button_callback(self):
    sel_sprite = manager.view.scroll_widget.get_focused_sprite()
    return manager.show_songs(sel_sprite)

  def _load_songartist_button(self):
    ''' This is the artist picture in the upper left.
    Clicking it should bring up a hi res version of
    the album art. '''
    image = theme.get_surface((125,160))
    print "songartist: " + self.artist
    sprite = widgets.ArtistArt(self.artist_id, self.artist)
    sprite.draw(image,(0,0))

    globals.gprint(self.artist,image,(2,132),16)
    button = widgets.Button(image,self._songartist_button_callback)
    button.rect.left = 0
    button.rect.top  = 26
    self.widgets.append(button)

  def _songartist_button_callback(self):
      print "show ArtistCoverView"
      return manager.show_artistcover_view(self.artist_id)

  def handle_event(self,event):
    if self.is_combo(event):
      if event.type == KEYDOWN and event.key==K_F4:
        can_handle = self.can_handle_combo(event)

        if can_handle==True and event.key == K_F4:
          manager.ignore_keypad_till = time.time() + 2
          manager.nowplaying_button.set_pressed(False) # will change views below
          ArtistSongsView(self.artist_id,self.artist).show()

        manager.nowplaying_button.set_ignore_next_mouseup(True)
        self.combo_timeout_start = time.time()
        return True

    return BaseView.handle_event(self,event)


class NowPlayingView(BaseView):
  def __init__(self):
    ''' This is the nowplaying selection view '''
    BaseView.__init__(self, 'Now Playing')
    self.album = None
    self.dirty = False
    self.combo_timeout_start = 0
    self.last_selected_index = None
    self._load_scroll_widget()
    self.widgets.append(widgets.VolumeButton())
    self.widgets.append(widgets.DeleteOneButton())
    self.update()

  def _load_scroll_widget(self):
    if self.scroll_widget != None:
      self.widgets.remove(self.scroll_widget)
      self.scroll_widget = None
    gc.collect(1)

    manager.clear()
    if self.dirty:
      status_area = widgets.Text("ADDING TO PLAYLIST")
      status_area.rect.topleft = (130,200)
      status_area.update()
      status_area.draw(manager.screen)
      pygame.display.flip()

    widget = widgets.ScrollWidget(Rect(
      130,
      manager.screen.get_rect().top,
      545,
      manager.screen.get_rect().bottom
    ),self._callback,
    self._get_song_list(),
    self.song_generator_callback,
    wrap=False,
    filterable=True)

    self.scroll_widget = widget
    self.widgets.append(widget)
    self.dirty = False

  def _get_song_list(self):
    return manager.playlist.list

  def song_generator_callback(self,id,path,get_name=False):
    song = db.song_of_path(path)[0]
    if get_name:
        return song['title']
    track=''
    if song['track']: track = "[%s] " % (song['track'],)
    return widgets.Song(id+1,track + song['title'],song['path'],artist=song['artist'],flags=song['flags'],artist_id=song['artist_id'])

  def _play_continuous(self):
    if not manager.view.scroll_widget.get_focused_sprite(): return
    if manager.view.scroll_widget.has_focused(): # paranoia
      if self.last_selected_index != self.scroll_widget.get_selected_sprite_index():
        manager.playlist.play(manager.view.scroll_widget.get_focused_sprite_index())
      else: manager.show_nowplaying()

  def _callback(self):
    self._play_continuous()

  def update_selection(self):
    print "now update: %s" % (manager.playlist.current,)
    if self.dirty: self._load_scroll_widget()
    manager.nowplaying_button.update()

    if not manager.playlist.list or manager.playlist.is_empty():
      return

    list = self.scroll_widget.get_list()
    c = 0
    for row in list:
      if not manager.playlist.is_empty() and c == manager.playlist.current:
        self.scroll_widget.set_focused_index(c,snap=True)
        self.scroll_widget.set_selected_index(c)
        print "selectednow: %s" % (self.scroll_widget.get_selected_sprite().path,)
      c += 1

    self.last_selected_index = self.scroll_widget.get_selected_sprite_index()

  def remove_item(self):
    i = self.scroll_widget.get_focused_sprite_index()
    manager.playlist.remove_item(i)
    if manager.playlist.is_empty():
      manager.back()
      return False
    self.scroll_widget.calc_scrollable()
    self.scroll_widget.flush_visible()
    self.update_selection()

  def handle_event(self,event):
    if self.is_combo(event):
      if event.type == KEYDOWN and (event.key==K_UP or event.key==K_DOWN or event.key==K_ESCAPE or event.key==K_F4):
        can_handle = self.can_handle_combo(event)

        if can_handle==True and event.key == K_UP and self.scroll_widget.has_focused():
          i = self.scroll_widget.get_focused_sprite_index()
          if i>0:
            manager.playlist.swap_items(i, i-1)
            self.scroll_widget.swapped_items(i, i-1)
        elif can_handle==True and event.key == K_DOWN and self.scroll_widget.has_focused():
          i = self.scroll_widget.get_focused_sprite_index()
          l = len(self.scroll_widget.get_list())-1
          if i<l:
            manager.playlist.swap_items(i, i+1)
            self.scroll_widget.swapped_items(i, i+1)
        elif can_handle==True and event.key == K_ESCAPE and self.scroll_widget.has_focused():
          i = self.scroll_widget.get_focused_sprite_index()
          if i>0:
            manager.playlist.swap_items(0, i)
            self.scroll_widget.swapped_items(0, i)
          l = len(self.scroll_widget.get_list())-1
          for j in xrange(1, l+1):
            manager.playlist.remove_item(1)
          self.scroll_widget.calc_scrollable()
          self.scroll_widget.flush_visible()
          self.update_selection()
        elif can_handle==True and event.key == K_F4 and self.scroll_widget.has_focused():
          i = self.scroll_widget.get_focused_sprite_index()
          song = self.scroll_widget.visible_sprites[i]['sprite']
          print "artist = ",song.artist
          manager.ignore_keypad_till = time.time() + 2
          manager.nowplaying_button.set_pressed(False) # will change views below
          manager.show_artist_albums_ext(song.artist_id,song.artist)

        manager.nowplaying_button.set_ignore_next_mouseup(True)
        self.combo_timeout_start = time.time()
        return True

    return BaseView.handle_event(self,event)


class GenreArtistView(BaseView):
  def __init__(self,genre_id,genre_name):
    ''' This is the genre artist view '''
    BaseView.__init__(self, genre_name)
    self.genre       = genre_name
    self.genre_id    = genre_id
    self.list         = []

    processtart=time.time()
    self.list =  db.get_artists(genre_id=self.genre_id)
    print "artist query took:" + str(time.time()-processtart)
    self.empty_view = (len(self.list)==0)
    if self.empty_view:
      return
    self.scroll_widget = None
    self._load_scroll_widget()
    self.is_temporary = True
    self.combo_timeout_start = 0
    self.widgets.append(widgets.VolumeButton())

  def _load_scroll_widget(self):
    if self.scroll_widget: return

    widget = widgets.ScrollWidget(Rect(
      130,
      manager.screen.get_rect().top,
      545,
      manager.screen.get_rect().bottom
    ),self._selected_callback,
    self.list,
    self._generator_callback)
    
    self.scroll_widget = widget
    self.widgets.append(widget)

  def _generator_callback(self,id,row,get_name=False):
    if get_name:
        return row['artist']
    return widgets.Artist(row['artist_id'],row['artist'])

  def _selected_callback(self):
    sel_sprite = manager.view.scroll_widget.get_focused_sprite()
    return manager.show_artist_albums(sel_sprite)


class VolumeView(TimerView):
  def __init__(self):
    ''' This is the nowplaying selection view '''
    TimerView.__init__(self,caption='Volume')
    self.album         = None
    self.cur_percent   = manager.player.volume
    self.slider_widget = None
    self._load_slider_widget()
    self.widgets.append(widgets.VolumeButton())
    self.update_selection()

  def _load_slider_widget(self):
    x = 130

    # Create Volume + Button
    plus_button = widgets.Button(theme.get_image('add'),self._plus_callback,True,repeat=True)
    plus_button.rect.left = x
    plus_button.rect.top  = manager.screen.get_rect().top + 18
    self.widgets.append(plus_button)

    # Create Volume - Button
    minus_button = widgets.Button(theme.get_image('remove'),self._minus_callback,True,repeat=True)
    minus_button.rect.left = x
    minus_button.rect.top  = manager.screen.get_rect().top + 420
    self.widgets.append(minus_button)

    # Create Slider Widget
    widget = widgets.Slider(Rect(
      x,
      manager.screen.get_rect().top + 60,
      57,
      360),
      self._slider_callback)
    
    self.slider_widget = widget
    self.widgets.append(widget)

  def _slider_callback(self):
    self.cur_percent = self.slider_widget.get_percent()
    print "volume callback: %s" % (self.cur_percent,)
    manager.player.set_volume(self.cur_percent)

  def _plus_callback(self):
    manager.player.volume_increase()

  def _minus_callback(self):
    manager.player.volume_decrease()

  def handle_event(self,event):
    if self.slider_widget:
      if event.type == KEYDOWN:
        if event.key == K_UP:
          self._plus_callback()
        elif event.key == K_DOWN:
          self._minus_callback()

    for widget in self.widgets:
      if widget.handle_event(event): return True
    return False

  def update(self):
    TimerView.update(self)
    if not self.slider_widget.is_idle(): self.reset_timeout()

  def update_selection(self):
    print "volume update: %s" % (manager.player.volume,)
    self.cur_percent = manager.player.volume
    self.slider_widget.set_percent(self.cur_percent)


class SongPositionView(BaseView):
  def __init__(self):
    ''' This is the nowplaying selection view '''
    BaseView.__init__(self,caption='Seek')
    self.album         = None
    self.cur_seconds   = manager.player.seconds
    self.step          = 10
    self._load_scroll_widget()
    self.widgets.append(widgets.VolumeButton())
    self.update()

  def _load_scroll_widget(self):
    if self.scroll_widget != None:
      self.widgets.remove(self.scroll_widget)
      self.scroll_widget = None
    gc.collect(1)

    widget = widgets.ScrollWidget(Rect(
      130,
      manager.screen.get_rect().top,
      545,
      manager.screen.get_rect().bottom
    ),self._make_ok_button_callback(),
    self._get_unit_list(),
    self.time_generator_callback)

    self.scroll_widget = widget
    self.widgets.append(widget)

  def _calc_step(self):
    if manager.player.length > 3600:
      # 3600 = 1 hr in seconds
      self.step = 60
    else: self.step = 10

  def _get_unit_list(self):
    self._calc_step()
    l = range(0,int(manager.player.length),int(self.step))
    return l

  def time_generator_callback(self,id,seconds,get_name=False):
    if get_name:
        return ""
    return widgets.Time(seconds)

  def _make_ok_button_callback(self):
    def _ok_button_callback():
      sel_sprite = manager.view.scroll_widget.get_focused_sprite()
      if self.cur_seconds == sel_sprite.seconds:
        manager.back()
      else:
        manager.player.seek(sel_sprite.seconds,2)
        self.update_selection(False,sel_sprite.seconds)
    return _ok_button_callback

  def update_selection(self,reload=True,seconds=None):
    print "songposition_view update:"
    if reload: self._load_scroll_widget()
    if not seconds: seconds = manager.player.seconds
    if seconds > 0:
      self.cur_seconds = int(round(seconds/self.step) * self.step)
    else:
      self.cur_seconds = 0
    print "cur_seconds = %s" % (self.cur_seconds,)
    list = self.scroll_widget.get_list()
    c = 0
    for row in list:
      if row == self.cur_seconds:
        if not (self.scroll_widget.get_focused_sprite() and self.scroll_widget.get_focused_sprite().seconds == self.cur_seconds):
          self.scroll_widget.set_focused_index(c,snap=True)
          self.scroll_widget.set_selected_index(c)
        print "selected songpos: %s" % (self.scroll_widget.get_selected_sprite().seconds,)
      c += 1


class ExitConfirmView(BaseView):
  def __init__(self):
    ''' This is the exit confirmation dialog/view '''
    BaseView.__init__(self)
    self.album          = None
    self.add_to_history = False
    self._load_ok_button()
    self._load_cancel_button()
    self.widgets.append(widgets.VolumeButton())
    status_area = widgets.Text("                     Quit Kagu?         ")
    status_area.rect.topleft = (130,200)
    status_area.update()
    self.widgets.append(status_area)

  def _make_ok_button_callback(self):
    def _ok_button_callback():
      manager.quit()
      sys.exit(0)
    return _ok_button_callback

  def _make_cancel_button_callback(self):
    def _cancel_button_callback():
      manager.back()
    return _cancel_button_callback

  def _load_ok_button(self):
    rect = Rect(200,300,75,75)
    image = theme.get_surface((rect.width,rect.height))
    image.blit(manager.background,(0,0),rect)
    globals.gprint("OK",image,(25,25))
    button = widgets.Button(image,self._make_ok_button_callback(),True)
    button.rect.left = rect.left
    button.rect.top  = rect.top
    self.widgets.append(button)

  def _load_cancel_button(self):
    rect = Rect(400,300,200,75)
    image = theme.get_surface((rect.width,rect.height))
    image.blit(manager.background,(0,0),rect)
    globals.gprint("CANCEL",image,(25,25))
    button = widgets.Button(image,self._make_cancel_button_callback(),False)
    button.rect.left = rect.left
    button.rect.top  = rect.top
    self.widgets.append(button)


class SyncCoverView(BaseView):
  def __init__(self):
    ''' This is the Zoomed Sync Cover view '''
    BaseView.__init__(self, 'Cover Image')
    self.album_widget  = None
    self.cur_id        = 0
    self.cur_type      = ""
    self.nowplaying    = None
    self.widgets.append(widgets.VolumeButton())
    self.update()

  def _load_widget(self):
    if not manager.playlist.list or manager.playlist.is_empty(): return
    if self.nowplaying == manager.playlist.status(): return # don't run DB query if nothing has changed
    if manager.nowplaying_button.last_id==self.cur_id and manager.nowplaying_button.last_sprite_type==self.cur_type: return

    self.nowplaying = manager.playlist.status()
    processtart=time.time()
    new_id = 0
    if manager.nowplaying_button.last_sprite_type=='album':
      new_id = db.song_of_path(manager.playlist.status())[0]['album_id']
    else:
      new_id = db.song_of_path(manager.playlist.status())[0]['artist_id']
    print "sync cover DB query (song_of_path) took:" + str(time.time()-processtart)
    self.cur_type = manager.nowplaying_button.last_sprite_type
    
    if new_id == self.cur_id: return # don't update if nothing has changed

    if self.album_widget: # clean up old widget
      self.widgets.remove(self.album_widget)

    self.cur_id = new_id
    processtart=time.time()
    if manager.nowplaying_button.last_sprite_type=='album':
      art_path = db.art_path_of_album(new_id)
    else:
      art_path = db.art_path_of_artist(new_id)

    art = widgets.CoverArt(new_id,530,manager.screen.get_rect().bottom,art_path)
    self.album_widget = widgets.Button(art.image,self._callback,is_default=True)
    # center widget on screen
    self.album_widget.rect.top  = manager.screen.get_rect().centery - self.album_widget.rect.height / 2
    self.album_widget.rect.left = manager.screen.get_rect().centerx - self.album_widget.rect.width  / 2
    print "load synced cover took:" + str(time.time()-processtart)
    self.widgets.append(self.album_widget)

  def _callback(self):
    return manager.show_nowplaying()

  def update_image(self):
    print "SynchedCover update:"
    self._load_widget()

  def update(self):
    self._load_widget()
    BaseView.update(self)


class AlbumCoverView(BaseView):
  def __init__(self):
    ''' This is the Zoomed Album Cover view '''
    BaseView.__init__(self, 'Album Cover')
    self.album_widget  = None
    self.album_id      = None
    self.widgets.append(widgets.VolumeButton())
    self.update()

  def _load_album_widget(self,album_id):
    if self.album_id != None and self.album_id == album_id: return # don't update if nothing has changed

    if self.album_widget: # clean up old widget
      self.widgets.remove(self.album_widget)
      self.album_widget = None

    self.album_id = album_id
    processtart=time.time()
    art_path = db.art_path_of_album(album_id)
    art = widgets.CoverArt(album_id,530,manager.screen.get_rect().bottom,art_path)
    self.album_widget = widgets.Button(art.image,manager.back,is_default=True)
    # center widget on screen
    self.album_widget.rect.top  = manager.screen.get_rect().centery - self.album_widget.rect.height / 2
    self.album_widget.rect.left = manager.screen.get_rect().centerx - self.album_widget.rect.width  / 2
    print "load album cover took:" + str(time.time()-processtart)
    self.widgets.append(self.album_widget)

  def _callback(self):
    return manager.back()

  def update_image(self,album_id):
    print "AlbumCover update:"
    self._load_album_widget(album_id)


class ArtistCoverView(BaseView):
  def __init__(self):
    ''' This is the Zoomed Artist Cover view '''
    BaseView.__init__(self, 'Artist Image')
    self.artist_widget = None
    self.artist_id     = None
    self.widgets.append(widgets.VolumeButton())
    self.update()

  def _load_artist_widget(self,artist_id):
    if self.artist_id != None and self.artist_id == artist_id: return # don't update if nothing has changed

    if self.artist_widget: # clean up old widget
      self.widgets.remove(self.artist_widget)
      self.artist_widget = None

    self.artist_id = artist_id
    processtart=time.time()
    art_path = db.art_path_of_artist(artist_id)
    art = widgets.CoverArt(artist_id,530,manager.screen.get_rect().bottom,art_path)
    self.artist_widget = widgets.Button(art.image,manager.back,is_default=True)
    # center widget on screen
    self.artist_widget.rect.top  = manager.screen.get_rect().centery - self.artist_widget.rect.height / 2
    self.artist_widget.rect.left = manager.screen.get_rect().centerx - self.artist_widget.rect.width  / 2
    print "load artist cover took:" + str(time.time()-processtart)
    self.widgets.append(self.artist_widget)

  def update_image(self,artist_id):
    print "ArtistCover update:"
    self._load_artist_widget(artist_id)


class MenuView(BaseView):
  def __init__(self):
    ''' This is the main menu view '''
    BaseView.__init__(self, 'Kagu')
    self.album_widget = None
    self._load_album_widget()
    self.scroll_widget = self.album_widget
    self.widgets.append(widgets.VolumeButton())

  def _load_album_widget(self):
    if self.album_widget: return

    widget = widgets.ScrollWidget(Rect(
      130,
      manager.screen.get_rect().top,
      545,
      manager.screen.get_rect().bottom
    ),self._callback,
    self._get_menu_list(),
    self.menu_generator_callback,
    wrap=False)
    
    self.album_widget = widget
    self.widgets.append(widget)

  def _get_menu_list(self):
    list = ['Music','Now Playing','Settings']
    return list

  def menu_generator_callback(self,id,row,get_name=False):
    if get_name:
        return ""
    return widgets.Text(row)

  def _callback(self):
    sel_sprite_index = manager.view.scroll_widget.get_focused_sprite_index()
    name = manager.view.scroll_widget.get_list()[sel_sprite_index]
    if   name == 'Music':       MusicView().show()
    elif name == 'Now Playing': manager.show_nowplaying()
    elif name == 'Settings':    SettingsView().show()


class MusicView(BaseView):
  def __init__(self):
    ''' This is the music view '''
    BaseView.__init__(self, 'Music')
    self.album_widget = None
    self._load_album_widget()
    self.scroll_widget = self.album_widget
    self.widgets.append(widgets.VolumeButton())

  def _load_album_widget(self):
    if self.album_widget: return

    widget = widgets.ScrollWidget(Rect(
      130,
      manager.screen.get_rect().top,
      545,
      manager.screen.get_rect().bottom
    ),self._callback,
    self._get_menu_list(),
    self.menu_generator_callback,
    wrap=False)
    
    self.album_widget = widget
    self.widgets.append(widget)

  def _get_menu_list(self):
    list = ['Playlists','Artists','Albums','Tracks','Genres']
    return list

  def menu_generator_callback(self,id,row,get_name=False):
    if get_name:
        return ""
    return widgets.Text(row)

  def _callback(self):
    sel_sprite_index = manager.view.scroll_widget.get_focused_sprite_index()
    name = manager.view.scroll_widget.get_list()[sel_sprite_index]
    if   name == 'Albums':    AlbumView().show()
    elif name == 'Tracks':     AllSongsView().show()
    elif name == 'Artists':   ArtistView().show()
    elif name == 'Playlists': PlaylistView().show()
    elif name == 'Genres':    GenreView().show()


class SettingsView(BaseView):
  def __init__(self):
    ''' This is the settings menu view '''
    BaseView.__init__(self, 'Settings')
    self.album_widget = None
    self._load_album_widget()
    self.scroll_widget = self.album_widget
    self.widgets.append(widgets.VolumeButton())

  def _load_album_widget(self):
    if self.album_widget: return

    widget = widgets.ScrollWidget(Rect(
      130,
      manager.screen.get_rect().top,
      545,
      manager.screen.get_rect().bottom
    ),self._callback,
    self._get_menu_list(),
    self.menu_generator_callback,
    wrap=False)
    
    self.album_widget = widget
    self.widgets.append(widget)

  def _get_menu_list(self):
    list = ['Sleep Timer'
        ,   'Fullscreen'
        ,   'Scrollbars'
        ,   'Playlist Shuffling'
        ,   'Auto Play'
        ,   'Headphone Sense'
        ,   'Sort Albums by Year'
        ,   'Show Image'
        ]
    if globals.ISMAEMO:
#      list.append('Turn Off Screen')
#      if manager.has_mplayer:
       list.append('Player')
    return list

  def menu_generator_callback(self,id,row,get_name=False):
    if get_name:
        return row
    if row=='Sleep Timer':
      if manager.sleep_timer>0:
        if manager.sleep_timer_dur == 3600:
          row+=': 1 Hour'
        elif manager.sleep_timer_dur == 7200:
          row+=': 2 Hours'
        else:
          row+=': ON?'
      else:
        row+=': OFF'
    elif row=='Player':
      if manager.default_player=='ossoplayer':
        row+=': OSSOPlayer'
      elif manager.default_player=='mplayer':
        row+=': MPlayer'
      elif manager.default_player=='gstplayer':
        row+=': GStreamer'
      else:
        row+=': Unknown'
    elif row=='Show Image':
      if manager.nowplayingbuttonimage=="artist":
        row+=': Artist'
      elif manager.nowplayingbuttonimage=="album":
        row+=': Album'
      else:
        row+=': Unknown'
    elif row=='Fullscreen':
      return widgets.CheckBoxText(row, manager.is_fullscreen)
    elif row=='Scrollbars':
      return widgets.CheckBoxText(row, manager.get_scrollbar_state)
    elif row=='Playlist Shuffling':
      return widgets.CheckBoxText(row, manager.playlist.get_random)
    elif row=='Auto Play':
      return widgets.CheckBoxText(row, manager.playlist.get_autoplay)
    elif row=='Headphone Sense':
      return widgets.CheckBoxText(row, manager.get_headphone_sense)
    elif row=='Sort Albums by Year':
      return widgets.CheckBoxText(row, manager.get_sort_albums_by_year)
      
    return widgets.Text(row)


  def _callback(self):
    update = False
    sel_sprite_index = manager.view.scroll_widget.get_focused_sprite_index()
    name = manager.view.scroll_widget.get_list()[sel_sprite_index]
    if   name == 'Fullscreen': manager.set_display_mode(not manager.is_fullscreen())
    elif name == 'Playlist Shuffling': manager.playlist.set_random(not manager.playlist.get_random())
    elif name == 'Auto Play': manager.playlist.set_autoplay(not manager.playlist.get_autoplay())
    elif name == 'Headphone Sense': manager.set_headphone_sense(not manager.get_headphone_sense())
    elif name == 'Sort Albums by Year': manager.set_sort_albums_by_year(not manager.get_sort_albums_by_year())
    elif name == 'Scrollbars':
      manager.set_scrollbar_state(not manager.scrollbar_state)
      # reset scrollbar state in current view
      if manager.view.scroll_widget:
        manager.view.scroll_widget.set_scrollbar(manager.get_scrollbar_state())
      # reset scrollbar state in any views cached in the history
      for view in manager.view_history:
        if view.scroll_widget:
          view.scroll_widget.set_scrollbar(manager.get_scrollbar_state())
      update = True

    elif name == 'Sleep Timer':
      if manager.sleep_timer>0:
        if manager.sleep_timer_dur==3600:
          manager.sleep_timer_dur=7200
        else:
          manager.sleep_timer=0
      else:
        manager.sleep_timer=1
        manager.sleep_timer_dur=3600
      update = True
    elif name == 'Player':
      if manager.default_player=='mplayer':
        manager.default_player='ossoplayer'
      elif manager.default_player=='ossoplayer':
        manager.default_player='gstplayer'
      else:
      	if manager.has_mplayer:
            manager.default_player='mplayer'
        else:
            manager.default_player='ossoplayer'
      manager.switch_player()
      update = True
        
    elif name == 'Turn Off Screen':
      globals.blank_screen()
      manager.screen_manually_blanked = True
    elif name == 'Show Image':
      if manager.nowplayingbuttonimage=="artist":
        manager.nowplayingbuttonimage="album"
      else:
        manager.nowplayingbuttonimage="artist"
      manager.nowplaying_button.update(True)
      update = True
      

    if update: self.scroll_widget.swapped_items(0, 0)



