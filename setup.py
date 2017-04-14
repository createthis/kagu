#!/usr/bin/env python2.5
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
import glob
import os, sys
from stat import *
from distutils.core import setup

# files to install
inst_icons_26   = [ 'data/icons/26x26/kagu.png' ]
inst_icons_40   = [ 'data/icons/40x40/kagu.png' ]
inst_icons_64   = [ 'data/icons/64x64/kagu.png' ]
inst_dbus          = [ 'data/kagu.service', 'data/kaguscanner.service' ]
inst_desktop       = [ 'data/kagu.desktop', 'data/kaguscanner.desktop' ]


#hack
def build_list(subdir):
  list = []
  files = []
  for f in os.listdir('src/kagu'+subdir):
    mode = os.stat('src/kagu'+subdir+'/'+f) [ST_MODE]
    if (S_ISDIR(mode)):
      if (f == ".svn"): continue
      list = list + build_list(subdir+'/'+f)
    else:
      files.append('src/kagu'+subdir+'/'+f)

  list.append( ('lib/kagu'+subdir, files ) )
  return list


lib_files = build_list("")

data_files = [
  ('share/icons/hicolor/26x26/hildon', inst_icons_26),
  ('share/icons/hicolor/40x40/hildon', inst_icons_40),
  ('share/icons/hicolor/64x64/hildon', inst_icons_64),
  ('share/applications/hildon', inst_desktop),
  ('share/dbus-1/services',   inst_dbus),
]

setup(
  name         = 'kagu',
  version      = '1.0',
#  package_dir  = { '':'src' },
#  packages     = [ 'kagu' ],
  description  = 'media player',
  author       = 'Jesse Guardiani',
  author_email = 'jesse@guardiani.us',
  url          = 'http://kagumedia.com/',
  scripts      = [ 'bin/kagu', 'bin/kagu-scanner' ],
  data_files   = data_files + lib_files
)

