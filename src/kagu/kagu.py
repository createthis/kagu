#!/usr/bin/python
# -*- coding: utf-8 -*-
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

import sys,remote

if remote.remote(sys.argv): sys.exit(0)

import os, pygame, time, gc
from pygame.locals import *
import gtk
import globals


def main():
  theme_tester = False

  argc = len(sys.argv)
  if argc==2 and sys.argv[1]=="--theme-tester":
    theme_tester = True
    print "enabling theme tester mode"
  elif argc>1 or (argc==2 and (sys.argv[1]=="--help" or sys.argv[1]=="-h")):
    print "kagu [--theme-tester] [-remote commands]"
    return

  dbfile = os.path.join(globals.calc_db_dir(), 'kagu.db')
  dbexists = os.path.exists(dbfile)
  if (not dbexists) or (dbexists and os.path.getsize(dbfile)==0):
    print "kagu.db not found - launching scanner"
    sys.exit(21)

  from db      import db as db
  from manager import manager as manager
  from theme   import theme   as theme
  import widgets, views


  globals.theme_tester = theme_tester

  #
  # Start up the main logic object
  #
  manager.start()

  #
  # Event Loop
  #
  clock = pygame.time.Clock()
  idle_start = 0
  
  pygame.event.clear() # clear event queue

  while 1:
    clock.tick(30)

    events = pygame.event.get()
    if not events and manager.idle_seconds>5: time.sleep(0.1)
    if manager.is_extended_idle():
      print "idle"
      dummycount = 0
      while not events and manager.is_extended_idle():
        # this is an optimized event loop designed to:
        # 1.) service manager.player
        # 2.) check for new pygame events with low latency and
        #     low CPU because we are not redrawing the screen
        time.sleep(0.1)
        events = pygame.event.get()
        gtk.main_iteration(block=False)
        dummycount=dummycount+1
        if dummycount>20:
          manager.check_sleep_timer()
          dummycount=0
    if events: manager.wake_up()
    if manager.screen_status == "dimmed":
      events = []
      pygame.event.clear() # ignore taps on dimmed screen
    for event in events:
      if event.type == QUIT:
        manager.quit()
        return
      manager.handle_event(event)

    manager.update()

    # draw everything
    manager.clear()
    manager.draw()
    pygame.display.flip()
    gtk.main_iteration(block=False)


if __name__ == '__main__': main()
