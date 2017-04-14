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

import pygame, time, gc
from pygame.locals import *
import globals
from db      import db      as db
from theme   import theme   as theme
from manager import manager as manager


class BaseWidget(pygame.sprite.Sprite):
  def __init__(self):
    pygame.sprite.Sprite.__init__(self) # call Sprite initializer
    self.image = None
    self.rect  = None
    self.visible = True

  def handle_event(self,event):
    ''' override me '''
    return False

  def is_idle(self):
    ''' override me '''
    return 1

  def set_selected(self,selected):
    if selected != self.selected: # ignore no change
      self.selected = selected

  def set_focus(self,focus):
    ''' override me '''

  def update(self):
    ''' override me '''

  def draw(self,surface):
    if self.visible:
      surface.blit(self.image,self.rect)

  def close(self):
    ''' override me '''


class Button(BaseWidget):
#
# we could also add a is_escape=False for albumbuttons etc below, which would then binds to the esc key
# but is it the right approach? -disq
#
  def __init__(self,image,onclick_cb,is_default=False,repeat=False):
    BaseWidget.__init__(self)
    self.image = image
    self.rect  = self.image.get_rect()
    self.onclick_cb = onclick_cb
    self.mousedown = False
    self.mouseup_timeout_start = None
    self.is_default = is_default
    self.ignore_next_mouseup = False
    self.repeat = repeat
    self.last_callback = None
    self.repeat_frequency = 0.10 # in seconds

  def handle_event(self,event):
    handled = False
    if not self.visible: return handled
    if event.type == MOUSEBUTTONDOWN and self.rect.collidepoint(pygame.mouse.get_pos()):
      # only register a button click if there has been some time since last button click. This prevents false clicks.
      if not self.mouseup_timeout_start or time.time()-self.mouseup_timeout_start > 0:
        self.mousedown = True
        self.mouseup_timeout_start = None
        self.ignore_next_mouseup = False
    if self.mousedown: handled = True
    if self.mousedown and event.type == MOUSEBUTTONUP:
      self.mousedown = False
      self.mouseup_timeout_start = time.time()
      if self.rect.collidepoint(pygame.mouse.get_pos()):
        if not self.ignore_next_mouseup:
          self.do_callback()
        else:
          self.ignore_next_mouseup = False
    if self.is_default and event.type == KEYDOWN and event.key == K_RETURN and (event.mod&128)==0:
        self.do_callback()
        handled = True
    return handled
        
  def set_ignore_next_mouseup(self, state=False):
    self.ignore_next_mouseup=state

  def do_callback(self):
    manager.loading_sign()
    self.last_callback = time.time()
    self.onclick_cb()

  def update(self):
    if self.repeat and self.mousedown and ( \
        not self.last_callback or \
        time.time() - self.last_callback > self.repeat_frequency):
      self.do_callback()
      self.ignore_next_mouseup = True
    
  def is_pressed(self):
    return self.mousedown

  def set_pressed(self, state):
    self.mousedown = state


class PlayBackButton(Button):
  ''' like a Button, but only visible when playlist is not empty '''

  def handle_event(self,event):
    if manager.playlist.is_empty() and self.mousedown==True:
      self.mousedown=self.ignore_next_mouseup=False
    if manager.playlist.is_empty(): return False
    return Button.handle_event(self,event)

  def draw(self,surface):
    if manager.playlist.is_empty(): return
    Button.draw(self,surface)


class ScrollWidget(BaseWidget):
  ''' This widget wraps sprites with equal heights and 
  presents the user with an interface for scrolling and
  selecting these sprites'''
  def __init__(self,rect,selected_cb,list,generator_cb,reset_timeout_cb=None,wrap=True,filterable=False):
    BaseWidget.__init__(self) # call Group initializer
    self.rect       = pygame.Rect(rect) # this is where we draw our widget within the surface
    self.y_spacer   = 5 # height in pixels of whitespace between the top and bottom of sprites
    self.offset     = 0
    self.distance   = 0
    self.mousedown  = 0
    self.speed      = 0
    self.num_events = 0
    self.friction   = 2
    self.friction_c = 0
    self.list       = list
    self.wrap       = wrap
    self.selection_indicator = Button(theme.get_image('sel_indicator'),self._selection_indicator_callback)
    self.selection_indicator.rect.topleft = (-100,-100) # off screen at first
    self.viewport_index = 0
    self.scrollable     = None
    self.sprites        = []
    self.selected_index = None # this is the highlighted item
    self.focused_index  = None # this is the item that we think the user is interested in. usually it scrolls.
    self.selected_cb    = selected_cb
    self.generator_cb   = generator_cb
    self.reset_timeout_cb = reset_timeout_cb
    self.last_state     = "idle" # see self._change_state() for possibilities
    self.cur_state      = "idle"
    self.tap_event_threshold = 12
    self.tap_distance_threshold = 12
    self.visible_sprite_indexes = [] # optimization for is_mostly_visible()
    self.visible_sprites        = {} # keys are indexes from self.visible_sprite_indexes, values are return values (should always be a widget derived from BaseWidget) of self.generator_cb.
    self.a2dp_paused    = False
    self.last_clean_up  = time.time()
    self.filter = ""
    self.filterable = filterable
    self.keyIndexes = {}

    self.scroll_bar = ScrollBar(Rect(
      self.rect.right - 60,
      self.rect.top,
      57,
      360),self.sync_with_scroll_bar,0)
    self.scroll_bar.rect.centery = self.rect.centery
    self.scroll_bar.rect.right   = self.rect.right

    self.scroll_up_button = Button(theme.get_image('scroll_up'),self._plus_callback,repeat=True)
    self.scroll_up_button.rect.right  = self.rect.right
    self.scroll_up_button.rect.bottom = self.scroll_bar.rect.top
    self.scroll_down_button = Button(theme.get_image('scroll_down'),self._minus_callback,repeat=True)
    self.scroll_down_button.rect.right = self.rect.right
    self.scroll_down_button.rect.top   = self.scroll_bar.rect.bottom
    self.set_scrollbar(manager.scrollbar_state)
    self.calc_filterlist()

  def set_scrollbar(self, state=False):
    self.scroll_bar.visible = state
    self.scroll_up_button.visible = state
    self.scroll_down_button.visible = state

  def _plus_callback(self):
    self.prev()

  def _minus_callback(self):
    self.next()

  def _selection_indicator_callback(self):
    ''' do nothing '''
    return

  def get_viewport_percent(self):
    ''' do stuff '''
    height = self.get_sprite_by_index(self.viewport_index).rect.height + self.y_spacer
    if len(self.visible_sprites) * height < self.rect.height: viewport_height = len(self.visible_sprites) * height
    else: viewport_height = self.rect.height
    percent = viewport_height * 100 / len(self.list * height)
    if percent > 100: percent = 100
    if percent < 0:   percent = 0
    return percent

  def sync_with_scroll_bar(self):
    if not self.list: return
    self.set_percent(self.scroll_bar.get_percent())
    self.scroll_bar.set_handle_length(self.get_viewport_percent())

  def _change_state(self,new_state):
    l = ['idle','tap','drag']
    if new_state not in l:
      print "WARNING: unknown state %s" % (new_state,)
      return
    self.last_state = self.cur_state
    self.cur_state  = new_state
    self.update_a2dp_paused()

  def has_selected(self):
    ''' The "selected" sprite is the one that is highlighted '''
    if self.selected_index == None: return False
    return True

  def has_focused(self):
    ''' The "focused" sprite is the one that we think the user has chosen '''
    if self.focused_index == None: return False
    return True

  def call_reset_timeout_cb(self):
    if self.reset_timeout_cb: self.reset_timeout_cb()

  def next(self):
    ''' Move focused_sprite to next sprite in list '''
    if self.is_idle():
      self.call_reset_timeout_cb()
      if self.has_focused():
        new_index = self.focused_index + 1
        if not self.wrap and new_index > len(self.list) - 1:
          return
        self.set_focused_index(new_index,True)
      else:
        self.new_focused_index()

  def prev(self):
    ''' Move focused_sprite to previous sprite in list '''
    if self.is_idle():
      self.call_reset_timeout_cb()
      if self.has_focused():
        new_index = self.focused_index - 1
        if not self.wrap and new_index < 0:
          return
        self.set_focused_index(new_index,True)
      else:
        self.new_focused_index()

  def get_selected_sprite(self):
    if not self.has_selected(): return None
    return self.get_sprite_by_index(self.selected_index)

  def get_selected_sprite_index(self):
    if not self.has_selected(): return None
    return self.selected_index

  def get_focused_sprite(self):
    if not self.has_focused(): return None
    return self.get_sprite_by_index(self.focused_index)

  def get_focused_sprite_index(self):
    if not self.has_focused(): return None
    return self.focused_index

  def _calc_new_index(self,index,list):
    length = len(list)
    while index != 0: # FIXME: looping is silly for very large abs() values of index. maybe use divmod instead?
      if index < 0: 
        index = index + length
      elif index > length - 1:
        index = index - length
      else: break # within the normal range, so return it
    return index

  def snap_focused(self):
    if self.is_scrollable() and self.has_focused():
      if not self.is_index_mostly_visible(self.focused_index):
        print "ping focus"
        self.viewport_index = self.focused_index
        self.offset = 0

  def snap_selected(self):
    if self.is_scrollable() and self.has_selected():
      if not self.is_index_mostly_visible(self.selected_index):
        print "ping select"
        self.viewport_index = self.selected_index
        self.offset = 0

  def snap_viewport_as_focused(self):
    if self.is_scrollable() and self.has_focused():
      if not self.is_index_mostly_visible(self.focused_index):
        print "ping viewport_as_focused"
        self.focused_index = self.viewport_index
        self.offset = 0
        return True
    return False

  def set_percent(self,percent):
    percent = 100 - percent
    if not percent: self.viewport_index = len(self.list) - 1
    num_items = len(self.list) - 1
    height = self.get_sprite_by_index(self.viewport_index).rect.height + self.y_spacer
    total_height = num_items * height
    viewport_height = percent * total_height / 100
    (self.viewport_index,self.offset) = divmod(viewport_height,height)
    self.offset = -self.offset

  def get_percent(self):
    num_items = len(self.list) - 1
    height = self.get_sprite_by_index(self.viewport_index).rect.height + self.y_spacer
    total_height = num_items * height
    viewport_height = self.viewport_index * height - self.offset
    if not viewport_height: percent = 100
    else: percent = 100 - (viewport_height * 100 / total_height)
    return percent

  def set_selected_index(self,index,snap=False):
    if self.has_selected(): self.get_selected_sprite().set_selected(False)
    self.selected_index = self._calc_new_index(index,self.list)
    self.get_selected_sprite().set_selected(True)
    if snap: self.snap_selected()
    self.update()

  def new_focused_index(self):
    self.focused_index = self.viewport_index
    self.offset = 0
    self.update()

  def set_focused_index(self,index,snap=False):
    if self.has_focused(): self.get_focused_sprite().set_focus(False)
    self.focused_index = self._calc_new_index(index,self.list)
    self.get_focused_sprite().set_focus(True)
    if snap: self.snap_focused()
    self.update()

  def get_list(self):
    return self.list

  def get_sprite_by_index(self,index):
    index = self._calc_new_index(index,self.list)
    if not self.visible_sprites.has_key(index):
