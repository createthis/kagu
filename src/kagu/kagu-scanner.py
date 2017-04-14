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

import sqlite3,os,mutagen,mutagen.easyid3,urllib,string,math,pygame,sys,time
import pygtk,gtk,gobject
from pygame.locals import *
import globals,prefs
if globals.ISMAEMO:
  import osso

from db      import db      as db
from theme   import theme   as theme

SCREENDEPTH = None

class DB():
  path = None
  con = None
  c = None

  def __init__(self,path):
    self.path = path
    
    do_create = not os.path.exists(self.path)

    self.con = sqlite3.connect(self.path)
    self.con.row_factory = sqlite3.Row
    self.c   = self.con.cursor()
    self.c.execute('PRAGMA synchronous = OFF;')
    if do_create:
      self.create_db()

  def _get_generic_id(self,table,name):
    valid_table_l = ['artist','album','genre']
    if not table in valid_table_l:
      assert None # paranoia
    for i in [0,1]: #only two iterations. If the first fails, the second should always succeed!
      self.c.execute('SELECT id FROM '+table+' WHERE name=?',(name,))
      for row in self.c:
        return row['id']
      # no rows if we made it here, so insert one
      self.c.execute('INSERT INTO '+table+' (name) VALUES (?)',(name,))
    assert None # Should never ever make it here, so blow up if we do

  def create_db(self):
    self.c.execute('''
      CREATE TABLE album (
        id        INTEGER NOT NULL UNIQUE PRIMARY KEY AUTOINCREMENT,
        name      VARCHAR NOT NULL,
        art_path  VARCHAR,
        artist_id INTEGER,
        genre_id  INTEGER,
        path      VARCHAR NOT NULL,
        year      INTEGER
      )
    ''')  
    self.c.execute('''
      CREATE INDEX album_name_path ON album (name, path)
    ''')
    self.c.execute('''
      CREATE INDEX album_year ON album (year)
    ''')
    self.c.execute('''
      CREATE INDEX album_genre ON album (genre_id)
    ''')
    self.c.execute('''
      CREATE INDEX album_artist ON album (artist_id)
    ''')
    
    self.c.execute('''
      CREATE TABLE artist (
        id          INTEGER NOT NULL UNIQUE PRIMARY KEY AUTOINCREMENT,
        name        VARCHAR NOT NULL,
        art_path    VARCHAR,
        genre_id    INTEGER
      )
    ''')
    self.c.execute('''
      CREATE INDEX artist_name ON artist (name)
    ''')
    self.c.execute('''
      CREATE INDEX artist_genre ON artist (genre_id)
    ''')
    
    self.c.execute('''
      CREATE TABLE song (
        id        INTEGER NOT NULL UNIQUE PRIMARY KEY AUTOINCREMENT,
        track     INTEGER,
        title     VARCHAR NOT NULL,
        length    REAL    NOT NULL,
        album_id  INTEGER NOT NULL,
        artist_id INTEGER NOT NULL,
        album_artist_id INTEGER NOT NULL,
        year      INTEGER,
        genre_id  INTEGER NOT NULL,
        path      VARCHAR NOT NULL,
        flags     INTEGER NOT NULL
      )
    ''')
    self.c.execute('''
      CREATE INDEX song_title     ON song (title)
    ''')
    self.c.execute('''
      CREATE INDEX song_album_id  ON song (album_id)
    ''')
    self.c.execute('''
      CREATE INDEX song_artist_id ON song (artist_id)
    ''')
    self.c.execute('''
      CREATE INDEX song_album_artist_id ON song (album_artist_id)
    ''')
    self.c.execute('''
      CREATE INDEX song_path ON song (path)
    ''')
    self.c.execute('''
      CREATE TABLE genre (
        id        INTEGER NOT NULL UNIQUE PRIMARY KEY AUTOINCREMENT,
        name      VARCHAR NOT NULL
      )
    ''')

    self.c.execute('''
      CREATE TABLE version (
        value     INTEGER NOT NULL
      )
    ''')
    self.c.execute('''
      INSERT INTO version (value) VALUES (''' + str(globals.DBVERSION) + ''')
    ''')

    self.c.execute('''
      CREATE TABLE album_art (
        album_id  INTEGER NOT NULL UNIQUE PRIMARY KEY,
        x         INTEGER NOT NULL,
        y         INTEGER NOT NULL
      )
    ''')

    self.c.execute('''
      CREATE TABLE artist_art (
        artist_id INTEGER NOT NULL UNIQUE PRIMARY KEY,
        x         INTEGER NOT NULL,
        y         INTEGER NOT NULL
      )
    ''')

    self.c.execute('''
      CREATE TABLE theme_sprite_type (
        id        INTEGER NOT NULL UNIQUE PRIMARY KEY AUTOINCREMENT,
        name      VARCHAR NOT NULL,
        path      VARCHAR NOT NULL
      )
    ''')

    self.c.execute('''
      INSERT INTO theme_sprite_type (name,path) VALUES ('default','data/sprites.png')
    ''')

    self.c.execute('''
      CREATE TABLE theme_sprite (
        id        INTEGER NOT NULL UNIQUE PRIMARY KEY AUTOINCREMENT,
        theme_id  INTEGER NOT NULL,
        name      VARCHAR NOT NULL,
        x         INTEGER NOT NULL,
        y         INTEGER NOT NULL,
        w         INTEGER NOT NULL,
        h         INTEGER NOT NULL
      )
    ''')

    self.c.execute('''
      CREATE INDEX theme_sprite_theme_id_and_name ON theme_sprite (theme_id,name)
    ''')
    
    self.c.execute('''
      CREATE TABLE m3u (
        id        INTEGER NOT NULL UNIQUE PRIMARY KEY AUTOINCREMENT,
        name      VARCHAR NOT NULL,
        path      VARCHAR NOT NULL
      )
    ''')

    self.c.execute('''
      CREATE INDEX m3u_name ON m3u (name)
    ''')
    
    self.c.execute('''
      CREATE INDEX m3u_path ON m3u (path)
    ''')
    
    self.update_theme()

  def update_theme(self):
    self.c.execute('''
      DELETE FROM theme_sprite
    ''')
    self.init_art_tables()
      
    default_theme_sprite_list = [
      {'name':'text_bg'           , 'x':  0, 'y':570, 'w':530, 'h': 79},
      {'name':'text_bg_sel'       , 'x':  0, 'y':651, 'w':530, 'h': 79},
      {'name':'albumartist_bg'    , 'x':  0, 'y':733, 'w':530, 'h':137},
      {'name':'albumartist_bg_sel', 'x':  0, 'y':874, 'w':530, 'h':137},
      {'name':'a2dp_on'           , 'x':176, 'y':488, 'w': 31, 'h': 43},
      {'name':'a2dp_off'          , 'x':208, 'y':488, 'w': 31, 'h': 43},
      {'name':'back_button'       , 'x':439, 'y':489, 'w': 39, 'h': 46},
      {'name':'exit_button'       , 'x':479, 'y':489, 'w': 39, 'h': 46},
      {'name':'background'        , 'x':  0, 'y':  0, 'w':800, 'h':480},
      {'name':'album_art_bg'      , 'x':703, 'y':490, 'w':125, 'h':160},
      {'name':'album_art_image'   , 'x':703, 'y':490, 'w':125, 'h':128},
      {'name':'album_art_ref'     , 'x':703, 'y':618, 'w':125, 'h': 32},
      {'name':'pause'             , 'x':  1, 'y':1014,'w': 54, 'h': 54},
      {'name':'play'              , 'x': 58, 'y':1014,'w': 54, 'h': 54},
      {'name':'next'              , 'x':115, 'y':1014,'w': 54, 'h': 54},
      {'name':'prev'              , 'x':172, 'y':1014,'w': 54, 'h': 54},
      {'name':'volume_bar_sel'    , 'x':157, 'y':521, 'w': 18, 'h': 11},
      {'name':'volume_bar'        , 'x':157, 'y':533, 'w': 18, 'h': 11},
      {'name':'repeat_off'        , 'x':312, 'y':487, 'w': 57, 'h': 42},
      {'name':'repeat_one'        , 'x':529, 'y':487, 'w': 57, 'h': 42},
      {'name':'repeat_all'        , 'x':587, 'y':487, 'w': 57, 'h': 42},
      {'name':'repeat_shuffle'    , 'x':255, 'y':487, 'w': 57, 'h': 42},
      {'name':'sel_indicator'     , 'x':529, 'y':530, 'w': 22, 'h': 24},
      {'name':'sel_indicator_down', 'x':552, 'y':530, 'w': 24, 'h': 22},
      {'name':'screen_off'        , 'x':587, 'y':530, 'w': 57, 'h': 42},
      {'name':'add_album'         , 'x':645, 'y':487, 'w': 57, 'h': 42},
#      {'name':'enqueue_mode'      , 'x':645, 'y':530, 'w': 57, 'h': 42},
      {'name':'clear_playlist'    , 'x':645, 'y':573, 'w': 57, 'h': 42},
      {'name':'delete_one'        , 'x':645, 'y':616, 'w': 57, 'h': 42},
      {'name':'volume'            , 'x':587, 'y':573, 'w': 57, 'h': 42},
      {'name':'menu'              , 'x':587, 'y':616, 'w': 57, 'h': 42},
      {'name':'view_caption_bg'   , 'x':703, 'y':652, 'w':125, 'h': 26},
      {'name':'slider_background' , 'x':704, 'y':680, 'w': 57, 'h':360},
      {'name':'slider_foreground' , 'x':762, 'y':680, 'w': 57, 'h':360},
      {'name':'scroll_background' , 'x':530, 'y':680, 'w': 57, 'h':360},
      {'name':'scroll_up'         , 'x':645, 'y':702, 'w': 57, 'h': 42},
      {'name':'scroll_down'       , 'x':645, 'y':745, 'w': 57, 'h': 42},
      {'name':'muted'             , 'x':645, 'y':659, 'w': 57, 'h': 42},
      {'name':'add'               , 'x':587, 'y':659, 'w': 57, 'h': 42},
      {'name':'remove'            , 'x':587, 'y':702, 'w': 57, 'h': 42},
      {'name':'checkbox_unchecked', 'x':530, 'y':573, 'w': 57, 'h': 42},
      {'name':'checkbox_checked'  , 'x':530, 'y':616, 'w': 57, 'h': 42},
      {'name':'delete_file'       , 'x':645, 'y':616, 'w': 57, 'h': 42},
      ]
    for row in default_theme_sprite_list:
      self.c.execute('''
        INSERT INTO theme_sprite (theme_id,name,x,y,w,h) VALUES (1,?,?,?,?,?)
        ''', (row['name'],row['x'],row['y'],row['w'],row['h']))

  def get_album_id(self,name,path,year,genre_id):
    for i in [0,1]: #only two iterations. If the first fails, the second should always succeed!
      self.c.execute('SELECT id FROM album WHERE name=? AND path=?',(name,path))
      for row in self.c:
        return row['id']
      # no rows if we made it here, so insert one
      self.c.execute('INSERT INTO album (name, path, year, genre_id) VALUES (?, ?, ?, ?)',(name,path,year,genre_id))
    assert None # Should never ever make it here, so blow up if we do
  
  def get_artist_id(self,artist,genre_id="Misc"):
    for i in [0,1]: #only two iterations. If the first fails, the second should always succeed!
      self.c.execute('SELECT id FROM artist WHERE name=?',(artist,))
      for row in self.c:
        return row['id']
      # no rows if we made it here, so insert one
      self.c.execute('INSERT INTO artist (name, art_path, genre_id) VALUES (?,?,?)',(artist,globals.UNKNOWNIMAGE,genre_id))
    assert None # Should never ever make it here, so blow up if we do
