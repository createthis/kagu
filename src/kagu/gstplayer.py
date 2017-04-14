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


import gst, pygst, gobject, time
import baseplayer
from manager import manager as manager


STATUS_TIMEOUT = 1000


class GSTPlayer(baseplayer.BasePlayer):
  player, source, sink, status_query, length_query, bus = None, None, None, None, None, None
  last_seconds, last_action_seconds = 0,0

  def _extended_init(self):
    if self.player != None:
            self.player.set_state(gst.STATE_NULL)
            self.bus = None
    try:
        self.player = gst.parse_launch( "gnomevfssrc name=source ! id3demux name=id3 ! dspmp3sink name=sink" )
    except:
        self.player = gst.parse_launch( "gnomevfssrc name=source ! id3lib name=id3 ! dspmp3sink name=sink" )

    self.source = self.player.get_by_name( "source" )
    self.sink   = self.player.get_by_name( "sink"   )

  def _update_play(self):
    print "update_play: %s" % (self.target,)
    self.stop_status_query()
    try:
      self._extended_init()
      self._update_volume()
      self.source.set_property("location", self.target)
      self.player.set_state(gst.STATE_PLAYING)

    except:
      print "CANNOT PLAY MUSIC"
    self.start_length_query()
    self.start_status_query()
    self.start_eos_watcher()

  def _update_volume(self):
    self.sink.set_property('volume', self.volume*65535/100)
    
  def _update_pause(self):
    if self.paused:
        self.stop_status_query()
        self.player.set_state(gst.STATE_PAUSED)
    else:
        self.player.set_state(gst.STATE_PLAYING)
        self.start_status_query()
    self.last_action_seconds = self.seconds
    
  def _seek(self, amount, mode=0):
    seekmsec = self.calc_seekmsec(amount, mode)
    if seekmsec == None:
        return

    if self.player.get_state() != gst.STATE_PAUSED:
      self.player.set_state(gst.STATE_PAUSED)

    event = gst.event_new_seek(1.0, gst.FORMAT_TIME,
      gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
      gst.SEEK_TYPE_SET, gst.MSECOND*seekmsec,
      gst.SEEK_TYPE_NONE, 0)

    if self.player.send_event(event):
      print "setting new stream time to 0"
      self.player.set_new_stream_time(0L)
    else:
      print "seek to %r failed" % location
    self.player.set_state(gst.STATE_PLAYING)

  def get_length(self):
    value,position = 0,0
    try: position, format = self.player.query_duration(gst.FORMAT_TIME)
    except: position = gst.CLOCK_TIME_NONE
    if position != gst.CLOCK_TIME_NONE: value=position
    self.length = int(value / gst.SECOND)
    if self.length: return False
    else: return True

  def get_seconds(self):
    value,position = 0,0
    try: position, format = self.player.query_position(gst.FORMAT_TIME)
    except: position = gst.CLOCK_TIME_NONE
    if position != gst.CLOCK_TIME_NONE: value=position
    self.last_seconds = self.seconds
    self.seconds = int(value / gst.SECOND)
#    if self.seconds < 0:
#         print "GST STATE:",repr(self.player.get_state())

  def calc_percent(self):
    if not self.length:
      self.percent = 0
    elif not self.seconds:
      self.percent = 0
    else:
      self.percent = self.seconds * 100 / self.length

  def _query_status(self):
    self.get_seconds()
    self.calc_percent()
    return True

  def on_message(self, bus, message):
    print "GST: got message!",repr(message.type)
    t = message.type
    if t == gst.MESSAGE_ERROR:
      err, debug = message.parse_error()
      print "Error: %s" % err, debug
      self.on_eos()
    elif t == gst.MESSAGE_EOS:
      self.on_eos()

  def on_eos(self):
    print "GST: ON EOS!"
    self.seconds = 0
    self.stop_status_query()
    self.length_query = None
    if manager.playlist.continuous:  #play next target
      manager.playlist.next(None, None)

  def start_status_query(self):
    if not self.status_query and not self.powersave:
        self.status_query = gobject.timeout_add(STATUS_TIMEOUT, self._query_status)

  def stop_status_query(self):
    if self.status_query:
      gobject.source_remove(self.status_query)
    self.status_query = 0

  def start_length_query(self):
    if self.length_query: gobject.source_remove(self.length_query)
    self.length_query = gobject.timeout_add(STATUS_TIMEOUT, self.get_length)

  def start_eos_watcher(self):
    if not self.bus:
      self.bus = self.player.get_bus()
      self.bus.add_signal_watch()
      self.bus.connect('message', self.on_message)
 
  def close(self):
    self.player.set_state(gst.STATE_NULL)

  def _update_powersave(self):
    if self.powersave:
      if self.status_query:
        self.stop_status_query()
    else:
      if self.paused == False:
        self.start_status_query()
