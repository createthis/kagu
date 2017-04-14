#!/usr/bin/env python

import sys, os, fcntl, gobject, time, signal

STATUS_TIMEOUT = 1000

#
#  Provides simple start/stop of an a2dpd process and remote management using a2dpd_ctrl.
#
class A2DPD:
 
  def __init__(self):
    self.running = False
  
  def start(self):
    if not self.running:
      print "starting a2dpd"
      self.running = os.spawnlp(os.P_NOWAIT,'a2dpd')
    os.spawnlp(os.P_NOWAIT,'a2dpd_ctl Startup')

  def stop(self):
    if not self.running: return
    print "killing a2dpd %d" % (self.running,)
    os.spawnlp(os.P_NOWAIT,'a2dpd_ctl Exit')
    os.kill(self.running,signal.SIGKILL) # make sure the bloody buggy thing dies a hard death
    os.waitpid(self.running,0)
    self.running = False
    

    
#End of file
