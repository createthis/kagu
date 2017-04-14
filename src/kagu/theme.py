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

import globals, pygame
from pygame.locals import *
from db import db as db


class Theme():
  def set_theme(self,name,convert=True):
    self.name = name
    self.path = db.get_theme_path(self.name)
    self.surface = pygame.image.load(self.path)
    if convert: self.surface = self.surface.convert()
    self.surface.set_alpha(None)
    self.colorkey = self.surface.get_at((
        self.surface.get_rect().right  - 1,
        self.surface.get_rect().bottom - 1))
    self.surface.set_colorkey(self.colorkey,RLEACCEL)
    self.image_cache = {}
    self.bar_color_sel = self.surface.get_at(self.get_rect('volume_bar_sel').center)
    self.bar_color     = self.surface.get_at(self.get_rect('volume_bar').center)

  def get_rect(self,sprite_name):
    row = db.get_theme_sprite(self.name,sprite_name)
    return Rect(row['x'],row['y'],row['w'],row['h'])

  def blit(self,image,point,sprite_name):
    return image.blit(self.surface,point,self.get_rect(sprite_name))

  def get_image(self,sprite_name):
    try:
      copy = self.image_cache[sprite_name].copy()
    except KeyError:
      rect = self.get_rect(sprite_name)
      image = self.get_surface((rect.width,rect.height))
      image.blit(self.surface,(0,0),rect)
      self.image_cache[sprite_name] = image
      copy = image.copy()
    return copy

  def get_surface(self,dimensions):
    image = pygame.Surface(dimensions,0,self.surface)
    image.fill(self.colorkey)
    image.set_colorkey(self.colorkey,RLEACCEL)
    return image

theme = Theme()
