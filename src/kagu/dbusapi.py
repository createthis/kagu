#!/usr/bin/env python
#
#
#   Copyright (c) 2007 Kemal Hadimli <disqkk@gmail.com>
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

from manager import manager as manager
import globals,playlist
from db import db as db
import dbus
import dbus.glib
import dbus.service
import gobject, time, thread, os

DBUSAPI_IFC='com.nokia.kagu'

class DBusApi(dbus.service.Object):
  def __init__(self, object_path='/com/nokia/kagu'):
    self.init_ok = False
    try:
      bus = dbus.SessionBus(private=True)
      bus_name = dbus.service.BusName(DBUSAPI_IFC, bus=bus)
      dbus.service.Object.__init__(self, bus_name, object_path)
      self.init_ok = True
    except:
      print "Error initializing DBusApi"

# FIXME: untested
# dbus-send --print-reply --type=method_call --dest=com.nokia.kagu /com/nokia/kagu com.nokia.kagu.query_status
# doesn't work?
  @dbus.service.method(dbus_interface=DBUSAPI_IFC, in_signature='', out_signature='')
  def query_status(self):
    if manager.playlist.status()!=None:
      self.update_play()
    else:
      self.stopped()

# FIXME: untested
# return statements could cause exceptions
  @dbus.service.method(dbus_interface=DBUSAPI_IFC, in_signature='', out_signature='uu')
  def get_position(self):
    if manager.playlist.status()!=None:
      return(int(manager.player.seconds),int(manager.player.length),)
    else:
      return(0,0,)

  @dbus.service.signal(dbus_interface=DBUSAPI_IFC, signature='u')
  def volume_changed(self, vol):
    pass

  @dbus.service.signal(dbus_interface=DBUSAPI_IFC, signature='b')
  def pause_toggled(self, new_state):
    pass

  @dbus.service.signal(dbus_interface=DBUSAPI_IFC, signature='ssussusss')
  def play(self, file, artist, track, title, album, length, art_path, year, genre):
    pass
      
  @dbus.service.signal(dbus_interface=DBUSAPI_IFC, signature='')
  def stopped(self):
    pass

  @dbus.service.signal(dbus_interface=DBUSAPI_IFC, signature='s')
  def playmode_changed(self, playmode):
    pass

  @dbus.service.signal(dbus_interface=DBUSAPI_IFC, signature='s')
  def state_changed(self, state):
    pass

  def update_play(self):
    file = manager.playlist.status()
    song = db.song_of_path(file)[0]

    if manager.nowplayingbuttonimage == 'album':
      art_path = song['art_path']
      if art_path == globals.UNKNOWNIMAGE: art_path = db.art_path_of_artist(song['artist_id'])
    else:
      art_path = db.art_path_of_artist(song['artist_id'])
    if art_path == globals.UNKNOWNIMAGE: art_path = ''
    
    genre = song['genre']
    if genre == None or genre == 'Unknown': genre=''
    
    try:
      track = int(song['track'])
    except:
      track = 0

    artist = ""
    title  = ""
    album  = ""
    year   = ""
    length = 0
    try:
      artist = str(song['artist'])
      title = str(song['title'])
      album = str(song['album'])
      year = str(song['year'])
      length = int(song['length'])
    except:
      pass

    self.play(file,artist,track,title,album,length,art_path,year,genre)
