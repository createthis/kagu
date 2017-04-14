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

import dbus, dbus.glib, dbus.service
import gobject, time
import baseplayer, globals, osso
from manager import manager as manager
import thread


OSSO_MEDIA_SERVER_PATH="/com/nokia/osso_media_server"
OSSO_MEDIA_SERVER_IFC="com.nokia.osso_media_server"
OSSO_MEDIA_SERVER_MUSIC_IFC="com.nokia.osso_media_server.music"

STATUS_TIMEOUT = 1000


class OSSOPlayer(baseplayer.BasePlayer):
  osso_rpc, bus, bus_iface, bus_obj, status_query = None, None, None, None, None

  def init_helper(self, *args):
    if self.bus == None:
      self.bus = dbus.SessionBus(private=True)
      self.bus_obj = self.bus.get_object(OSSO_MEDIA_SERVER_IFC, OSSO_MEDIA_SERVER_PATH)
      self.bus_iface = dbus.Interface(self.bus_obj, OSSO_MEDIA_SERVER_MUSIC_IFC)
      self.bus_iface.connect_to_signal("state_changed", self.on_state)
      self.bus_iface.connect_to_signal("end_of_stream", self.on_eos)

  def __init__(self, threads=False):
    self.threads = threads
    baseplayer.BasePlayer.__init__(self)
    
  def _extended_init(self):
    if self.osso_rpc == None: self.osso_rpc = osso.Rpc(globals.osso_c)
    if self.threads:
      thread.start_new_thread(self.init_helper, (None,))
    else:
      self.init_helper(None)

  def on_state(self,arg=None):
    if not isinstance(manager.player, OSSOPlayer): return
    state = "%s" % (arg,)
    
    print "got state: %s (old self.paused=%s)" % (state,self.paused,)

    # dupe signal checks can't be done using self.paused because baseplayer/manager modifies it
    if state == "playing":
      self._update_volume() # usually voip and other apps change the volume
      self.start_status_query()
      self.paused = False
      manager.play_button.update()
    elif (state == "paused" or state == "stopped"):
      self.stop_status_query()
      self.paused = True
      manager.play_button.update()

  def on_eos(self,arg=None):
    file = "%s" % (arg,)
    print "EOS for %s" % (file,)
    self.stop_status_query()
    if manager.playlist.continuous:  #play next target
      manager.playlist.next(None, None)

  def send_cmd(self, method, args=()):
    self.osso_rpc.rpc_run(
        OSSO_MEDIA_SERVER_IFC,
        OSSO_MEDIA_SERVER_PATH,
        OSSO_MEDIA_SERVER_MUSIC_IFC,
        method,
        args,
        wait_reply = False)

  def _update_play(self):
    print "update_play: %s" % (self.target,)

    self._update_volume()

    # the next _interrupt() call will be caused by the following cmd so set a flag to ignore it
    self.ignore_next_interruption_till = time.time() + 3 # only valid for 3 seconds
    self.send_cmd("play_media", (str("file://"+self.target),) )

  def _update_volume(self):
    self.send_cmd("set_volume", (float(float(self.volume) / 100.0),) )
    
  def _update_pause(self):
    self.send_cmd("pause")
    # during the unpause something keeps changing the volume to 0.5, update it during the unpause
    # NOTE: A reboot fixed this for me. Tried various rtcomm and Skype calls, it's not that.
    # It's the Internet radio. Once you play/stop on the desktop applet, it messes with the
    # mediaserver volume on each play request. Need to test more and report/whine -disq

#    if self.paused: self._update_volume() # FIXME:not fast enough, unnecessary


  def _seek(self, amount, mode=0):
    # make sure self.seconds and self.length are up to date
    if not self.status_query:
      self._query_status()

    if not self.bus_obj:
      print "ossoplayer: ignored seek: bus object not ready"
      return

    seekmsec = self.calc_seekmsec(amount, mode)
    if seekmsec == None:
        return

    # The first parameter seems to be dummy, valid values are 0 thru 2. Probably an unimplemented
    # "whence" flag (refer to the fseek() manpage for explanation)
    try:
      self.bus_obj.seek(dbus.Int32(0), dbus.Int32(seekmsec), dbus_interface=OSSO_MEDIA_SERVER_MUSIC_IFC)
    except:
      print "dbus exception during ossoplayer.seek()"

  def stop(self):
    self.send_cmd("stop")

  def calc_percent(self):
    if not self.length:
      self.percent = 0
    elif not self.seconds:
      self.percent = 0
    else:
      self.percent = self.seconds * 100 / self.length

  def _query_status(self):
    # rpc_run_async segfaults, rpc_run won't return lists
    try:
      (cur, tot) = self.bus_obj.get_position(dbus_interface=OSSO_MEDIA_SERVER_MUSIC_IFC)
      self.seconds = cur / 1000
      self.length = tot / 1000
    except:
      self.length = 0
      # ogg playback won't return total length
      # FIXME: handle this better, make a seperate code block for application/ogg
      try: 
        cur = self.bus_obj.get_position(dbus_interface=OSSO_MEDIA_SERVER_MUSIC_IFC)
        self.seconds = cur / 1000
      except:
        self.seconds = 0

    self.calc_percent()
    return True

  def stop_status_query(self):
    if self.status_query:
      gobject.source_remove(self.status_query)
    self.status_query = 0

  def start_status_query(self):
    if not self.status_query and not self.powersave:
      self._query_status() # don't wait STATUS_TIMEOUT msecs for the update
      self.status_query = gobject.timeout_add(STATUS_TIMEOUT, self._query_status)

  def close(self):
    self.stop_status_query()
    self.stop()

  def _update_powersave(self):
    if self.powersave:
      if self.status_query:
        self.stop_status_query()
    else:
      if self.paused == False:
        self.start_status_query()
        
