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


import re,os
from db      import db      as db


FN = os.path.expanduser("~/.kagu/playlist.m3u")


class M3U():
  def save(self, list, filename=FN):
    try:
      f = open(filename, "w")
    except StandardError:
      return False
    
    for target in list:  #append each target to file
      f.write(target + "\n")
    
    f.close()
    return True

  def is_not_comment(self,line):
    return not re.match(r'^#',line)

  def chomp(self,line):
    return line.rstrip('\n').rstrip('\r')
  
  def load(self, filename=FN):
    try:
      f = open(filename, "r")
    except StandardError:
      return False
    
    list = f.readlines()
    list = filter(self.is_not_comment,list)
    safelist = []
    path = os.path.dirname(filename)

    for item in list:
      try:
        item = self.chomp(item)
        if item.find('/')!=0:
          item=path+'/'+item
        safelist.append(item)
      except:
        print "error reading playlist item",item
      
    f.close()
    return safelist

  def songs_of_path(self,path):
    list = self.load(filename=path)
    path = os.path.dirname(path)
    safelist = []
    for s in list:
      rows = db.song_of_path(s)
      if (len(rows)>0):
        safelist.append(rows[0])
    return safelist

m3u = M3U()