#    return self._get_generic_id('artist',artist)

  def insert_song(self,track,title,artist,album,album_artist,length,year,genre,path,flags):
    #print 'insert_song():\n\ttitle=%s\n\tartist=%s\n\talbum=%s\n\tlength=%s\n\tpath=%s' % \
    #    (title.encode('ascii','ignore'),artist.encode('ascii','ignore'),album.encode('ascii','ignore'),length,path.encode('ascii','ignore'))
    genre_id = self._get_generic_id('genre', genre)
    album_id  = self.get_album_id(album, os.path.dirname(path), year, genre_id)
    artist_id = self.get_artist_id(artist,genre_id)
    if album_artist == artist:
      album_artist_id = artist_id
    else:
      album_artist_id = self.get_artist_id(album_artist,genre_id)
    self.c.execute('''
      INSERT INTO song (track,title,length,album_id,artist_id,album_artist_id,year,genre_id,path,flags) VALUES (?,?,?,?,?,?,?,?,?,?)
    ''',(track,title,length,album_id,artist_id,album_artist_id,year,genre_id,path,flags))

  def get_album_paths(self):
    self.c.execute('''
      SELECT a.name AS album
           , s.path AS path
           , a.id   AS album_id
        FROM song s
             JOIN album a ON s.album_id=a.id
    GROUP BY s.album_id
    ''')
    return self.c.fetchall()

  def get_artist_list(self):
    self.c.execute('''
      SELECT name AS artist
           , id   AS artist_id
        FROM artist
    ''')
    return self.c.fetchall()

  def get_song_paths(self):
    self.c.execute('''
      SELECT id
           , path
           , album_id
        FROM song
    ''')
    return self.c.fetchall()

  def get_m3u_paths(self):
    self.c.execute('''
      SELECT id
           , path
        FROM m3u
    ''')
    return self.c.fetchall()

  def remove_song(self, song_id):
    self.c.execute('''
      DELETE FROM song WHERE id=?
      ''', (song_id,))

  def remove_m3u(self, m3u_id):
    self.c.execute('''
      DELETE FROM m3u WHERE id=?
      ''', (m3u_id,))

  def is_empty_album(self, album_id):
    self.c.execute('''
      SELECT s.id AS song_id
        FROM album a
             JOIN song s ON s.album_id=a.id
      WHERE a.id=? AND s.id IS NOT NULL LIMIT 1
    ''',(album_id,))
    for row in self.c:
      return False
    return True

  def remove_album(self, album_id):
    self.c.execute('''
      DELETE FROM album WHERE id=?
      ''', (album_id,))

  def set_song_album_artist_id(self,album_id,artist_id):
    self.c.execute('UPDATE song SET album_artist_id = ? WHERE album_id = ?',(artist_id,album_id))

  def set_album_artist_id(self,album_id,artist_id):
    self.c.execute('UPDATE album SET artist_id = ? WHERE id = ?',(artist_id,album_id))

  def set_album_art_path(self,album_id,path):
    self.c.execute('UPDATE album SET art_path = ? WHERE id = ?',(path,album_id))

  def set_artist_art_path(self,artist_id,path):
    self.c.execute('UPDATE artist SET art_path = ? WHERE id = ?',(path,artist_id))

  def set_artist_name(self,artist_id,name):
    self.c.execute('UPDATE artist SET name = ? WHERE id = ?',(name,artist_id))

  def set_album_name(self,album_id,name):
    self.c.execute('UPDATE album SET name = ? WHERE id = ?',(name,album_id))

  def set_song_flag(self,song_id,flag,remove=False):
    if not remove:
      self.c.execute('UPDATE song SET flags=flags | ? WHERE id = ?',(flag,song_id))
    else:
      self.c.execute('UPDATE song SET flags=flags & ~ ? WHERE id = ?',(flag,song_id))

  def init_art_tables(self):
    self.c.execute('''
      DELETE FROM album_art
    ''')
    self.c.execute('''
      DELETE FROM artist_art
    ''')

  def insert_album_art(self,album_id,x,y):
    self.c.execute('''
      REPLACE INTO album_art (album_id,x,y) VALUES (?,?,?)
    ''',(album_id,x,y))

  def insert_artist_art(self,artist_id,x,y):
    self.c.execute('''
      REPLACE INTO artist_art (artist_id,x,y) VALUES (?,?,?)
    ''',(artist_id,x,y))

  def insert_m3u(self,name,path):
    self.c.execute('''
      INSERT INTO m3u (name,path) VALUES (?,?)
    ''',(name,path))

  def is_compilation(self,album_id):
    ''' Does this album have more than one artist? '''
    self.c.execute('''
      SELECT s1.album_id
           , s1.artist_id
           , s2.artist_id
        FROM song s1
             JOIN song s2 ON s1.album_id = s2.album_id
       WHERE s1.artist_id != s2.artist_id
         AND s1.album_id = ?
    GROUP BY s1.album_id
    ''', (album_id,))
    for row in self.c:
      return 1
    return None

  def get_version(self):
    try:
      self.c.execute('''
      SELECT value FROM version LIMIT 1
      ''')
      for row in self.c:
        return int(row['value'])
    except:
      return 0
    return 0

  def song_of_path(self, path):
    self.c.execute('''
    SELECT id FROM song WHERE path = ? LIMIT 1
    ''', (path,))
    for row in self.c:
      return int(row['id'])
    return 0

  def m3u_of_path(self, path):
    self.c.execute('''
    SELECT id FROM m3u WHERE path = ? LIMIT 1
    ''', (path,))
    for row in self.c:
      return int(row['id'])
    return 0

  def artist_of_album(self,album_id):
    ''' return list of all artists associated with a given album '''
    artist_a = []

    # replace s.artist_id with s.album_artist_id and it won't work sometimes -disq
    # just tested and somehow it seems to work for me now, still not enabling -disq
    self.c.execute('''
      SELECT DISTINCT a.name AS name
                    , a.id   AS id
        FROM song s
             JOIN artist a ON s.album_artist_id = a.id
       WHERE s.album_id = ?
    ''', (album_id,))