#      print "generating index=%s,value=%s,focused=%s,selected=%s" % (index,self.list[index],(self.focused_index == index),(self.selected_index == index))
      self.visible_sprites[index] = {'last_access_time':time.time(), 'sprite':self.generator_cb(index,self.list[index])}
      if index == self.focused_index: self.visible_sprites[index]['sprite'].set_focus(True)
      if index == self.selected_index: self.visible_sprites[index]['sprite'].set_selected(True)
    else: self.visible_sprites[index]['last_access_time'] = time.time()
    return self.visible_sprites[index]['sprite']

  def _calc_viewport_index(self):
    while self.offset != 0:
      height = self.get_sprite_by_index(self.viewport_index).rect.height + self.y_spacer
      if self.offset > 0:
        if self.offset > height:
          self.offset = self.offset - height
          self.viewport_index = self._calc_new_index(self.viewport_index - 1,self.list)
        elif self.get_sprite_by_index(self.viewport_index).rect.top > self.rect.top:
          self.offset = 0 - height + self.offset
          self.viewport_index = self._calc_new_index(self.viewport_index - 1,self.list)
        else: return
      else:
        if abs(self.offset) > height:
          self.offset = self.offset + height
          self.viewport_index = self._calc_new_index(self.viewport_index + 1,self.list)
        else: return

  def _apply_friction(self):
    self.friction_c = self.friction_c + 1
    if self.friction_c >= self.friction:
      self.friction_c = 0
      self.speed = self.speed - cmp(self.speed,0)

  def _move(self):
    if not self.wrap: # prevent movement wrapping
      if ((self.speed < 0 or self.offset < 0) and self.viewport_index == len(self.list) - 1) or \
         ((self.speed > 0 or self.offset > 0) and self.viewport_index == 0):
        self.speed    = 0
        self.offset   = 0

    self.offset = self.offset + self.speed
    self._calc_viewport_index()
    if not self.speed: return
    self._apply_friction()

  def _update_scroll_bar(self):
    self.scroll_bar.set_percent(self.get_percent())
    self.scroll_bar.set_handle_length(self.get_viewport_percent())

  def _update_sprite_rect(self,index,offset):
    sprite = self.get_sprite_by_index(index)
    sprite.rect.top  = self.rect.top + offset
    sprite.rect.left = self.rect.left
    if not self.rect.colliderect(sprite.rect): return False
    return True

  def is_index_mostly_visible(self,index):
    if not self.list: return False
    if index not in self.visible_sprite_indexes: return False
    if self.rect.collidepoint(self.get_sprite_by_index(index).rect.center): return True
    return False

  def update(self):
    if not self.list: return
    self.scroll_up_button.update()
    self.scroll_down_button.update()
    self.scroll_bar.update()
    self._move()
    self.visible_sprite_indexes = []

    i      = self.viewport_index
    offset = self.offset
    first  = True
    while self._update_sprite_rect(i,offset) or first:
      self.visible_sprite_indexes.append(i)
      offset = self.get_sprite_by_index(i).rect.bottom + self.y_spacer - self.rect.top
      if not self.wrap and i == len(self.list) - 1: break # prevent display wrapping
      i = self._calc_new_index(i+1,self.list)
      first = False
      if i == self.viewport_index: break # handle lists that are shorter than the viewport

    if self.has_focused():
      self.get_focused_sprite().update()
      self.selection_indicator.rect.centery = self.get_focused_sprite().rect.centery
      self.selection_indicator.rect.left = self.rect.left - self.selection_indicator.rect.width - 2

    if time.time() - self.last_clean_up > 5:
      self.clean_up()

    self._update_scroll_bar()

  def _is_tap(self):
    if self.num_events <= \
        self.tap_event_threshold and abs(self.distance) <= \
        self.tap_distance_threshold: return True
    return False

  def tap_select(self,run_callback=True):
    if not self.list: return
    mouse_pos = pygame.mouse.get_pos()
    for i in self.visible_sprite_indexes:
      if self.get_sprite_by_index(i).rect.collidepoint(mouse_pos):
        if run_callback and self.has_focused() and self.get_focused_sprite_index() == i:
          self.set_selected_index(i)
          self.selected_cb()
          self._change_state('idle')
        self.set_focused_index(i)
        break

  def calc_scrollable(self):
    self.scrollable = None
    self.update()
    self.is_scrollable()

  def is_scrollable(self):
    if not self.visible_sprite_indexes: self.update()
    if self.scrollable != None: return self.scrollable
    if not self.list: return False
    height = 0
    for i in self.visible_sprite_indexes:
      height += self.get_sprite_by_index(i).rect.height

    spacer_height = (len(self.visible_sprite_indexes) - 1) * self.y_spacer
    height += spacer_height

    if height > self.rect.height: self.scrollable = True
    elif len(self.list) > len(self.visible_sprite_indexes): self.scrollable = True
    else: self.scrollable = False
    return self.scrollable

  def handle_event(self,event):
    handled = False
    if self.is_scrollable():
      if self.scroll_up_button.handle_event(event): return True
      if self.scroll_down_button.handle_event(event): return True
      if self.scroll_bar.handle_event(event): return True
    if event.type == MOUSEBUTTONDOWN:
      if self.rect.collidepoint(pygame.mouse.get_pos()):
        self.speed      = 0
        self.distance   = 0
        self.num_events = 0
        self.mousedown = 1
    elif event.type == MOUSEBUTTONUP:
      if self.mousedown:
        handled = True
        self.mousedown  = 0
        self.friction_c = 0
        if self._is_tap():
          # This was a tap, not a drag
          self._change_state('tap')
          if self.last_state == 'drag':
            self.tap_select(False)
          self.stop_animation()
    elif event.type == MOUSEMOTION:
      if self.mousedown and self.list and self.is_scrollable():
        (rel_x,rel_y) = event.rel
        self.offset = self.offset + rel_y
        if cmp(rel_y,0) and cmp(rel_y,0) != cmp(self.distance,0): # changed direction
          self.num_events = 0
          self.distance   = 0
        self.num_events = self.num_events + 1
        self.distance   = self.distance   + rel_y
        self.speed      = self.get_sprite_by_index(self.viewport_index).rect.height / 50 * self.distance / self.num_events
        if not self._is_tap(): self._change_state('drag')
    elif event.type == KEYDOWN and event.key == K_RETURN and (event.mod&128)==0:
      handled = True
      if not self.has_focused(): self.new_focused_index()
      self.set_selected_index(self.get_focused_sprite_index())
      self.selected_cb()
    elif event.type == KEYDOWN and event.key == K_UP and (event.mod&128)==0:
      handled = True
      if self.cur_state=='drag' and self.snap_viewport_as_focused():
        self.stop_animation()
      else:
        self.prev()
    elif event.type == KEYDOWN and event.key == K_DOWN and (event.mod&128)==0:
      handled = True
      if self.cur_state=='drag' and self.snap_viewport_as_focused():
        self.stop_animation()
      else:
        self.next()
    elif event.type == KEYDOWN and (event.mod&128)==0 and self.filterable:
        x = str(event.unicode).lower()
        if x!="" and event.key>=32 and event.key<128:
            print "unicode=",event.unicode,x,event.mod,event.key
            self.filter_jump(x, (event.mod&1)>0)
