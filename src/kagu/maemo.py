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

from manager import manager as manager
import ossoplayer
import dbus
import dbus.glib
import dbus.service
import gobject, time, thread, os

# BME = Battery Monitor Events?
BME_REQ_PATH="/com/nokia/bme/request"
BME_REQ_IFC ="com.nokia.bme.request"


class BMERequest(dbus.service.Object):
    def __init__(self, bus_name, object_path=BME_REQ_PATH):
        dbus.service.Object.__init__(self, bus_name, object_path)

    @dbus.service.signal(BME_REQ_IFC)
    def status_info_req(self):
        print "sent"


class BatteryMonitor:
  def __init__(self):
    self.bus = dbus.SystemBus(private=True)
    self.bus.add_signal_receiver(self.handle_charging_off,"charger_charging_off")
    self.bus.add_signal_receiver(self.handle_charging_on ,"charger_charging_on" )
    name = dbus.service.BusName(BME_REQ_IFC, bus=self.bus)
    e = BMERequest(name)
    e.status_info_req()

  def handle_charging_on(self,sender=None):
    print "charging"
    manager.on_battery = False
    manager.update_powersave()

  def handle_charging_off(self,sender=None):
    print "on_battery"
    manager.on_battery = True
    manager.update_powersave()


class ScreenMonitor:
  def __init__(self):
    self.bus = dbus.SystemBus(private=True)
    obj = self.bus.get_object('com.nokia.mce', '/com/nokia/mce/signal')
    iface = dbus.Interface(obj, 'com.nokia.mce.signal')
    iface.connect_to_signal("display_status_ind", self.handler)

  def handler(self,sender=None):
    status = "%s" % (sender,)
    print "screen is %s" % (status,)
    manager.set_screen_status(status)
    manager.update_powersave()


class HeadsetButtonMonitor:
  def __init__(self):
    try:
      self.lastpress = 0
      self.bus = dbus.SystemBus()
      obj = self.bus.get_object('org.freedesktop.Hal', '/org/freedesktop/Hal/devices/platform_retu_headset_logicaldev_input')
      iface = dbus.Interface(obj, 'org.freedesktop.Hal.Device')
      iface.connect_to_signal("Condition", self.handler)
    except:
      print "Could not connect to HAL service, headsetbutton monitor disabled"

  def handler(self,arg1,arg2):
    if (arg1 != "ButtonPressed") or (arg2 != "phone"):
      return

    print "HeadsetButtonMonitor: got headset switch"
    import globals
    if manager.player!=None:
      if self.lastpress + 1.5 >= time.time():
        globals.infobanner("Headset switch: Next") # check screen visibility before this?
        manager.wake_up(blind_action=True)
        manager.next_track()
      else:
        globals.infobanner("Headset switch: Play/Pause") # check screen visibility before this?
        manager.wake_up(blind_action=True)
        manager.player.set_pause(not manager.player.paused)

      self.lastpress = time.time()


class OSSOMediaMonitor:
  bus, callback = None, None

  def __init__(self):
    if self.bus == None:
      self.bus = dbus.SessionBus(private=True)
      self.bus.add_signal_receiver(self.on_state, "Notify")

  def on_state(self, arg1, arg2, arg3):
    if (arg1 != "com.osso.Playback") or (arg2 != "State"):
      return

    # the order of the state changes are inconsistent. sometimes they go Stop,Play,Stop,Play,
    # sometimes Stop,Play,Play,Stop etc. It messes up the logic.

    # Looks like this signal is generated from libplayback-1-0, and seems like osso-hss-control
    # somehow utilizes it. Seems like there are playback states/classes "VoIP", "Media", "Background"
    # and apps set theirs accordingly. Couldn't find a way though. Maybe I'm just hallucinating.
    
    # Maybe the reason we're getting double play/stop messages is having two seperate services
    # (osso-media-server and the voip app) using the same subsystem?

    # update -- now we got info on this: http://www.gossamer-threads.com/lists/maemo/developers/25492
    # i'm just keeping it simple. if something happens, pause the music to be safe.

    ti = int(time.time())
    print "got com.osso.Playback state: %s time=%i" % (arg3,ti,)

    if (arg3 == "Play"):
        manager.player._interrupt(True)
    elif (arg3 == "Stop"):
        manager.player._interrupt(False)

class HeadphonesMonitor:
  watchid = None
  status  = ""

  # Possible status files, and the condition to watch for each
  possible_status_files = {'/sys/devices/platform/gpio-switch/headphone/state':gobject.IO_PRI, '/sys/devices/platform/gpio-switch/headphone/connection_switch':(gobject.IO_PRI|gobject.IO_IN)}
  status_file = ''

  def __init__(self):
    # Detect the headphone connectivity status file
    for sf in self.possible_status_files.keys():
      if os.path.exists(sf):
        self.status_file = sf
        break

    if '' == self.status_file:
      # Couldn't find a status file
      # This should only happen on a non-maemo OS, or if something's seriously wrong
      print 'Unable to find headphone status indicator'
    else:
      self.handler(None, None) # initialize self.status
      self.watchid = gobject.io_add_watch(file(self.status_file, 'r'), self.possible_status_files[self.status_file], self.handler, priority=gobject.PRIORITY_DEFAULT_IDLE)

  def handler(self, source, condition):
    if not manager.get_headphone_sense(): return True
#    print "headphones handler called!"

    if source:
      source.readlines() # flush the buffer. reading from this somehow doesn't work correctly

    f = open(self.status_file, "r")
    state = f.readline().rstrip("\n").rstrip("\r") # read from a fresh fd
    f.close()

    if state != self.status and self.status!="":
      print "headphones:",state
      if state == "disconnected":
        if manager.player!=None: manager.player.set_pause(True)
      elif state == "connected":
        if manager.player!=None: manager.player.set_pause(False)

    self.status=state
    return True


def maemo_helper(*args):
  batterymon = BatteryMonitor()
  screenmon  = ScreenMonitor()
  ossomediamon  = OSSOMediaMonitor()
  hpmon  = HeadphonesMonitor()
  hsmon  = HeadsetButtonMonitor()

thread.start_new_thread(maemo_helper, (None,))