#    print "q="+str(album_id)
    for row in self.c:
#      print "id="+str(row['id'])+" name="+str(row['name'])
      artist_a.append(row)
    return artist_a

  def consolidate_artist_names(self, cb_func=None):
    ''' fix dupe artists we created with set_artist_name '''
    self.c.execute('''
      SELECT id, name FROM artist
    ''')
    list = self.c.fetchall()
    removed = {}
    for row in list:
      artist_id     = row['id']
      artist_name   = row['name']
      
      try:
        if (removed[artist_id]==True):
#          print "DUPE, skipping artist #"+str(artist_id)
          continue
      except:
#        print "artist #"+str(artist_id)
        if cb_func:
          cb_func()


      self.c.execute('''
        SELECT id FROM artist WHERE id != ? AND name = ?
        ''', (artist_id, artist_name,))
      list2 = self.c.fetchall()
      for dupe in list2:
        print "replacing "+str(dupe['id'])+" with "+str(artist_id)+" ("+str(artist_name)+")"

        self.c.execute('''
          UPDATE album SET artist_id = ? WHERE artist_id = ?
          ''', (artist_id, dupe['id'],))
        self.c.execute('''
          UPDATE song SET artist_id = ? WHERE artist_id = ?
          ''', (artist_id, dupe['id'],))
        self.c.execute('''
          UPDATE song SET album_artist_id = ? WHERE album_artist_id = ?
          ''', (artist_id, dupe['id'],))
        self.c.execute('''
          DELETE FROM artist WHERE id = ?
          ''', (dupe['id'],))
        removed[dupe['id']]=True

  def consolidate_album_names(self, cb_func=None):
    ''' fix dupe albums we created with set_album_name '''
    self.c.execute('''
      SELECT id, name, path FROM album
    ''')
    list = self.c.fetchall()
    removed = {}
    for row in list:
      album_id     = row['id']
      album_name   = row['name']
      album_path   = row['path']
      
      try:
        if (removed[album_id]==True):
#          print "DUPE, skipping album #"+str(album_id)
          continue
      except:
#        print "album #"+str(album_id)
        if cb_func:
          cb_func()

      self.c.execute('''
        SELECT id FROM album WHERE id != ? AND name = ? AND path = ?
        ''', (album_id, album_name, album_path))
      list2 = self.c.fetchall()
      for dupe in list2:
        print "replacing "+str(dupe['id'])+" with "+str(album_id)+" ("+str(album_name)+")"

        self.c.execute('''
          UPDATE song SET album_id = ? WHERE album_id = ?
          ''', (album_id, dupe['id'],))
        self.c.execute('''
          DELETE FROM album WHERE id = ?
          ''', (dupe['id'],))
        removed[dupe['id']]=True


class Art():
  def __init__(self,name,width,height,art_path):
    self.name     = name
    self.width    = width
    self.height   = height
    self.art_path = art_path
    self.image    = pygame.Surface((self.width,self.height),0,theme.surface)
    theme.blit(self.image,(0,0),'album_art_image')
    self.__load_image()

  def __load_image(self):
#    print "art_path: " + self.art_path
    try:
      image = pygame.image.load(self.art_path)
    except:
      print "exception loading image, defaulting to UNKNOWN"
      image = pygame.image.load(globals.UNKNOWNIMAGE)

    image.set_colorkey((255,0,0), pygame.RLEACCEL)

    if not image.get_width()==self.width:
      image=pygame.transform.scale(image, (self.width,128))
    self.image.blit(image, (0,0))
    self.rect  = self.image.get_rect()


