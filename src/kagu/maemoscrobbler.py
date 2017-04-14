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


import osso
import globals,playlist
from db import db as db
from manager import manager as manager


class MaemoScrobbler():
  def __init__(self):
    self.osso_rpc = osso.Rpc(globals.osso_c)
    self.playing  = False

  def _get_rpc_args(self):
    song = db.song_of_path(manager.playlist.status())[0]
    if (song['flags']&1) > 0: return None
    
    rpc_args = (
        str(song['artist']),
        str(song['title']),
        str(song['album']),
        int(song['length']),
        int(0)) # FIXME: This field (position) should be pulled dynamically from playlist eventually
    return rpc_args

  def play(self):
    if self.playing: self.stop()
    
    rpcargs = self._get_rpc_args()
    if rpcargs == None:
      print "skipped MaemoScrobbler"
      return

    print "MaemoScrobbler.play()"
    
    self.osso_rpc.rpc_run(
        "com.nokia.songlistend",
        "/com/nokia/songlistend",
        "com.nokia.songlistend",
        "playing",
        rpcargs,
        wait_reply = False)
    self.playing = True


  def stop(self):
    print "MaemoScrobbler.stop()"
    self.osso_rpc.rpc_run(
        "com.nokia.songlistend",
        "/com/nokia/songlistend",
        "com.nokia.songlistend",
        "stopped",
        wait_reply = False)
    self.playing = False