#           self.filter_add(x)
#        elif event.key == 8:
#            if event.mod == 1:
#                self.filter_reset()
#            else:
#                self.filter_backspace()

    if self.last_state == 'idle' and self.cur_state == 'tap': self.tap_select()
    if self.mousedown: handled = True
    return handled
    
  def move_home(self):
    self.call_reset_timeout_cb()
    self.set_focused_index(0,snap=True)

  def move_end(self):
    self.call_reset_timeout_cb()
    self.set_focused_index(len(self.list)-1,snap=True)

  def filter_jump(self, char, reverse=False):
    char = char.lower()[0]
    print "jump to",char
    if self.keyIndexes.has_key(char):
        li = self.keyIndexes[char]
        if reverse:
            jump = li[-1]
            for l in reversed(li):
                if l<self.focused_index:
                    jump=l
                    break
        else:
            jump = li[0]
            for l in li:
                if l>self.focused_index:
                    jump=l
                    break

        self.call_reset_timeout_cb()
        self.set_focused_index(jump,snap=True)

  def filter_addstr(self, chars):
# check if chars is addable first (any matches, etc)
    self.filter = self.filter + chars
    self.filter_updated()

  def filter_reset(self):
    self.filter = ""
    self.filter_updated()

  def filter_backspace(self):
    self.filter = self.filter[:-1]
    self.filter_updated()

  def filter_updated(self):
    print "new filter string = *"+self.filter+"*"

  def update_a2dp_paused(self):
    ''' A2DP + Mplayer chews up a lot of CPU, so if the user wants to spin the scroll widget
    at full speed, then we need to pause A2DP playback while the widget is scrolling.'''
    if self.a2dp_paused:
      if self.is_idle() and manager.player.paused:
        manager.player.pause()
        self.a2dp_paused = False
    else:
      if self.cur_state == 'drag' and manager.a2dp_button.a2dp_on and not manager.player.paused:
        manager.player.pause()
        self.a2dp_paused = True

  def is_idle(self):
    idle = (not self.speed and not self.mousedown)
    if idle and self.cur_state != 'idle': self._change_state('idle')
    if not idle: self.call_reset_timeout_cb()
    return idle

  def draw(self,surface):
    if not self.list: return
    i = self.viewport_index
    for i in self.visible_sprite_indexes:
      self.get_sprite_by_index(i).draw(surface)
    if self.has_focused() and self.is_index_mostly_visible(self.focused_index): self.selection_indicator.draw(surface)
    if self.is_scrollable():
      self.scroll_up_button.draw(surface)
      self.scroll_down_button.draw(surface)
      self.scroll_bar.draw(surface)

  def stop_animation(self):
    self.speed      = 0
    self.distance   = 0
    self.num_events = 0
    self.mousedown  = 0
    self.friction_c = 0
    self.update()

  def clean_up(self):
    ''' delete unused self.visible_sprites keys '''
    now = time.time()
    self.last_clean_up = now
    collected = False
    for key in self.visible_sprites.keys():
      if now - self.visible_sprites[key]['last_access_time'] > 5: # delete if inactive for more than 5 seconds
        print "deleting index=%s,value=%s" % (key,self.list[key])
        del self.visible_sprites[key]
        collected = True
    if collected: gc.collect(0)

  def swap_items(self, item1, item2):
    tmp = self.list[item1]
    self.list[item1] = self.list[item2]
    self.list[item2] = tmp
    self.swapped_items(item1, item2)

  def calc_filterlist(self):
    self.keyIndexes = {}
    cnt = -1
    for i in self.list:
        cnt+=1
        itemname = self.generator_cb(cnt, i, get_name=True)
        if len(itemname)>0:
            char = itemname.lower()[0]
            if not self.keyIndexes.has_key(char):
                self.keyIndexes[char] = []
            self.keyIndexes[char].append(cnt)
#    print self.keyIndexes

  def flush_visible(self):
    self.visible_sprites = {}
    self.snap_focused()
    self.update()

  def swapped_items(self, item1, item2):
    if self.selected_index == item1:
      self.selected_index = item2
    elif self.selected_index == item2:
      self.selected_index = item1
      
    if self.focused_index == item1:
      self.focused_index = item2
    elif self.focused_index == item2:
      self.focused_index = item1
   
    self.flush_visible()
    self.calc_filterlist()

  def close(self):
    self.visible_sprites = {}
    self.list = []
    self.selected_cb, self.generator_cb, self.reset_timeout_cb = None, None, None


class CoverArtWidget(BaseWidget):
  def __init__(self,id,type,name,show_reflection=True,unknown_okay=True):
    BaseWidget.__init__(self)
    self.invalid    = True
    self.id         = id
    self.type       = type
    self.name       = name
    self.show_reflection = show_reflection
    self.theme_rect       = theme.get_rect('album_art_bg')
    self.theme_rect_ref   = theme.get_rect('album_art_ref')
    self.theme_rect_image = theme.get_rect('album_art_image')

    self.cache_rect = None
    self.rect       = None
    if not self.get_cache_rect(unknown_okay): return
    if show_reflection:
      self.rect = Rect(0,0,self.theme_rect.width,self.theme_rect.height)
    else:
      self.rect = Rect(0,0,self.theme_rect_image.width,self.theme_rect_image.height)
    self.invalid    = False
    self.calced_im  = None
    if self.type == "artist":
      self.cachefile  = globals.artistcache
    else:
      self.cachefile  = globals.albumcache

  def get_cache_rect(self, unknown_okay=True):
    if self.type == "album":
      list = db.get_album_art(self.id)
    elif self.type == "artist":
      list = db.get_artist_art(self.id)

    if not list:
      print "invalid album cache for %s" % (self.name,)
      return # should never happen

    row = list[0]
    if not unknown_okay and row['x']==0 and row['y']==0: return False
    self.cache_rect = Rect(row['x'],row['y'],self.theme_rect_image.width,self.theme_rect_image.height)
    return True

  def calc_image(self):
    im = pygame.Surface((self.theme_rect.width, self.theme_rect.height), 0, theme.surface)
    im.blit(self.cachefile,self.rect,self.cache_rect)

    reflection=pygame.transform.flip(im, 0, 1)
    reflection.set_alpha(60)
    theme.blit(im,(0,self.theme_rect_image.height),'album_art_ref')
    im.blit(reflection, (0, self.theme_rect_image.height), Rect(0, self.theme_rect_ref.height, self.theme_rect_ref.width, self.theme_rect_ref.height*2))
    #name in the reflection space
    globals.gprint(str(self.name),im,(2, 145),16,False)
    return im

  def draw(self,surface,point=None):
    if not point: point = self.rect
    if not self.show_reflection:
      surface.blit(self.cachefile,point,self.cache_rect)
    else:
      if not self.calced_im:
        self.calced_im = self.calc_image()
      surface.blit(self.calced_im,point)

  def __cmp__(self,other):
    if hasattr(other,'id') and hasattr(other,'type'): # FIXME: this is an ugly hack made 'necessary' by combining Button()s with Album()s in the same list
      return cmp(self.type+'_'+str(self.id),other.type+'_'+str(other.id))
    return 1