class NewSongProcessor:
  ignore_dir_l = ['.','..','maps']
  ext_l = ['.mp3','.ogg','.wma','.aac','.m4p','.m4a','.mp4','.m3u','.flac']
  m3u_to_ignore = [ '/home/user/.mediaplayer-engine/radiochannels.m3u' ]
  data_dir = None
  update_func = None
  tick_func = None
  last_audioscrobbler_query = 0
  
  def __init__(self,DB,data_dir,update_func,tick_func,prefs):
    self.DB = DB
    self.data_dir = data_dir
    self.update_func = update_func
    self.tick_func = tick_func
    self.tot_filecount = 0
    self.filecount = 0
    self.myprefs   = prefs

  def _get_mut_val(self,mut,name):
    if isinstance(mut, mutagen.mp4.MP4):
      return self._get_mut_val_mp4(mut, name)

    return self._get_mut_val_easyid3(mut, name)

  def _get_mut_val_easyid3(self,mut,name):
    ''' Sometimes we'll have a valid ID3 tag, but missing information.
    This method is responsible for how we handle these cases. '''
    try:
      if name == 'tracknumber':
        # usually track is '3', but sometimes '3/9'. deal with it.
        return mut[name][0].split("/")[0]
      else:
        return mut[name][0]
    except:
      if name == 'tracknumber' or name=='date':
        return None
      elif name == 'albumartist':
        return ''
      else:
        print "WARNING: no %s tag, will use UNKNOWN: %s" % (name,mut.filename)
        return 'UNKNOWN'

  def _get_mut_val_mp4(self,mut,name):
    try:
      if name == 'tracknumber':
        return mut['trkn'][0][0]
      elif name == 'title':
        return mut['\xa9nam'][0]
      elif name == 'artist':
        return mut['\xa9ART'][0]
      elif name == 'album':
        return mut['\xa9alb'][0]
      elif name == 'albumartist':
        return mut['aART'][0]
      elif name == 'genre':
        return mut['\xa9gen'][0]
      elif name == 'date':
        return mut['\xa9day'][0]
      else:
        return mut[name][0]
    except:
      if name == 'tracknumber' or name=='date':
        return None
      elif name == 'albumartist':
        return ''
      else:
        print "WARNING: no %s tag, will use UNKNOWN: %s" % (name,mut.filename)
        return 'UNKNOWN'


  def _fix_net_search_string(self, s):
    s = s.replace("_"," ")
    s = s.replace(":"," ")
    s = s.replace("?"," ")
    s = s.replace("/"," ")
    s = s.replace("-"," ")
    s = s.replace("~"," ")
    s = s.replace("["," ")
    s = s.replace("]"," ")
    s = s.replace("(1)","")
    s = s.replace("(2)","")
    s = s.replace("(3)","")
    s = s.replace("(4)","")
    return s

  def _fix_fs_filename(self, s):
    s = s.replace(":"," ")
    s = s.replace(";"," ")
    s = s.replace("&"," and ")
    s = s.replace("$"," ")
    s = s.replace("?"," ")
    s = s.replace("/"," ")
    s = s.replace("~"," ")
    s = s.replace("<"," ")
    s = s.replace(">"," ")
    s = s.replace("`"," ")
    s = s.replace("\\"," ")
    s = s.replace("  "," ")
    s = s.replace("  "," ")
    return s

  def _decode_xml(self, s):
    s = s.replace("&lt;","<")
    s = s.replace("&gt;",">")
    s = s.replace("&apos;","'")
    s = s.replace("&amp;","&")
    return s

  def deletedeleted(self):
    ''' Delete the now non-existent files from songs table '''
    list = self.DB.get_song_paths()
    listlen = len(list)

    modified_albums = {}

    c = 0
    for row in list:
      c = c + 1
      songid  = row['id']
      path    = row['path']
      albumid = row['album_id']

      if self.update_func:
        self.update_func(os.path.basename(path))
        if self.tick_func: self.tick_func(c * 100 / listlen)
        
      if not os.path.exists(path):
        print "removing track, file nonexistent: ",path
        self.DB.remove_song(songid)
        modified_albums[albumid]=True

    ak = modified_albums.keys()

    # check for each album to have at least one song assigned, if not remove the album    
    
    for albumid in ak:
      print "modified albumid: "+str(albumid)
      if self.DB.is_empty_album(albumid):
        print "removing album "+str(albumid)
        self.DB.remove_album(albumid)

    list = self.DB.get_m3u_paths()
    listlen = len(list)
    c = 0
    for row in list:
      c = c + 1
      m3uid  = row['id']
      path    = row['path']

      if self.update_func:
        self.update_func(os.path.basename(path))
        if self.tick_func: self.tick_func(c * 100 / listlen)
        
      if not os.path.exists(path):
        print "removing m3u, file nonexistent: ",path
        self.DB.remove_m3u(m3uid)


  def recurse(self,path,depth=0,scout=False):
    ''' This is the primary directory tree walking method.
    It calls self.add_file() as it descends. '''
    try:
      if depth == 0:
        if scout: self.tot_filecount = 0
        self.filecount = 0
      depth+=1
      if (os.path.exists(path) and depth < 32):
        for fn in os.listdir(path):
          if fn[0]=='.' and path!='/home/user/MyDocs': # ignore hidden dirs/files
            print 'Skipped file/dir:',fn,'in',path
            continue
        
          if fn.lower() in self.ignore_dir_l: # ignore these dirs
            continue

          cur_path = os.path.join(path,fn)
          #print "cur_path='"+cur_path+"'";
          (rootfn,ext) = os.path.splitext(fn)
          if ext.lower() in self.ext_l:
            self.filecount = self.filecount + 1
            if self.update_func: self.update_func(fn)
            if scout:
              self.tot_filecount = self.tot_filecount + 1
              if self.tick_func: self.tick_func()
            else:
              self.add_file(cur_path)
              if self.tick_func: self.tick_func(self.filecount * 100 / self.tot_filecount)

          elif os.path.isdir(cur_path):
            if os.path.islink(cur_path):
              pointsto = os.path.realpath(cur_path)
#              print cur_path+" is a link and points to "+pointsto
              if cur_path.find(pointsto)==0:
                print cur_path+" points to "+pointsto+", skipped to prevent recursion"
                continue
              cur_path = pointsto

            if cur_path in globals.get_no_path_list():
              print "skipped "+cur_path+", in ignore list"
              continue

            self.recurse(cur_path,depth,scout)
    except OSError, message:
      print "OSError:", message

  def add_file(self,path):
    (rootfn,ext) = os.path.splitext(path)
    if ext.lower() == '.m3u':
      self.add_m3u(path)
    else: self.add_song(path)

  def add_m3u(self,path):
    if self.DB.m3u_of_path(path)>0:
#      print "file exists in db, skipping: ",path
      return
    for ig in self.m3u_to_ignore:
      if path.find(ig)>-1:
        print "skipping m3u: ",path
        return
    (rootfn,ext) = os.path.splitext(path)
    name = os.path.basename(rootfn)
    self.DB.insert_m3u(name,path)

  def add_song(self,path):
    ''' This method is responsible for parsing ID3 headers 
    and sending ID3 info off to the DB class for storage '''
    
    if self.DB.song_of_path(path)>0:
