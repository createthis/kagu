#!/usr/bin/env python

# NOTE: This module is not Win32 compatible as it uses fcntl and nonblocking pipes. mplayer isn't common on Win32 anyway.

import sys, os, fcntl, gobject, time
import baseplayer
import a2dpd
from manager import manager as manager


STATUS_TIMEOUT = 1000
MPLAYER = os.path.expanduser("~/.mplayer")
if not os.access(MPLAYER, os.F_OK | os.W_OK):
  os.mkdir(MPLAYER)  #create mplayer directory

#
#  Provides simple piped I/O to an mplayer process.
#
class Mplayer(baseplayer.BasePlayer):
  
  mplayerIn, mplayerOut, a2dpd = None, None, None
  eofHandler, statusQuery, lengthQuery = 0, 0, 0
  ext_d = {'.mp3':'ffmp3','.wma':'ffwmav2','.aac':'faad','.m4p':'faad','.m4a':'faad','.mp4':'faad'}
  
  #
  #   Plays the specified target.
  #
  def _update_play(self):
    print "mplayer: play,a2dpd=%s,target=%s" % (self.a2dpd,self.target)
    self.ignore_next_interruption_till = time.time() + 3 # only valid for 3 seconds
    if self.mplayerOut: # do not start a new mplayer instance if one is already running
      print "loadfile \"" + self.target + "\" 0"
      self.cmd("loadfile \"" + self.target + "\" 0")
      return
   
    if self.a2dpd:
      self.a2dpd.start()
      (rootfn,ext) = os.path.splitext(self.target)
      if self.ext_d.has_key(ext.lower()):
        opts = "-ac %s -ao alsa:device=a2dpd2 " % (self.ext_d[ext.lower()],)
      else: return False # unsupported file format
    else: opts = ""

    mpc = "mplayer " + opts + "-slave -quiet -forceidx \"" + self.target + "\" 2>/dev/null"
    
    self.mplayerIn, self.mplayerOut = os.popen2(mpc)  #open pipe
    fcntl.fcntl(self.mplayerOut, fcntl.F_SETFL, os.O_NONBLOCK)
    
    self.startEofHandler()
    self.startLengthQuery()
    self.startStatusQuery()
    
  def restart(self):
    print "mplayer: restart request,self.mplayerOut=%s,a2dpd=%s" % (self.mplayerOut,self.a2dpd)
    if self.mplayerOut:
      print "restarting"
      ''' save current state '''
      self._query_status()
      percent = self.percent
      seconds = self.seconds
      target  = self.target
      paused  = self.paused
      self.close()
      ''' restore state '''
      self.play(target)
      time.sleep(0.5)
      self.seek(seconds,2,True)
      if paused: self.pause()

  def get_a2dpd(self):
    return self.a2dpd

  def set_a2dpd(self,on):
    print "mplayer: switching a2dpd: %s" % (on,)
    if on and not self.a2dpd:
      self.a2dpd = a2dpd.A2DPD()
      self.a2dpd.start()
      self.restart()
    elif not on and self.a2dpd:
      a2dpd_tmp = self.a2dpd
      self.a2dpd = None
      self.restart() # restart mplayer before terminating a2dpd to avoid alsa sound card issues
      a2dpd_tmp.stop()
    else: print "no change"

  def _update_volume(self):
    print "volume=%d" % (self.volume,)
    self.cmd("volume " + str(self.volume) + " 1")

  #  Issues command to mplayer.
  #
  def cmd(self, command):
    if not self.mplayerIn: return
    
    try:
      self.mplayerIn.write(command + "\n")
      self.mplayerIn.flush()  #flush pipe
    except StandardError:
      return
    
  #
  #  Toggles pausing of the current mplayer job and status query.
  #
  def _update_pause(self):
    print "mplayer: pause=%s" % (self.paused,)
    if not self.mplayerIn: return
      
    if self.paused: self.stopStatusQuery()
    else: self.startStatusQuery()
      
    self.cmd("pause")

  #
  #  Seeks the amount using the specified mode.  See mplayer docs.
  #
  def _seek(self, amount, mode=0):
    print "mplayer: seek: %s" % (str(amount),)
    self.cmd("seek " + str(amount) + " " + str(mode))
    self._query_status()
  
  #
  #  Cleanly closes any IPC resources to mplayer.
  #
  def close(self):
    print "mplayer: close"
    
    if self.paused:  #untoggle pause to cleanly quit
      self.pause()

    if self.a2dpd: self.a2dpd.stop()
    self.stopStatusQuery()  #cancel query
    self.stopEofHandler()  #cancel eof monitor
    
    self.cmd("quit")  #ask mplayer to quit
    
    try:      
      self.mplayerIn.close()   #close pipes
      self.mplayerOut.close()
    except StandardError:
      pass
      
    self.mplayerIn, self.mplayerOut = None, None
    self.percent = 0
    self.seconds = 0.0
    self.target  = None
    
  #
  #  Triggered when mplayer's stdout reaches EOF.
  #
  def handleEof(self, source, condition):
    print "mplayer: handling EOF!"
    
    self.stopStatusQuery()  #cancel query
    
    self.mplayerIn, self.mplayerOut = None, None
    
    if manager.playlist.continuous:  #play next target
      manager.playlist.next(None, None)
      
    return False
    
  #
  #  Queries mplayer's playback status and upates the progress bar.
  #
  def _query_status(self):
    
    self.cmd("get_percent_pos")  #submit status query
    self.cmd("get_time_pos")
    
    time.sleep(0.05)  #allow time for output
    
    line, percent, seconds = None, -1, -1
    
    while True:
      try:  #attempt to fetch last line of output
        line = self.mplayerOut.readline()
      except StandardError:
        break
        
      if not line: break
      
      if line.startswith("ANS_PERCENT_POSITION"):
        percent = int(line.replace("ANS_PERCENT_POSITION=", ""))
      
      if line.startswith("ANS_TIME_POSITION"):
        seconds = float(line.replace("ANS_TIME_POSITION=", ""))

    if seconds != -1: self.seconds = seconds
    if percent != -1: self.percent = percent
    return True
    
  def queryLength(self):
    self.cmd("get_time_length")
    
    time.sleep(0.05)  #allow time for output
    
    line, length = None, -1
    
    while True:
      try:  #attempt to fetch last line of output
        line = self.mplayerOut.readline()
      except StandardError:
        break
        
      if not line: break
      
      if line.startswith("ANS_LENGTH"):
        length = float(line.replace("ANS_LENGTH=", ""))

    if length != -1:
      self.length = length
      return False # terminates the loop. We only need to query length once per song.
    return True
    
  #
  #  Inserts the status query monitor.
  #
  def startStatusQuery(self):
    self.statusQuery = gobject.timeout_add(STATUS_TIMEOUT, self._query_status)

  def startLengthQuery(self):
    if self.lengthQuery: gobject.source_remove(self.lengthQuery)
    self.lengthQuery = gobject.timeout_add(STATUS_TIMEOUT, self.queryLength)

  #
  #  Removes the status query monitor.
  #
  def stopStatusQuery(self):
    if self.statusQuery:
      gobject.source_remove(self.statusQuery)
    self.statusQuery = 0
    
  #
  #  Inserts the EOF monitor.
  #
  def startEofHandler(self):
    self.eofHandler = gobject.io_add_watch(self.mplayerOut, gobject.IO_HUP, self.handleEof)
  
  #
  #  Removes the EOF monitor.
  #
  def stopEofHandler(self):
    if self.eofHandler:
      gobject.source_remove(self.eofHandler)
    self.eofHandler = 0
    
#End of file