class ArtistArt(CoverArtWidget):
  def __init__(self,id,name,show_reflection=True,unknown_okay=True):
    CoverArtWidget.__init__(self,id,"artist",name,show_reflection=show_reflection,unknown_okay=unknown_okay)

class Album(CoverArtWidget):
  def __init__(self,id,name,show_reflection=True,unknown_okay=True):
    CoverArtWidget.__init__(self,id,"album",name,show_reflection=show_reflection,unknown_okay=unknown_okay)


class BackButton(Button):
  def __init__(self):
    ''' This is the button in the lower left. It's
    a back button and clicking it goes back to
    the album screen. '''
    self.image = theme.get_surface((125,63))
    self._load_image()
    Button.__init__(self,self.image,manager.back)
    self.rect.left = 0 # FIXME: the controlling view should probably set the x,y pos for us
    self.rect.top  = manager.screen.get_rect().height - self.image.get_rect().height - 0

  def _load_image(self):
    self.image.fill(theme.colorkey)
    if manager.view_history:
      theme.blit(self.image,(37,0),'back_button')
    else:
      theme.blit(self.image,(41,0),'exit_button')

  def update(self):
    return


class PlayButton(PlayBackButton):
  def __init__(self):
    ''' I really hope I don't have to explain this button. '''
    self.image = theme.get_surface((115,53))
    theme.blit(self.image,(39,0),'play')
    PlayBackButton.__init__(self,self.image,self._callback)
    self.rect.left = 675 # FIXME: the controlling view should probably set the x,y pos for us
    self.rect.top  = 145
    self.playing   = False

  def _load_image(self):
    self.image.blit(manager.background,(0,0),self.rect)
    if manager.playlist.is_paused(): theme.blit(self.image,(39,0),'play')
    else: theme.blit(self.image,(40,0),'pause')

  def update(self):
    self._load_image()

  def _callback(self):
    print "playbutton"
    manager.playlist.pause()
    self.update()
    return 


class NextButton(PlayBackButton):
  def __init__(self):
    ''' Skips forward by one track '''
    self.image = theme.get_surface((115,53))
    theme.blit(self.image,(40,0),'next')
    PlayBackButton.__init__(self,self.image,self._make_callback())
    self.rect.left = 675 # FIXME: the controlling view should probably set the x,y pos for us
    self.rect.top  = 208

  def _make_callback(self):
    def _callback():
      manager.next_track()
      return 
    return _callback


class PrevButton(PlayBackButton):
  def __init__(self):
    ''' Skips backward by one track '''
    self.image = theme.get_surface((115,53))
    theme.blit(self.image,(40,0),'prev')
    PlayBackButton.__init__(self,self.image,self._make_callback())
    self.rect.left = 675 # FIXME: the controlling view should probably set the x,y pos for us
    self.rect.top  = 82

  def _make_callback(self):
    def _callback():
      manager.prev_track()
      return 
    return _callback


class RepeatButton(Button):
  def __init__(self):
    ''' Repeat: (none|one|all) '''

    self.image_x = 27
    self.image = theme.get_surface((125,43))
    theme.blit(self.image,(self.image_x,0),'repeat_off')
    Button.__init__(self,self.image,self._make_callback())

    self.rect.left = 0 # FIXME: the controlling view should probably set the x,y pos for us
    self.rect.top  = manager.screen.get_rect().height - self.image.get_rect().height - 123
    self.read_interpret_mode()
    self.update()

  def _make_callback(self):
    def _callback():
      if self.mode=='repeat_off': self.mode='repeat_all'
      elif self.mode=='repeat_all': self.mode='repeat_one'
      else: self.mode='repeat_off'
      self.write_mode()
      self.update()
      print "RepeatButton: new mode is %s" % self.mode
      return 
    return _callback

  def read_interpret_mode(self):
    if manager.playlist.repeat_one: self.mode='repeat_one'
    elif manager.playlist.repeat: self.mode='repeat_all'
    else: self.mode='repeat_off'

  def write_mode(self):
    if self.mode=='repeat_one':
      manager.playlist.repeat=True
      manager.playlist.repeat_one=True
      manager.playlist.continuous=True
    elif self.mode=='repeat_all':
      manager.playlist.repeat=True
      manager.playlist.repeat_one=False
      manager.playlist.continuous=True
    else:
      manager.playlist.repeat=False
      manager.playlist.repeat_one=False
      manager.playlist.continuous=True
    if manager.dbusapi: manager.dbusapi.playmode_changed(self.mode)

  def update(self):
    theme.blit(self.image,(self.image_x,0),self.mode)


class AddAlbumButton(Button):
  def __init__(self):
    ''' Enqueues the whole album in playlist '''

    self.image_x = 27
    self.image = theme.get_surface((125,43))
    theme.blit(self.image,(self.image_x,0),'add_album')
    Button.__init__(self,self.image,self._callback)

    self.rect.left = 0 # FIXME: the controlling view should probably set the x,y pos for us
    self.rect.top  = manager.screen.get_rect().height - self.image.get_rect().height - 220
    self.update()

  def _callback(self):
    import views
    totaladded = 0
    if isinstance(manager.view,views.ArtistAlbumView):
      # get song list from DB for each album
      for album_row in manager.view.scroll_widget.get_list():
        list = db.get_songs(album_id=album_row['album_id'])
        for row in list:
          manager.playlist.add(row['path'])
          totaladded += 1

      if (3 < totaladded) and manager.playlist.get_random():
        manager.playlist.shuffle()
        if not manager.playlist.is_paused():
          manager.playlist.play(0)
      manager.playlist.update()
      manager.show_nowplaying()
      manager.view_history_pop() # remove ArtistAlbumView from history
      return 
    else:
      for row in manager.view.scroll_widget.get_list():
        manager.playlist.add(row['path'])
        totaladded += 1
      if (3 < totaladded) and manager.playlist.get_random():
        manager.playlist.shuffle()
        if not manager.playlist.is_paused():
          manager.playlist.play(0)
      manager.playlist.update()
      manager.show_nowplaying()
      manager.view_history_pop() # remove SongView from history
      return 


class VolumeButton(Button):
  def __init__(self):
    ''' Show VolumeView '''
    self.volume = None
    self.image_x = 27
    self.image = theme.get_surface((125,43))
    Button.__init__(self,self.image,self._callback)

    self.rect.left = 0 # FIXME: the controlling view should probably set the x,y pos for us
    self.rect.top  = 30+26
    self._load_image()
    self.update()

  def update(self):
    if manager.player.volume != self.volume:
      self._load_image()

  def _load_image(self):
    self.volume = manager.player.volume
    image_name = 'muted' if not self.volume else 'volume'
    theme.blit(self.image,(self.image_x,0),image_name)

  def _callback(self):
    manager.show_volume()