#      print "file exists in db, skipping: ",path
      return
    
    try:
      mut = mutagen.File(path)
      length = mut.info.length
      if isinstance(mut, mutagen.mp3.MP3): # special mutagen case for MP3s
        mut = mutagen.easyid3.EasyID3(path)

      title       = self._get_mut_val(mut, 'title')
      artist      = self._get_mut_val(mut, 'artist')
      tracknumber = self._get_mut_val(mut, 'tracknumber')
      album       = self._get_mut_val(mut, 'album')
      albumartist = self._get_mut_val(mut, 'albumartist')
      genre       = self._get_mut_val(mut, 'genre')
      year        = self._get_mut_val(mut, 'date')
    except:
      print "WARNING: invalid or missing id3 header: ", path
      length      = 0
      title       = 'UNKNOWN'
      artist      = 'UNKNOWN'
      tracknumber = None
      album       = 'UNKNOWN'
      albumartist = ''
      year        = None
      genre       = 'UNKNOWN'

    try:
      if int(year)<1900 or year=='UNKNOWN':
        year = None
    except:
      year = None
    
    genre = genre.strip().title()
    if genre in ['Default', 'Other', 'Genre']:
      genre = 'Unknown'
    elif genre.find('General ')==0:
      genre = genre[len('General '):]
      
    flags = 0

    if title=='UNKNOWN' and artist!='UNKNOWN':
      flags = 1
      base = os.path.splitext(os.path.basename(path))[0].replace("_", " ")
      spl = base.split('-', 1) #maximum of 2 splits
      for i in xrange(0, len(spl)): spl[i]=spl[i].strip()
      if len(spl)!=2:
        title = base
      else:
        if spl[0].isdigit():
          if tracknumber==None: tracknumber = spl[0]
          title = spl[1]
        else:
          title = base
    elif title=='UNKNOWN' and artist=='UNKNOWN':
      flags = 1
      base = os.path.splitext(os.path.basename(path))[0].replace("_", " ")
      spl = base.split('-', 2) #maximum of 3 splits
      l = len(spl)
      for i in xrange(0, l): spl[i]=spl[i].strip()

      if l == 3:
        if spl[0].isdigit():
          tracknumber   = spl[0]
          artist        = spl[1]
          title         = spl[2]
        elif spl[1].isdigit():
          artist        = spl[0]
          tracknumber   = spl[1]
          title         = spl[2]
        else:
          artist        = spl[0]
          title         = str(spl[1])+" - "+str(spl[2])
      elif l == 2:
        if spl[0].isdigit():
          tracknumber   = spl[0]
          title         = spl[1]
        else:
          artist        = spl[0]
          title         = spl[1]
      else:
          title         = base
          
    if album == 'UNKNOWN':
      tmp = os.path.basename(os.path.dirname(path)).strip()
      if tmp!='': album = tmp

    # tags are sometimes messy, try to fix -disq
    album   = album .replace("  ", " ")
    album   = album .replace("  ", " ")
    artist  = artist.replace("  ", " ")
    artist  = artist.replace("  ", " ")
    title   = title .replace("  ", " ")
    title   = title .replace("  ", " ")
    albumartist = albumartist.replace("  ", " ")
    albumartist = albumartist.replace("  ", " ")
    
    if albumartist == "":
      albumartist=artist
#    else:
#      print "album="+str(album)+" artist="+str(artist)+" albumartist="+str(albumartist)
#      print "*****"
                                            
    self.DB.insert_song(
      tracknumber,
      title.strip(),
      artist.strip().title(),
      album.strip().title(),
      albumartist.strip().title(),
      length,
      year,
      genre,
      path,
      flags
    );

  def get_album_covers(self,album_cache_fn,overwrite=False,skipdownload=False):
    global SCREENDEPTH

    download_covers  = False if self.myprefs.get('download_covers')        == "False" else True
    download_hi_res  = False if self.myprefs.get('download_hi_res_covers') == "0"     else True
    heuristic_covers  = False if self.myprefs.get('heuristic_covers')        == "False" else True
    
    if skipdownload==True: download_covers = False
    
    width,height,x,y = 125,128,0,0
    list = self.DB.get_album_paths()
    num_albums = len(list)+1
    num_albums_per_side = int(math.ceil(math.sqrt(num_albums)))
    cache_image = pygame.Surface((width * num_albums_per_side,height * num_albums_per_side))

    album_art = Art("",width,height,globals.UNKNOWNIMAGE)
    cache_image.blit(album_art.image, (x,y),album_art.rect)
    x = x + width

    c = 1
    for row in list:
      c = c + 1
      dir   = os.path.dirname(row['path'])

      # ugly hack to prevent the exception in posixpath.py on apt installs -disq
      try:
        os.path.exists(dir)
      except:
        print "WARNING: exception in os.path.exists - hack in place"
        dir = dir.encode('ascii', 'ignore')
      
      album = row['album']
      album_id = row['album_id']

      if self.update_func:
        self.update_func(album)
        if self.tick_func: self.tick_func(c * 100 / num_albums)

      list_of_artists = self.DB.artist_of_album(album_id)
      
#      print "album id = "+str(album_id)+" len="+str(len(list_of_artists))

      if len(list_of_artists)>1:
#      if False:
        compilation_album = True
        artist = "Various Artists"
        vaid = self.DB.get_artist_id(artist)
        self.DB.set_album_artist_id(album_id, vaid)
        self.DB.set_song_album_artist_id(album_id, vaid)
        self.DB.insert_artist_art(vaid,0,0)
      else:
        compilation_album = False
        artistrow = list_of_artists[0]
        self.DB.set_album_artist_id(album_id, artistrow['id'])
        artist = artistrow['name']

      art_path = self.get_existing_cover(dir)
      newtitle = ""
      if not art_path: (art_path, newtitle) = self.get_net_album_cover_info(artist,album,dir,download_covers,download_hi_res,compilation_album,overwrite=overwrite,heuristic=heuristic_covers)
