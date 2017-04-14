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
import time, os, globals


class BasePlayer:
  ''' This class defines the public API for every player derived from it 
  and also sets some sane defaults and basic functionality. '''
  paused = True
  volume = 100
  target = None
  interrupted, ignore_next_interruption_till = False, 0  

  def __init__(self):
    self.percent   = 0
    self.seconds   = 0.0
    self.length    = 0.0
    self.powersave = False
    self._extended_init()
    self.set_volume(manager.prefs.getInt("volume"),show_volumeview=False)

  def _extended_init(self):
    ''' do init stuff '''
    ''' override me '''

  def _update_volume(self):
    ''' set player volume '''
    ''' override me '''

  def _update_pause(self):
    ''' set paused/playing '''
    ''' override me '''

  def _update_play(self):
    ''' set play target '''
    ''' override me '''

  def _update_powersave(self):
    ''' set powersave state on/off '''
    ''' override me '''

  ''' This method should be overridden to hook VOIP interruptions '''
  def _interrupt(self, begin):
    ''' override me if needed '''
    if self.ignore_next_interruption_till > 0 and self.ignore_next_interruption_till >= time.time():
      print "IGNORED interrupt: %s" % (begin,)
    else:
      self.ignore_next_interruption_till = 0
      print "got interrupt: %s" % (begin,)
      self.set_pause(True)

  def _seek(self, amount, mode=0):
    ''' seek '''
    ''' override me '''

  def _query_status(self):
    ''' override me '''

  def play(self, target):
    ''' play a file '''
    if not os.path.exists(target):
      globals.infobanner("File not found")
      return
    self.length  = 0.0
    self.percent = 0
    self.seconds = 0.0
    self.target  = target
    self.paused  = False
    self._update_play()

  def volume_increase(self,blind=False):
    self.volume += 10
    if self.volume > 100: self.volume = 100
    self._update_volume()
    if manager.dbusapi: manager.dbusapi.volume_changed(self.volume)
    if not blind: manager.show_volume()

  def volume_decrease(self,blind=False):
    self.volume -= 10
    if self.volume < 0: self.volume = 0
    self._update_volume()
    if manager.dbusapi: manager.dbusapi.volume_changed(self.volume)
    if not blind: manager.show_volume()
    
  def set_volume(self,new_volume,show_volumeview=True):
    if new_volume < 0: new_volume = 0
    if new_volume > 100: new_volume = 100
    self.volume = new_volume
    self._update_volume()
    if manager.dbusapi: manager.dbusapi.volume_changed(self.volume)
    if show_volumeview: manager.show_volume()
    
  def pause(self, is_paused = None):
    if is_paused == None:
      if self.paused: self.paused = False
      else: self.paused = True
    else: self.paused = is_paused
    if manager.dbusapi: manager.dbusapi.pause_toggled(self.paused)
    self._update_pause()
    manager.play_button.update()

  def set_pause(self, state):
    ''' state: True=Pause False=Unpause '''

    if state==False and manager.playlist.current==None:
      print "set_pause: initiating play"
      manager.playlist.play(0)
      return

    if self.paused!=state:
      print "set_pause: toggling pause, req =",state
      self.pause()
    else:
      print "set_pause: skipped pause, req =",state
    
  def seek(self, amount, mode=0, same_position=False):
    if not same_position and manager.scrobbler: manager.scrobbler.stop()
    self._seek(amount, mode)

  def set_powersave(self, is_powersave):
    if self.powersave == is_powersave: return # only call for changes in state
    self.powersave = is_powersave
    print "powersave = %s" % (self.powersave,)
    self._update_powersave()
  
  def calc_seekmsec(self, amount, mode):
    if mode == 0:
      seekmsec = int((self.seconds + amount) * 1000)
      if seekmsec<0: seekmsec=0
      elif seekmsec>self.length*1000:
        print "player: ignored seek(0): overflow"
        return None
    elif mode == 1:
      if not self.length:
        print "player: ignored seek(1): length unknown"
        return None
      seekmsec = int(float(float(amount) / 100.0) * self.length * 1000)
    elif mode == 2:
      seekmsec=int(amount*1000)
      if seekmsec>self.length*1000:
        print "player: ignored seek(2): overflow"
        return None
    else:
      print "player: ignored seek: unknown mode"
      return None

    print "player: seek to %i msec" % (seekmsec,)
    return seekmsec

  def close(self):
    ''' close '''