class ClearPlaylistButton(PlayBackButton):
  def __init__(self):
    ''' Clear Playlist '''

    self.image_x = 27
    self.image = theme.get_surface((125,43))
    theme.blit(self.image,(self.image_x,0),'clear_playlist')
    Button.__init__(self,self.image,self._callback)

    self.rect.left = 0 # FIXME: the controlling view should probably set the x,y pos for us
    self.rect.top  = manager.screen.get_rect().height - self.image.get_rect().height - 220
    self.update()

  def _callback(self):
    import gtk
    if (not globals.confirm_dlg("Clear playlist?", gtk.STOCK_CLEAR)): return
    for i in range(len(manager.view_history)):
      if manager.view_history[i].caption == 'Now Playing': # insure that we see the view before the playlist view
        manager.back(i-1)
        break
    if manager.view.caption == 'Now Playing': manager.back()
    manager.playlist.clear()
    return 


class DeleteOneButton(PlayBackButton):
  def __init__(self):
    ''' Delete One from Playlist '''

    self.image_x = 27
    self.image = theme.get_surface((125,43))
    theme.blit(self.image,(self.image_x,0),'delete_one')
    Button.__init__(self,self.image,self._callback)

    self.rect.left = 0 # FIXME: the controlling view should probably set the x,y pos for us
    self.rect.top  = 140
    self.update()

  def _callback(self):
    manager.nowplaying_view.remove_item()


class DeletePlaylistFileButton(Button):
  def __init__(self):
    ''' Delete Selected File from PlaylistView '''

    self.image_x = 27
    self.image = theme.get_surface((125,43))
    theme.blit(self.image,(self.image_x,0),'delete_file')
    Button.__init__(self,self.image,self._callback)

    self.rect.left = 0 # FIXME: the controlling view should probably set the x,y pos for us
    self.rect.top  = 140
    self.update()

  def _callback(self):
    import gtk
    if (not globals.confirm_dlg("Delete selected file?", gtk.STOCK_DELETE)): return
    sel_sprite = manager.view.scroll_widget.get_focused_sprite()
    if sel_sprite:
      print "delete playlist file",sel_sprite.path
      manager.playlist.delete_playlist(sel_sprite.path)
      manager.view._load_scroll_widget()


class A2DPButton(Button):
  def __init__(self):
    ''' This is the bluetooth button in the upper right. It displays
    the status of bluez a2dpd. '''
    self.image = theme.get_surface((125,43))
    Button.__init__(self,self.image,self._make_a2dp_button_callback())
    self.a2dp_on   = False
    self.rect.left = -200
    self.rect.top  = -200
    if not manager.has_a2dp and not globals.theme_tester: return
    self.tester_a2dp_status = False
    theme.blit(self.image,(45,0),'a2dp_off')
    self.rect.left = 681
    self.rect.top  = 10

  def _load_image(self):
    if globals.theme_tester:
      self.a2dp_on = self.tester_a2dp_status
    else:
      import mplayer
      if isinstance(manager.player, mplayer.Mplayer):
        self.a2dp_on = manager.player.get_a2dpd()
      else: self.a2dp_on = False
    print "a2dp: %s" % (self.a2dp_on,)
    self.image.fill(theme.colorkey)
    if self.a2dp_on: theme.blit(self.image,(45,0),'a2dp_on')
    else: theme.blit(self.image,(45,0),'a2dp_off')

  def update(self):
    if not manager.has_a2dp and not globals.theme_tester: return
    self._load_image()

  def _make_a2dp_button_callback(self):
    def _a2dp_button_callback():
      print "switching a2dp modes from button"
      manager.clear()
      status_area = Text("PLEASE WAIT...")
      status_area.rect.topleft = (130,200)
      status_area.update()
      status_area.draw(manager.screen)
      pygame.display.flip()
      
      if globals.theme_tester:
        self.tester_a2dp_status = not self.tester_a2dp_status
        self.update()
        return

      a2dp = None
      import mplayer
      if isinstance(manager.player, mplayer.Mplayer):
        a2dp = manager.player.get_a2dpd()
      if not a2dp:
        manager.switch_player(player_name="mplayer", set_a2dp=True)
      else:
        manager.switch_player(skip_if_a2dp=False)

      self.update()
      return 
    return _a2dp_button_callback


class NowPlayingButton(PlayBackButton):
  def __init__(self):
    ''' This is the button in the lower right. It displays
    the currently playing album and song. '''
    self.title_text_x = 2
    self.title_text_y = 152
    self.position_text_x = 2
    self.position_text_y = 0
    self.album_x = 0
    self.album_y = 20
    self.image = theme.get_surface((125,160+self.album_y))
    self.pbar_background = None
    theme.blit(self.image,(self.album_x,self.album_y),'album_art_bg')
    Button.__init__(self,self.image,self._make_nowplaying_button_callback())
    self.rect.left = 675 # FIXME: the controlling view should probably set the x,y pos for us
    self.rect.top  = manager.screen.get_rect().height - self.image.get_rect().height
    self.current   = None
    self.last_sprite = None
    self.last_sprite_type = ""
    self.last_id = 0
    self.position_string = ""
    self.current_song = None
    self.pbar         = None
    self._get_pbar_background()

  def _get_pbar_background(self):
    self.pbar_background = theme.get_surface((self.rect.width,self.album_y - self.position_text_y))
    self.pbar_background.blit(manager.background,(0,0),Rect(
      self.rect.left,
      self.rect.top  + self.position_text_y,
      self.rect.width,
      self.album_y - self.position_text_y))
    self.pbar_background.fill((0,0,0),Rect(0,self.pbar_background.get_rect().height - 5,self.pbar_background.get_rect().width,5))

  def _load_image(self, flush=False):
    # position text
    if self.current_song and manager.playlist.status() == self.current:
      song = self.current_song
    else:
      song = self.current_song = db.song_of_path(manager.playlist.status())[0]
    if not self.pbar: self.pbar = ProgressBar(
        Rect(0,self.album_y - 4,self.rect.width,3),segmented=False)

    current_time  = globals.format_time(manager.player.seconds)
    player_length = globals.format_time(manager.player.length)
    new_pos_s     = "%s of %s (%3d%%)" % (current_time,player_length,manager.player.percent)
    if self.position_string != new_pos_s:
      self.pbar.set_percent(manager.player.percent)
      self.position_string = new_pos_s
      self.image.blit(self.pbar_background,(0,self.position_text_y))
      self.pbar.draw(self.image)
      globals.gprint(
        self.position_string,
        self.image,
        (self.position_text_x, self.position_text_y),
        16,
        False)
    if manager.playlist.status() == self.current and not flush: return
    print "nowplaying: " + song['album']

    if flush or not self.last_sprite or self.last_sprite_type!=manager.nowplayingbuttonimage or (self.last_sprite_type=="album" and self.last_sprite.id != song['album_id']) or (self.last_sprite_type=="artist" and self.last_sprite.id != song['artist_id']):
      self.last_sprite_type=manager.nowplayingbuttonimage
      if manager.nowplayingbuttonimage=="artist":
        self.last_sprite = ArtistArt(song['artist_id'], song['artist'])
        self.last_id = song['artist_id']
      else:
        self.last_sprite = Album(song['album_id'], song['album'], unknown_okay=False)
        self.last_id = song['album_id']
        if self.last_sprite.invalid:
          print "invalid nowplaying album image, using artistimage instead"
          self.last_sprite = ArtistArt(song['artist_id'], song['artist'])
          self.last_sprite_type="artist"
          self.last_id = song['artist_id']

    self.last_sprite.draw(self.image,(self.album_x,self.album_y))

    track = song['track']
    if not track: track = ''
    else: track = "%02d " % (track,)
    # title text
    globals.gprint(
      track+song['title'],
      self.image,
      (self.title_text_x, self.title_text_y),
      16)
    self.current = manager.playlist.status()

  def update(self, flush=False):
    if not manager.playlist.status():
      return
    self._load_image(flush)

  def _make_nowplaying_button_callback(self):
    def _nowplaying_button_callback():
      print "show now_playing"
      if manager.view.scroll_widget:
        manager.view.scroll_widget.stop_animation()
      return manager.show_nowplaying()
    return _nowplaying_button_callback