#      if not art_path: art_path = globals.UNKNOWNIMAGE

      if newtitle!="": self.DB.set_album_name(album_id, newtitle)

      if not art_path:
        self.DB.set_album_art_path(album_id, globals.UNKNOWNIMAGE)
        self.DB.insert_album_art(album_id,0,0)
        continue

      self.DB.set_album_art_path(album_id,art_path)
      album_art = Art(album,width,height,art_path)
      self.DB.insert_album_art(album_id,x,y)
      cache_image.blit(album_art.image, (x,y),album_art.rect)
      x = x + width
      if x > cache_image.get_rect().width - width:
        x = 0
        y = y + height
    cache_image_conv = cache_image.convert(SCREENDEPTH)
    pygame.image.save(cache_image_conv,album_cache_fn)

  def get_existing_cover(self,dir):
    for fn in ('folder.jpg','cover.jpg'):
      path = os.path.join(dir,fn)
      if os.path.exists(path):
        return path
    return None # nothing found

  def get_net_album_cover_info(self, artist, album, dir, really_download, download_hi_res, compilation_album=False, overwrite=False, heuristic=False):
    cover_dir = os.path.join(self.data_dir,'covers')
    if not os.path.exists(cover_dir): os.mkdir(cover_dir)
    fn=os.path.join(cover_dir,self._fix_fs_filename(artist.encode('ascii','ignore')+'_'+album.encode('ascii','ignore')+'.jpg'))
    if not overwrite and os.path.exists(fn):
      return fn, "" # file already exists...
    elif overwrite: print "overwriting album covers (AS)"

    if not really_download:
      return False, ""

    searchString='"'+album+'"'
    searchAltString=album
    
    if fn.find("NOARTIST") != -1 or fn.find("UNKNOWN") != -1: # ignore these
      return False, ""

    if not compilation_album:
      searchString=searchString+ ' '+ artist
      searchAltString=searchAltString+ ' OR '+ artist

    (asret, newtitle) = self.retrieve_image_from_AudioScrobbler(artist, album, fn, download_hi_res)
    if asret:
      return fn, newtitle

    # saw this in two seperate occasions, audioscrobbler omits the "-" in album names i think -disq
    tmp = album .replace("-",   " ")
    tmp = tmp   .replace("  ",  " ")
    tmp = tmp   .replace("  ",  " ")

    (asret, newtitle2) = self.retrieve_image_from_AudioScrobbler(artist, tmp, fn, download_hi_res)
    if asret:
      return fn, newtitle2
      
    if newtitle2!="": newtitle=newtitle2

    if not heuristic:
      try:
        os.unlink(fn)
      except:
        pass
      return False, newtitle

    if overwrite and os.path.exists(fn): # only overwrite AS covers
      return fn, newtitle
    
    if self.retrieve_image_from_MSN(searchString + " (cd OR cover)",fn):
      return fn, newtitle
    if self.retrieve_image_from_MSN(searchAltString + " (cd OR cover)",fn):
      return fn, newtitle
    if self.retrieve_image_from_Yahoo(string.replace(artist+" "+ album," "," OR ")+ " OR cd",fn):
      return fn, newtitle
    return False, newtitle

  def retrieve_image_from_Yahoo(self, search_string, filename):
    print "Yahoo DL: "+filename.encode('ascii','ignore')
    urladdress="http://images.search.yahoo.com/search/images?"
    imageSearch = self._fix_net_search_string(search_string)
    params = {'p':imageSearch.encode('ascii', 'ignore')}

    txdata = urllib.urlencode(params)
    urladdress=urladdress+txdata+"&ei=UTF-8"
    #print "opening" + urladdress
    found=False
    try:
        sock = urllib.urlopen(urladdress)
        htmlSource = sock.read()
    except:
        print "unable to get socket"
        print sys.exc_info()[0]
        return False
    try:
        imagelocationStart=htmlSource.find('Go to fullsize image')+28
        if (imagelocationStart>28):
            imagelocationend=htmlSource.find('"',imagelocationStart)
            imagelocation=htmlSource[imagelocationStart:imagelocationend]
            urllib.urlretrieve(imagelocation, filename)
            found=True
        else:
            print "invalid image..."

        sock.close()
        return found
    except:
        print "Problem saving file:" + filename
        print sys.exc_info()[0]
        return False

  def retrieve_image_from_MSN(self, search_string, filename):
    print "MSN DL: "+filename.encode('ascii','ignore')
    urladdress="http://search.msn.com/images/results.aspx?"
    imageSearch = self._fix_net_search_string(search_string)
    params = {'q':imageSearch.encode('ascii', 'ignore')}

    txdata = urllib.urlencode(params)
    urladdress=urladdress+txdata+"&FORM=QBIR"
    #print "opening" + urladdress
    found=False
    try:
        sock = urllib.urlopen(urladdress)
        htmlSource = sock.read()
    except:
        print "unable to get socket"
        print sys.exc_info()[0]
        return False
    try:
        imagelocationStart=htmlSource.find('thumbnail')-52
        imagelocationStart=htmlSource.find('src="',imagelocationStart)+5
        #print imagelocationStart
        if (imagelocationStart>28):
            imagelocationend=htmlSource.find('"',imagelocationStart)
            imagelocation=htmlSource[imagelocationStart:imagelocationend]
            urllib.urlretrieve(imagelocation, filename)
            found=True
        else:
            print "invalid image..."

        sock.close()
        return found
    except:
        print "Problem saving file:" + filename
        print sys.exc_info()[0]
        return False

  def _encode_string(self, str):
#    print "to encode: "+str
    encoded = urllib.urlencode({'dummy':str})
    result = encoded[encoded.find('dummy=')+6:]
#    print "encoded: "+result
    return result

  def retrieve_image_from_AudioScrobbler(self, artist, album, filename, download_hi_res):
    ti = int(time.time())

    # no more than one query per sec
    if (self.last_audioscrobbler_query>0) and (self.last_audioscrobbler_query>=ti):
      print "flood protection: skip AS"
      return False, ""

    self.last_audioscrobbler_query = ti

    try:
      print "AS DL: "+filename.encode('ascii','ignore')
      urladdress="http://ws.audioscrobbler.com/1.0/album/"
      urladdress=urladdress + self._encode_string(artist) + "/" + self._encode_string(album) + "/info.xml"
