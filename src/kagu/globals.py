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

import pygame,os,gc,fcntl,time,gtk
from pygame.locals import *


albumcache      = None
artistcache     = None
MAINFONTCOLOR   = None
MAINFONTBGCOLOR = None
initialized     = False
ISMAEMO         = False
osso_c          = None
font_o_cache    = {}
theme_tester    = False
UNKNOWNIMAGE    = "data/UNKNOWN_UNKNOWN.jpg"
DBVERSION       = 3
timer_time      = 0


def init_globals():
  global ISMAEMO, osso_c
  gc.disable() # don't let garbage collector ruin our frame rate
  #gc.set_debug(gc.DEBUG_LEAK)
  #
  # Init Pymp
  #
  HOME = os.path.expanduser("~/.kagu")

  if not os.access(HOME, os.F_OK | os.W_OK):
    os.mkdir(HOME)  #create prefs directory

  if os.name=="posix" and os.path.exists('/media/mmc1'): ISMAEMO=True
  if ISMAEMO:
    try:
      import osso
      osso_c = osso.Context("kagu", "1.0", False)
    except:
      print "could not initialize osso context"

def gprint_ret(text,font_size=False,fg_color=False,bg_color=None):
  global MAINFONTCOLOR
  global MAINFONTBGCOLOR
  global font_o_cache
  if not font_size: font_size = 36
  if not fg_color: fg_color = MAINFONTCOLOR
  #if not bg_color: bg_color = MAINFONTBGCOLOR
  if font_size not in font_o_cache:
    font_o_cache[font_size] = pygame.font.Font(None,font_size)
  font = font_o_cache[font_size]
  if bg_color: font_surf=font.render(text, True, fg_color, bg_color)
  else: font_surf=font.render(text, True, fg_color)
  return font_surf

def gprint(text,surface,point=(200,200),font_size=False,fg_color=False,bg_color=None):
  font_surf = gprint_ret(text,font_size,fg_color,bg_color)
  surface.blit(font_surf,point)


def get_path_list():
#  path_a = ['/media/mmc1/flac'] # disq-devel
  path_a = ['/media/mmc1','/media/mmc2','/media/mmc3','/home/user/MyDocs/.sounds','/Volumes/OSX/iTunes','/share/mp3/My Chemical Romance','/var/lib/mythtv/music']
  return path_a

def get_no_path_list():
  path_a = ['/usr', '/dev', '/proc', '/sys', '/media/mmc1/Navicore', '/media/mmc2/Navicore']
  return path_a

def calc_db_dir():
  return os.path.expanduser("~/.kagu/")

def format_time(seconds):
  secs=int(seconds)
  if secs>=3600:
    (h, ms) = divmod(secs, 3600)
    (m, s) = divmod(ms, 60)
    formatted_time   = "%2d:%02d:%02d" % (h, m, s,)
  else:
    formatted_time   = "%2d:%02d" % divmod(secs,60)
  return formatted_time

def blank_screen():
  global ISMAEMO
  try:
    if ISMAEMO:
      print "manually blanking screen"
      f = open("/dev/fb0", "w")
      # FBIOBLANK=0x4611, VESA_POWERDOWN=3 in <linux/fb.h>
      fcntl.ioctl(f, 0x4611, 3) 
      f.close()
    return ISMAEMO
  except:
    return False

def timer_init():
  global timer_time
  timer_time = time.time()

def timer_check(st):
  global timer_time
  ti = time.time()
  print st + " took:" + str(ti-timer_time)
  timer_time = ti

def infobanner(text):
  global osso_c

  if osso_c==None:
    print "skipped infobanner:",text
    return

  import osso  # osso_c would be None if ISMAEMO==False anyway
  sysnote = osso.SystemNote(osso_c)
  if sysnote == None:
    print "error creating infobanner:",text
    return
  sysnote.system_note_infoprint(text)
  print "infobanner:",text

#
#  Confirm action
#
def confirm_dlg(text, button=gtk.STOCK_OK):
    print "showing confirmation dialog"
    import gtk
    dialog = gtk.Dialog("Confirmation", None, gtk.DIALOG_MODAL, (button, gtk.RESPONSE_ACCEPT, gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT))
    dialog.set_default_response(gtk.RESPONSE_REJECT)
    label = gtk.Label("    "+text+"    ")
    dialog.vbox.pack_start(label, False, True, 15)
    dialog.vbox.show_all()
    resp = dialog.run()
    dialog.destroy()
    if resp == gtk.RESPONSE_REJECT:
      return(False)
    return(True)


if not initialized: init_globals()