class Label(BaseWidget):
  def __init__(self, caption, rect, pad_x=4, pad_y=4, font_size=16, background=None):
    self.visible    = True
    self.background = background
    self.rect       = rect
    self.pad_x      = pad_x
    self.pad_y      = pad_y
    self.font_size  = font_size
    self.set_caption(caption)

  def set_caption(self, caption):
    self.caption = caption
    if self.background:
      self.image = theme.get_image(self.background)
    else:
      self.image = theme.get_surface((self.rect.width,self.rect.height))
      self.image.blit(manager.background,(0,0),self.rect)
    globals.gprint(
      self.caption,
      self.image,
      (self.pad_x, self.pad_y),
      self.font_size)
    


class Artist(BaseWidget):
  def __init__(self,artist_id,artist,selected=False):
    BaseWidget.__init__(self)
    self.id         = artist_id
    self.selected   = selected
    self.theme_rect = None
    self.get_theme_rect()
    self.num_albums = 0
    self.get_num_albums()
    self.rect       = Rect(0,0,self.theme_rect.width,self.theme_rect.height)
    self.artist_art = ArtistArt(artist_id,artist,show_reflection=False)
    self.artist     = RawText(self.get_artist_rect(),artist,subtext=self.get_subtext())

  def get_num_albums(self):
    list = db.get_albums(artist_id=self.id)
    self.num_albums = len(list)

  def get_subtext(self):
    postfix = ''
    if self.num_albums != 1: postfix='s'
    return "%s Album%s" % (self.num_albums,postfix)

  def get_artist_rect(self):
    x = self.artist_art.rect.right
    y = self.rect.top + 30
    return Rect(x,y,self.rect.right - 55 - x, self.rect.bottom - y)

  def get_theme_rect(self):
    if self.selected:
      self.theme_rect = theme.get_rect('albumartist_bg_sel')
    else:
      self.theme_rect = theme.get_rect('albumartist_bg')

  def draw(self,surface):
    surface.blit(theme.surface,self.rect,self.theme_rect)
    self.artist_art.rect.topleft = (self.rect.left + 16,self.rect.top + 6)
    self.artist_art.draw(surface)
    self.artist.rect.topleft = self.get_artist_rect().topleft
    self.artist.draw(surface)

  def update(self):
    self.artist_art.update()
    self.artist.update()

  def set_focus(self,focus):
    self.artist.set_focus(focus)
      
  def __cmp__(self,other):
    return cmp(
        ': '.join((self.artist.name.lower(),str(self.artist_art.id))),
        ': '.join((other.artist.name.lower(),str(other.artist_art.id)))
    )


class AlbumArtist(BaseWidget):
  def __init__(self,album_id,album,artist_id,artist,selected=False):
    BaseWidget.__init__(self)
    self.text_x   = 55
    self.text_y   = 30
    self.selected = selected
    self.theme_rect = None
    self.get_theme_rect()
    self.rect      = Rect(0,0,self.theme_rect.width,self.theme_rect.height)
    self.album     = Album(album_id,album,show_reflection=False)
    self.album_id  = album_id
    self.artist_id = artist_id
    self.num_songs = 0
    self.get_num_songs()
    self.year      = self.get_album_year()
    self.artist    = RawText(self.get_artist_rect(),artist,album)
    self.third_row = RawText(self.get_artist_rect(),self.get_third_row_text(),size=30)

  def get_num_songs(self):
    list = db.get_songs(album_id=self.album_id)
    self.num_songs = len(list)

  def get_third_row_text(self):
    postfix = ''
    if self.num_songs != 1: postfix='s'
    if self.year:
      return "%s, %s Track%s" % (self.year,self.num_songs,postfix)
    return "%s Track%s" % (self.num_songs,postfix)

  def get_album_year(self):
    year = db.get_album_year(self.album_id)
    if not year: return ''
    return str(year)

  def get_artist_rect(self):
    x = self.album.rect.right
    y = self.rect.top + self.text_y
    return Rect(x,y,self.rect.right - self.text_x - x, 40)

  def get_theme_rect(self):
    if self.selected:
      self.theme_rect = theme.get_rect('albumartist_bg_sel')
    else:
      self.theme_rect = theme.get_rect('albumartist_bg')

  def draw(self,surface):
    surface.blit(theme.surface,self.rect,self.theme_rect)
    self.album.rect.topleft = (self.rect.left + 16,self.rect.top + 6)
    self.album.draw(surface)
    self.artist.rect.topleft = self.get_artist_rect().topleft
    self.artist.draw(surface)
    self.third_row.rect.topleft = self.artist.rect.bottomleft
    self.third_row.draw(surface)

  def update(self):
    self.album.update()
    self.artist.update()
    self.third_row.update()

  def set_focus(self,focus):
    self.artist.set_focus(focus)
    self.third_row.set_focus(focus)
      
  def __cmp__(self,other):
    return cmp(
        ': '.join((self.artist.name.lower(),str(self.album.id))),
        ': '.join((other.artist.name.lower(),str(other.album.id)))
    )


class ScrollingText(BaseWidget):
  ''' scrolling text within a rectangle '''
  def __init__(self,name,rect,size=False):
    self.rect     = rect
    self.name     = name
    self.size     = size
    self.offset   = 0
    self.step     = 10  # number of pixels to move text
    self.frequency= 0.1 # how often to move text, in seconds
    self.focus    = False
    self.font_surf= globals.gprint_ret(self.name,self.size)
    self.sep_font_surf= globals.gprint_ret(' ~ ',self.size)
    self.scroll_timeout_start = 0

  def draw(self,surface):
    old_clip = surface.get_clip()
    surface.set_clip(self.rect)
    surface.blit(self.font_surf,(self.rect.left-self.offset,self.rect.top))
    if self.offset:
      surface.blit(self.sep_font_surf,(self.rect.left-self.offset + self.font_surf.get_rect().width,self.rect.top))
      surface.blit(self.font_surf,(self.rect.left-self.offset + self.font_surf.get_rect().width + self.sep_font_surf.get_rect().width,self.rect.top))
    surface.set_clip(old_clip)
      
  def set_focus(self,focus):
    if focus != self.focus:
      if not focus:
        self.offset = 0
    self.focus = focus

  def update(self):
    if not self.scroll_timeout_start or time.time() - self.scroll_timeout_start >= self.frequency:
      self.scroll_timeout_start = time.time()
      if self.font_surf.get_rect().width> self.rect.width:
        self.offset = self.offset + self.step
        if self.offset >= self.font_surf.get_rect().width + self.sep_font_surf.get_rect().width: self.offset = 0
        return True
    return False


class RawText(BaseWidget):
  # FIXME: this shouldn't take a height argument. Height should
  #        be automatic based on returned font surface size
  # FIXME: subtext is probably a bad idea. we should just take
  #        a font size instead and do subtext manually everywhere
  def __init__(self, rect, name, subtext=None, selected=False, size=None):
    BaseWidget.__init__(self)
    self.name     = name
    self.subtext  = subtext
    self.selected = selected
    self.rect     = rect
    self.focus    = False
    self.scrolling_text = None
    self.scrolling_subtext = None
    self.text_x   = 15
    self.text_y   = 25
    self.size     = size
    if self.subtext: self.text_y = self.text_y - 15
    self.get_scrolling_text()
    self.get_scrolling_subtext()

  def get_scrolling_text(self):
    if not self.scrolling_text:
      self.scrolling_text = ScrollingText(
          self.name,
          Rect(self.text_x, self.text_y, self.rect.width - (self.text_x * 2) - self.text_x, self.rect.height),
          self.size)

  def get_scrolling_subtext(self):
    if self.subtext and not self.scrolling_subtext:
      self.scrolling_subtext = ScrollingText(
          self.subtext,
          Rect(self.text_x, self.text_y+30, self.rect.width - (self.text_x * 2) - self.text_x, self.rect.height),
          30)

  def draw(self,surface):
    self.scrolling_text.rect.topleft = (self.rect.left + self.text_x, self.rect.top + self.text_y)
    self.scrolling_text.draw(surface)
    if self.scrolling_subtext:
      self.scrolling_subtext.rect.topleft = (self.rect.left + self.text_x, self.rect.top + self.text_y+30)
      self.scrolling_subtext.draw(surface)

  def __cmp__(self,other):
    if hasattr(other,'name'): # FIXME: this is an ugly hack made 'necessary' by combining Button()s with Album()s in the same list
      return cmp(self.name.lower(),other.name.lower())
    return 0

  def set_focus(self,focus):
    self.scrolling_text.set_focus(focus)
    if self.scrolling_subtext: self.scrolling_subtext.set_focus(focus)

  def update(self):
    self.scrolling_text.update()
    if self.scrolling_subtext: self.scrolling_subtext.update()