#       print "opening " + urladdress
    except:
      print "AS: exception in url builder"
      return False, ""

    found=False
    try:
        sock = urllib.urlopen(urladdress)
        htmlSource = sock.read()
    except:
        print "unable to get socket"
        print sys.exc_info()[0]
        return False, ""
    
    newTitle = ""
    try:
      for i in [0,1]:
        size    = '<large>'  if download_hi_res else '<medium>'
        sizeend = '</large>' if download_hi_res else '</medium>'
        imagelocationStart=htmlSource.find('<coverart>') + 10
        imagelocationStart=htmlSource.find(size, imagelocationStart) + len(size)
        if (imagelocationStart>10+len(size)):
            imagelocationend=htmlSource.find(sizeend,imagelocationStart)
            imagelocation=self._decode_xml(htmlSource[imagelocationStart:imagelocationend])
            if imagelocation.find('/noimage/')>0:
              print 'album cover not found in AS'
            else:
              urllib.urlretrieve(imagelocation, filename)
              if os.stat(filename).st_size < 1024 and download_hi_res==True:
                download_hi_res = False
                try:
                  os.unlink(filename)
                except:
                  pass
                continue
              
              found=True
              break
        else:
            print "cover art for artist/album pair not found in AS"
            break

      tagStart=htmlSource.find('<album ')
      if (tagStart>0):
        tagEnd=htmlSource.find(">", tagStart+6)
        tag=htmlSource[tagStart+6:tagEnd]
        titleStart=tag.find('title="')
        if titleStart>=0:
          titleEnd=tag.find('"', titleStart+7)
          newTitle=self._decode_xml(tag[titleStart+7:titleEnd])
          print "newtitle="+str(newTitle)

      sock.close()
      return found, newTitle
    except:
        print "Problem saving file:" + filename
        print sys.exc_info()[0]
        return False, ""

  def get_artist_images(self,artist_cache_fn,overwrite=False,skipdownload=False):
    global SCREENDEPTH
    
    download_covers  = False if self.myprefs.get('download_covers')        == "False" else True
    width,height,x,y = 125,128,0,0

    if skipdownload==True: download_covers = False

    list = self.DB.get_artist_list()

    num_artists = len(list)+1
    num_artists_per_side = int(math.ceil(math.sqrt(num_artists)))
    cache_image = pygame.Surface((width * num_artists_per_side,height * num_artists_per_side))

    cover_dir = os.path.join(self.data_dir,'covers')
    if not os.path.exists(cover_dir): os.mkdir(cover_dir)

    if overwrite: print "overwriting artist images"

    artist_art = Art("",width,height,globals.UNKNOWNIMAGE)
    cache_image.blit(artist_art.image, (x,y),artist_art.rect)
    x = x + width

    listlen = len(list)

    c = 1
    for row in list:
      c = c + 1
      artist = row['artist']
      artist_id = row['artist_id']

      if self.update_func:
        self.update_func(artist)
        if self.tick_func: self.tick_func(c * 100 / listlen)

      fn=os.path.join(cover_dir,self._fix_fs_filename(artist.encode('ascii','ignore')+'.jpg'))

      new_artistname = ""
      if download_covers:
        if overwrite or not os.path.exists(fn):
          new_artistname = self.retrieve_artist_from_AudioScrobbler(artist, fn)

      if new_artistname!="":
        print "new="+str(new_artistname)+" id="+str(artist_id)+" old="+str(artist)
        self.DB.set_artist_name(artist_id, new_artistname)

      if not os.path.exists(fn):
        self.DB.set_artist_art_path(artist_id, globals.UNKNOWNIMAGE)
        self.DB.insert_artist_art(artist_id,0,0)
        continue

      self.DB.set_artist_art_path(artist_id, fn)
      artist_art = Art(artist,width,height,fn)
      self.DB.insert_artist_art(artist_id,x,y)
      cache_image.blit(artist_art.image, (x,y),artist_art.rect)
      x = x + width
      if x > cache_image.get_rect().width - width:
        x = 0
        y = y + height

    cache_image_conv = cache_image.convert(SCREENDEPTH)
    pygame.image.save(cache_image_conv,artist_cache_fn)


  def retrieve_artist_from_AudioScrobbler(self, artist, filename):
    ti = int(time.time())

    # no more than one query per sec
#    if (self.last_audioscrobbler_query>0) and (self.last_audioscrobbler_query>=ti):
#      print "flood protection: skip AS2"
#      return ""

#    self.last_audioscrobbler_query = ti

    try:
#      print "AS2 DL: "+filename.encode('ascii','ignore')
      urladdress="http://ws.audioscrobbler.com/1.0/artist/"
      urladdress=urladdress + self._encode_string(artist) + "/similar.xml"
#       print "opening " + urladdress
    except:
      print "AS2: exception in url builder"
      return ""

    artistname = ""
    try:
        sock = urllib.urlopen(urladdress)
        htmlSource = sock.read()
    except:
        print "unable to get socket"
        print sys.exc_info()[0]
        return ""
    try:
        tagStart=htmlSource.find('<similarartists')
        if (tagStart>0):
            tagEnd=htmlSource.find(">", tagStart+15)
            tag=htmlSource[tagStart+15:tagEnd]
            
            imageStart=tag.find(' picture="')
            imagelocation=""
            if (filename!="") and (imageStart>=0):
              imageEnd=tag.find('"', imageStart+10)
              imagelocation=self._decode_xml(tag[imageStart+10:imageEnd])
              if imagelocation.find('/noimage/')>0:
                print 'artist image not found in AS'
              else:
#                print "imageloc="+imagelocation
                urllib.urlretrieve(imagelocation, filename)

            arStart=tag.find(' artist="')
            if (arStart>=0):
              arEnd=tag.find('"', arStart+9)
              artistname=self._decode_xml(tag[arStart+9:arEnd])
              print "artistname="+artistname
        else:
            print "artist not found in AS"

        sock.close()
        return artistname
    except:
        print "Problem saving file:" + filename
        print sys.exc_info()[0]
        return ""


class Scanner():
  global theme

  def quit(self, something=None, data=None):
    if data!=None:
      exitcode=int(data)
    else:
      exitcode=0      

    sys.exit(exitcode)

  def checkbox_update(self, wid):
    tmp = wid.get_active()
    self.cbox_hires.set_sensitive(tmp)
    self.cbox_heuristic.set_sensitive(tmp)

  def are_you_sure_dialog(self):
    default_download = False if self.myprefs.get('download_covers')        == "False" else True
    heuristic_covers = False if self.myprefs.get('heuristic_covers')        == "False" else True
    download_hi_res_str  = self.myprefs.get('download_hi_res_covers')
    download_hi_res  = False if download_hi_res_str == '0' else True
    if download_hi_res_str == '2': self.overwrite=True

    dialog = gtk.Dialog("Scan for music", self.window, 0, (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT, gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT))
    dialog.set_default_response(gtk.RESPONSE_ACCEPT)
    
    label = gtk.Label("    Would you like to scan your device for music?    ") #fixme: ugly
    dialog.vbox.pack_start(label, False, True, 15)

    cbox = gtk.CheckButton("Download album covers from the net")
    dialog.vbox.pack_start(cbox, False, True, 0)
    cbox.set_active(default_download)

    cbox2 = gtk.CheckButton("High resolution album covers")
    dialog.vbox.pack_start(cbox2, False, True, 0)
    cbox2.set_active(download_hi_res)
    self.cbox_hires=cbox2

    cbox4 = gtk.CheckButton("Heuristic cover search")
    dialog.vbox.pack_start(cbox4, False, True, 0)
    cbox4.set_active(heuristic_covers)
    self.cbox_heuristic=cbox4

    cbox.connect("toggled", self.checkbox_update)
    self.checkbox_update(cbox)

    cbox3 = gtk.CheckButton("Force a full scan")
    dialog.vbox.pack_start(cbox3, False, True, 0)
    cbox3.set_active(False)

    dialog.vbox.show_all()
    if dialog.run() != gtk.RESPONSE_ACCEPT:
      dialog.destroy()
      self.quit()
    
    dl = cbox.get_active()
    dl2 = cbox2.get_active()
    dl3 = cbox3.get_active()
    dl4 = cbox4.get_active()

    dialog.destroy()
    self.myprefs.set('download_covers', str(dl))
    self.myprefs.set('heuristic_covers', str(dl4))
    if dl2 == True: self.myprefs.set('download_hi_res_covers', '1')
    else:           self.myprefs.set('download_hi_res_covers', '0')
    
    self.heuristic_covers = dl4

    self.myprefs.save()
    if dl2 != download_hi_res: self.overwrite = True
    if dl3 == True:
      self.fullscan  = True
      self.overwrite = True
    else:
      if dl == False:
        self.overwrite = False
    return dl


  def completed_dialog(self):
    dialog = gtk.Dialog("Scan complete", self.window, 0, (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
    dialog.set_default_response(gtk.RESPONSE_ACCEPT)
    
    label = gtk.Label("   Succesfully finished scanning your music collection.   \n   Now run Kagu Media Player to listen.   ") #fixme: ugly
    dialog.vbox.pack_start(label, False, True, 15)

    cbox = gtk.CheckButton("Run Kagu now")
    dialog.vbox.pack_start(cbox, False, True, 0)
    cbox.set_active(True)

    dialog.vbox.show_all()
    dialog.run()
    dl = cbox.get_active()
    dialog.destroy()
    return dl
    
  def notify(self, text):
    if self.batch_mode:
      print text
    else:
      self.pbarlabel.set_text(text)
      self.scan_tick()

  def __init__(self, update_theme=False, batch_mode=False):
    global theme

    if update_theme==True:
      batch_mode=True
    self.batch_mode = batch_mode

    if not self.batch_mode:
      if globals.ISMAEMO:
        import hildon
        self.app = hildon.Program()
        self.window = hildon.Window()
      else:
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)

      self.window.set_title("kagu scanner")
      self.window.connect("destroy", self.quit)

      if globals.ISMAEMO: self.app.add_window(self.window)

      self.pbar = gtk.ProgressBar()
      self.pbarlabel = gtk.Label("Ready to scan...")
      self.commentlabel = gtk.Label()

      vbox = gtk.VBox(False, 0)
      vbox.pack_start(self.pbarlabel, False, False, 0)
      vbox.pack_start(self.pbar, False, False, 0)
      vbox.pack_start(self.commentlabel, False, False, 0)
      self.window.add(vbox)

      self.window.show_all()
      self.scan_tick()

    self.myprefs = prefs.Prefs()
    self.overwrite = False
    self.fullscan  = False
    self.heuristic_covers = True

    self.db_dir = globals.calc_db_dir()

    if not self.batch_mode:
      self.are_you_sure_dialog()
      self.notify("Preparing...")

    if not update_theme:
      if self.fullscan:
        try:
          os.unlink(os.path.join(self.db_dir, 'kagu.db'))
        except:
          print "nothing to unlink"

    self.path_a = globals.get_path_list()
    self.mydb = DB(os.path.join(self.db_dir, 'kagu.db'))
    self.mydb.con.commit()

    db.reconnect()

    theme.set_theme(self.myprefs.get('theme'),False)
    globals.MAINFONTCOLOR   = theme.surface.get_at((93,512))
    globals.MAINFONTBGCOLOR = theme.surface.get_at((40,582))

    if update_theme:
      print "Updating theme table"
      self.mydb.update_theme()
      self.sp=NewSongProcessor(self.mydb, self.db_dir, None, None, self.myprefs)
      print "Updating artist cache"
      self.sp.get_artist_images(os.path.join(self.db_dir, 'artist_cache.tga'),skipdownload=True)
      print "Updating album cache"
      self.sp.get_album_covers(os.path.join(self.db_dir, 'album_cache.tga'),skipdownload=True)
      self.mydb.con.commit()
      print "Done"
      self.quit()
    else:
      self.sp=NewSongProcessor(self.mydb, self.db_dir, self.scan_update, self.scan_tick, self.myprefs)

    self.notify("Scanning...")

    os.nice(5)

    self.notify("Checking for missing music")
    self.sp.deletedeleted()

    for path in self.path_a: # scan for music
      if os.path.exists(path):
        self.notify("Looking for files in " + path)
        self.sp.recurse(path,0,True)
        self.notify("Reading ID3 tags from " + path)
        self.sp.recurse(path)
        self.mydb.con.commit()

    self.mydb.init_art_tables()

    if self.myprefs.get('download_covers') == "True":
      self.notify("Downloading artist images...")
    else:
      self.notify("Reading artist images...")

    self.sp.get_artist_images(os.path.join(self.db_dir, 'artist_cache.tga'),overwrite=self.overwrite)

    self.notify("Consolidating duplicate artists...")
    self.mydb.consolidate_artist_names(cb_func=self.scan_tick)

    self.notify("Consolidating duplicate albums...")
    self.mydb.consolidate_album_names(cb_func=self.scan_tick)

    if self.myprefs.get('download_covers') == "True":
      self.notify("Downloading album covers...")
    else:
      self.notify("Reading album covers...")

    self.sp.get_album_covers(os.path.join(self.db_dir, 'album_cache.tga'),overwrite=self.overwrite)

    self.scan_update("")
    self.notify("Completed")
    self.mydb.con.commit()

    if not self.batch_mode and self.completed_dialog():
      print "will launch kagu"
      self.quit(data=20)

    self.quit()


  def scan_update(self, fn):
    if self.batch_mode:
      return
    if fn:
      self.commentlabel.set_text(fn)
      self.pbar.pulse()    


  def scan_tick(self,percent=None):
    if self.batch_mode:
      return
    if percent: self.pbar.set_fraction(percent/100.0)
    while gtk.events_pending():
      gtk.main_iteration()


def init_pygame():
  global SCREENDEPTH
  SCREENRECT = Rect(0, 0, 800, 480)
  os.environ["SDL_VIDEO_X11_WMCLASS"]="kaguscanner"
  pygame.init()
  if not globals.ISMAEMO:
    SCREENDEPTH = pygame.display.mode_ok(SCREENRECT.size, 0, 32)
  else:
    SCREENDEPTH = pygame.display.mode_ok(SCREENRECT.size, 0, 16)

def main():
  update_theme = False
  batch_mode = False
  
  argc = len(sys.argv)
  if argc==2 and sys.argv[1]=="--update-theme":
    print "Theme update mode"
    update_theme = True
  elif argc==2 and (sys.argv[1]=="--batch-mode" or sys.argv[1]=="-y"):
    print "Batch mode"
    batch_mode = True
  elif argc==2 and sys.argv[1]=="--delete-db":
    print "Deleting db"
    try:
      os.unlink(os.path.join(globals.calc_db_dir(), 'kagu.db'))
    except:
      print "nothing to unlink"
    sys.exit(0)

  db_dir = globals.calc_db_dir()
  mydb = DB(os.path.join(db_dir, 'kagu.db'))
  mydb.con.commit()
  db.reconnect()
  wiped_db = False
  if mydb.get_version()!=globals.DBVERSION:
    print "db version != "+str(globals.DBVERSION)+", wiping db"
    try:
      wiped_db = True
      os.unlink(os.path.join(db_dir, 'kagu.db'))
    except:
      print "nothing to unlink"

  if argc==2 and sys.argv[1]=="--install":
    print "Install mode"
    if wiped_db == False:
      update_theme = True
    else:
      sys.exit(0)
  elif update_theme==False and batch_mode==False and (argc>1 or (argc==2 and (sys.argv[1]=="--help" or sys.argv[1]=="-h"))):
    print "kagu-scanner [--update-theme] [--delete-db] [--install] [--batch-mode|-y]"
    return

  init_pygame()

  # initiate connection
  if update_theme == False and batch_mode == False and globals.ISMAEMO:
    osso_rpc = osso.Rpc(globals.osso_c)
    osso_rpc.rpc_run("com.nokia.icd", "/com/nokia/icd", "com.nokia.icd", "connect", (str(""),int(1),), wait_reply = False)

  Scanner(update_theme, batch_mode)

if __name__ == '__main__': main()