class Text(RawText):
  def __init__(self, name, subtext=None, selected=False):
    self.selected = selected
    self.theme_rect = None
    self.get_theme_rect()
    self.rect     = Rect(0,0,self.theme_rect.width,self.theme_rect.height)
    self.name     = name
    self.subtext  = subtext
    RawText.__init__(self,self.rect,name,subtext,self.selected)

  def get_theme_rect(self):
    if self.selected:
      self.theme_rect = theme.get_rect('text_bg_sel')
    else:
      self.theme_rect = theme.get_rect('text_bg')

  def draw(self,surface):
    surface.blit(theme.surface,self.rect,self.theme_rect)
    RawText.draw(self,surface)

  def set_selected(self,selected):
    if selected != self.selected: # ignore no change
      self.selected = selected
      self.get_theme_rect()


class IconText(Text):
  def __init__(self, icon_name, name, subtext=None, selected=False):
    Text.__init__(self,name,subtext,selected)
    self.icon_x    = 5
    self.icon_name = icon_name
    self.icon_rect = theme.get_rect(self.icon_name)
    self.text_x += self.icon_x + self.icon_rect.width

  def draw(self,surface):
    Text.draw(self,surface)
    icon_height = self.icon_rect.height
    icon_top = self.rect.centery - icon_height / 2
    theme.blit(surface,(self.rect.left + self.icon_x,icon_top),self.icon_name)


class CheckBoxText(IconText):
  def __init__(self, name, checked_callback, subtext=None, selected=False):
    self.checked_callback = checked_callback
    self.checked = self.checked_callback()
    self.last_checked = self.checked
    IconText.__init__(self,self._get_icon_name(),name,subtext,selected)

  def _get_icon_name(self):
    if self.checked: return 'checkbox_checked'
    else: return 'checkbox_unchecked'

  def update(self):
    self.checked = self.checked_callback()
    if self.checked != self.last_checked:
      self.last_checked = self.checked
      self.icon_name = self._get_icon_name()
    IconText.update(self)


class M3U(Text):
  def __init__(self,id,name,path):
    self.id       = id
    self.name     = name
    self.path     = path
    self.num_songs= 0
    self.get_num_songs()
    Text.__init__(self,self.name,subtext=self.get_subtext())

  def get_num_songs(self):
    from m3u import m3u as m3u
    list = m3u.songs_of_path(self.path)
    self.num_songs = len(list)

  def get_subtext(self):
    postfix = ''
    if self.num_songs != 1: postfix='s'
    return "%s Track%s" % (self.num_songs,postfix)


class Genre(Text):
  def __init__(self,id,name):
    self.id       = id
    self.name     = name
    self.num_artists = 0
    self.num_albums  = 0
    self.get_num_artists()
    self.get_num_albums()
    Text.__init__(self,self.name,subtext=self.get_subtext())

  def get_num_artists(self):
    list = db.get_artists(genre_id=self.id)
    self.num_artists = len(list)

  def get_num_albums(self):
    list = db.get_albums(genre_id=self.id)
    self.num_albums = len(list)

  def get_subtext(self):
    artist_postfix = ''
    if self.num_artists != 1: artist_postfix='s'
    album_postfix = ''
    if self.num_albums != 1: album_postfix='s'
    return "%s Artist%s, %s Album%s" % (self.num_artists,artist_postfix,self.num_albums,album_postfix)


class Song(Text):
  def __init__(self,track,title,path,artist=None,artist_id=None,flags=0,album=None,album_id=None,subtext_album=False):
    self.track     = self._fix_track(track)
    self.title     = title
    self.path      = path
    self.artist    = artist
    self.artist_id = artist_id
    self.album     = album
    self.album_id  = album_id
    self.flags     = flags
    self.track_font_surf= globals.gprint_ret(self.track)
    if subtext_album==False:
      Text.__init__(self,self.title,subtext=self.artist)
    else:
      Text.__init__(self,self.title,subtext=self.album)

  def _fix_track(self,track):
    if not track: track = ''
    else: track = "%02d " % (track,)
    return track

  def get_scrolling_text(self):
    if not self.scrolling_text:
      self.scrolling_text = ScrollingText(
          self.name,
          Rect(
            self.text_x + self.track_font_surf.get_rect().width,
            self.text_y,
            self.rect.width - (self.text_x * 2) - self.track_font_surf.get_rect().width,
            self.rect.height))

  def get_scrolling_subtext(self):
    if self.subtext and not self.scrolling_subtext:
      self.scrolling_subtext = ScrollingText(
          self.subtext,
          Rect(
            self.text_x + self.track_font_surf.get_rect().width,
            self.text_y+30,
            self.rect.width - (self.text_x * 2) - self.track_font_surf.get_rect().width,
            self.rect.height),
          30)

  def draw(self,surface):
    surface.blit(theme.surface,self.rect,self.theme_rect)
    surface.blit(self.track_font_surf,(self.rect.left + self.text_x,self.rect.top + self.text_y))
    self.scrolling_text.rect.topleft = (self.rect.left + self.text_x + self.track_font_surf.get_rect().width, self.rect.top + self.text_y)
    self.scrolling_text.draw(surface)
    if self.scrolling_subtext:
      self.scrolling_subtext.rect.topleft = (self.rect.left + self.text_x + self.track_font_surf.get_rect().width, self.rect.top + self.text_y+30)
      self.scrolling_subtext.draw(surface)

  def __cmp__(self,other):
    if not other: return 0
    return cmp(self.track + self.name.lower(),other.track + other.name.lower())


class ProgressBar(BaseWidget):
  def __init__(self, rect, percent=0, color=None, segmented=True, horizontal=True):
    ''' Displays a graphical bar within a rectangle representing a positive integer 
    between 0 and 100, inclusive '''
    self.visible    = True
    self.rect       = rect
    self.percent    = int(percent)
    self.horizontal = horizontal
    self.segmented  = segmented
    if color == None: self.bar_color = theme.bar_color_sel
    else: self.bar_color = color

  def draw(self,image):
    if self.horizontal:
      max_bar_width      = self.rect.right - self.rect.left
      current_bar_width  = max_bar_width * self.percent / 100
      bar_segment_width  = max_bar_width / 10
      current_bar_height = self.rect.bottom - self.rect.top
      current_bar_top    = self.rect.top
    else:
      max_bar_height     = self.rect.bottom - self.rect.top
      current_bar_width  = self.rect.right - self.rect.left
      current_bar_height = max_bar_height * self.percent / 100
      current_bar_top    = self.rect.bottom - current_bar_height
      bar_segment_height = max_bar_height / 10

    if not self.segmented: image.fill(self.bar_color,Rect(self.rect.left,current_bar_top,current_bar_width,current_bar_height))
    else:
      c = 0
      if self.horizontal:
        while c < current_bar_width:
          if c + bar_segment_width < current_bar_width:
            current_segment_width = bar_segment_width
          else:
            current_segment_width = current_bar_width - c
          image.fill(self.bar_color,Rect(self.rect.left + c,self.rect.top,current_segment_width - 1,current_bar_height))
          c += bar_segment_width
      else:
        while c < current_bar_height:
          if c + bar_segment_height < current_bar_height:
            current_segment_height = bar_segment_height
          else:
            current_segment_height = current_bar_height - c
          image.fill(self.bar_color,Rect(self.rect.left,self.rect.bottom - self.rect.top + c,current_bar_width,current_segment_height - 1))
          c += bar_segment_height
      
  def set_color(self,color):
    self.bar_color = color

  def set_percent(self,percent):
    self.percent = int(percent)

  def get_percent(self):
    return self.percent

  def __cmp__(self,other):
    if not other: return 0
    return cmp(self.percent,other.percent)


class BaseRenderBar():
  def __init__(self,progress_bar):
    ''' This is a render class for the PercentBar '''
    self.progress_bar = progress_bar
    self.background = 'slider_background'
    self.foreground = 'slider_foreground'
    theme_image_rect = theme.get_rect(self.foreground)

  def draw(self,image):
    ''' override me '''


class SliderRenderBar(BaseRenderBar):
  def draw(self,image):
    pbar = self.progress_bar
    max_bar_height     = pbar.rect.bottom - pbar.rect.top
    current_bar_width  = pbar.rect.right - pbar.rect.left
    current_bar_height = max_bar_height * pbar.percent / 100
    current_bar_top    = pbar.rect.bottom - current_bar_height
    bar_segment_height = max_bar_height / 10

    theme.blit(image,pbar.rect,self.background)
    theme_image_rect = theme.get_rect(self.foreground)
    image.blit(theme.surface,(pbar.rect.left,current_bar_top),Rect(
      theme_image_rect.left,
      theme_image_rect.top + theme_image_rect.height - current_bar_height,
      current_bar_width,
      current_bar_height))


class ScrollRenderBar(BaseRenderBar):
  def __init__(self,progress_bar):
    BaseRenderBar.__init__(self,progress_bar)
    self.background = 'scroll_background'
    self.min_handle_length = 60
    self.set_handle_length(0)

  def set_handle_length(self,length):
    if length < self.min_handle_length:
      self.handle_length = self.min_handle_length
    else:
      self.handle_length = length

  def draw(self,image):
    pbar = self.progress_bar
    half_handle_length = self.handle_length / 2
    max_bar_height     = pbar.rect.height - self.handle_length
    current_bar_width  = pbar.rect.right - pbar.rect.left
    handle_top         = max_bar_height * pbar.percent / 100
    if handle_top > max_bar_height: handle_top = max_bar_height
    if handle_top < 0: handle_top = 0
    current_bar_top    = pbar.rect.bottom - self.handle_length - handle_top

    theme.blit(image,pbar.rect,self.background)
    theme_image_rect = theme.get_rect(self.foreground)
    image.blit(theme.surface,(pbar.rect.left,current_bar_top),Rect(
      theme_image_rect.left,
      theme_image_rect.top,
      current_bar_width,
      half_handle_length))
    image.blit(theme.surface,(pbar.rect.left,current_bar_top+half_handle_length),Rect(
      theme_image_rect.left,
      theme_image_rect.bottom - half_handle_length,
      current_bar_width,
      half_handle_length))


class PercentBar(ProgressBar):
  def __init__(self, rect, percent=0):
    ''' Displays a graphical bar within a rectangle representing a positive integer 
    between 0 and 100, inclusive '''
    self.renderer   = SliderRenderBar(self)
    ProgressBar.__init__(self,
        rect,
        percent,
        segmented=False,
        horizontal=False)

  def set_renderer(self,new_renderer):
    self.renderer = new_renderer(self)

  def draw(self,image):
    if self.visible: self.renderer.draw(image)


class Slider(PercentBar):
  def __init__(self,rect, onclick_cb, percent=0):
    self.last_percent = None
    self.last_pos     = None
    self.jitter_threshold = 10 # consider this number +/- to not be motion
    PercentBar.__init__(
        self,
        rect,
        percent)
    self.onclick_cb = onclick_cb
    self.mousedown  = False
    self.selection_indicator = Button(theme.get_image('sel_indicator'),self._selection_indicator_callback)
    self.selection_indicator.rect.topleft = (-100,-100) # off screen at first

  def _selection_indicator_callback(self):
    ''' do nothing '''
    return

  def _calc_percent(self):
    (x,y) = pygame.mouse.get_pos()
    if y < self.rect.top: y = self.rect.top
    if y > self.rect.bottom: y = self.rect.bottom
    self.set_percent(100 * (self.rect.bottom - y) / self.rect.height)
    self.selection_indicator.rect.centery = y
    self.selection_indicator.rect.left = self.rect.left - self.selection_indicator.rect.width - 2

  def update(self):
    if not self.visible: return
    if not self.mousedown: return
    self._calc_percent()
    if self.mousedown and self.percent != self.last_percent and time.time() - self.mousedown_last_update > 0.5:
      self.last_percent = self.percent
      self.onclick_cb()
      self.mousedown_last_update = time.time()

  def is_idle(self):
    return not self.mousedown

  def handle_event(self,event):
    handled = False
    if not self.visible: return handled
    if event.type == MOUSEBUTTONDOWN and self.rect.collidepoint(pygame.mouse.get_pos()):
      self.mousedown_last_update = time.time()
      self.mousedown = True
    if self.mousedown: handled = True
    if self.mousedown and event.type == MOUSEMOTION:
      (x,y) = pygame.mouse.get_pos()
      if self.last_pos and (y > self.last_pos + self.jitter_threshold or y < self.last_pos - self.jitter_threshold):
        # don't run callback until motion has stopped. this prevents jerky animations.
        self.mousedown_last_update = time.time()
      self.last_pos = y
    if self.mousedown and event.type == MOUSEBUTTONUP:
      self.mousedown = False
      self._calc_percent()
      self.onclick_cb()
    return handled

  def draw(self,surface):
    if not self.visible: return
    PercentBar.draw(self,surface)
    if self.mousedown:
      self.selection_indicator.draw(surface)
      (x,y) = pygame.mouse.get_pos()
      if y < self.rect.top: y = self.rect.top
      if y > self.rect.top + self.rect.height: y = self.rect.top + self.rect.height
      font_surf = globals.gprint_ret("%s%%" % (self.percent,),32)
      font_x = self.rect.left - font_surf.get_rect().width
      font_y = y - self.selection_indicator.rect.height - font_surf.get_rect().height
      surface.blit(font_surf,(font_x,font_y))
    else:
      font_surf = globals.gprint_ret("%s%%" % (self.percent,),32)
      surface.blit(font_surf,(self.rect.centerx - (font_surf.get_rect().width / 2),self.rect.centery - (font_surf.get_rect().height / 2)))


class ScrollBar(Slider):
  def __init__(self,rect, onclick_cb, percent=0):
    Slider.__init__(self,rect, onclick_cb, percent=0)
    self.set_renderer(ScrollRenderBar)

  def _calc_percent(self):
    (x,y) = pygame.mouse.get_pos()
    handle_length = self.renderer.handle_length
    half_handle_length = handle_length / 2
    if y < self.rect.top + half_handle_length:
      y = self.rect.top + half_handle_length
    if y > self.rect.bottom - half_handle_length:
      y = self.rect.bottom - half_handle_length
    self.set_percent(100 * (self.rect.bottom - half_handle_length - y) / (self.rect.height - handle_length))
    self.selection_indicator.rect.centery = y
    self.selection_indicator.rect.left = self.rect.left - self.selection_indicator.rect.width - 2

  def set_handle_length(self,percent):
    length = percent * self.rect.height / 100
    self.renderer.set_handle_length(length)

  def update(self):
    if not self.mousedown: return
    self._calc_percent()
    if self.mousedown and self.percent != self.last_percent:
      self.last_percent = self.percent
      self.onclick_cb()

  def draw(self,surface):
    if not self.visible: return
    PercentBar.draw(self,surface)
    if self.mousedown:
      self.selection_indicator.draw(surface)


class Time(Text):
  def __init__(self,seconds):
    self.seconds  = seconds
    Text.__init__(self,globals.format_time(self.seconds))

  def __cmp__(self,other):
    if not other: return 0
    return cmp(self.seconds,other.seconds)


class CoverArt():
  def __init__(self,id,width,height,art_path):
    self.id     = id
    self.width    = width
    self.height   = height
    self.art_path = art_path
    self._load_image()

  def _load_image(self):
    print "art_path: " + self.art_path
    try:
      self.image = pygame.image.load(self.art_path)
    except:
      print "exception loading image, defaulting to UNKNOWN"
      self.image = pygame.image.load(globals.UNKNOWNIMAGE)

    self.image.set_colorkey((255,0,0), pygame.RLEACCEL)

    if self.image.get_width()>self.width:
      self.image=pygame.transform.scale(self.image, (self.width,self.height))
    elif self.image.get_width()<300:
      #scale to width of 300, keeping height in proportion
      self.image=pygame.transform.scale(self.image, (300,300 * self.image.get_height() / self.image.get_width()))
    else:
      self.width  = self.image.get_width()
      self.height = self.image.get_height()

    self.rect = self.image.get_rect()

