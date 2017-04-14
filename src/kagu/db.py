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

import os, sqlite3
import globals


class DB():
  db_dir = None
  path = None
  con = None
  c = None

  def __init__(self):
    self.db_dir = globals.calc_db_dir()
    self.path = os.path.join(self.db_dir,'kagu.db')
    self.connect()

  def reconnect(self):
    self.close()
    self.connect()

  def connect(self):
    self.con = sqlite3.connect(self.path)
    self.con.row_factory = sqlite3.Row
    self.c   = self.con.cursor()
    self.c.execute('PRAGMA synchronous = OFF;')

  def close(self):
    self.con.close()
    self.con = None
    self.c   = None
    
  def get_db_dir(self):
    return self.db_dir

  def art_path_of_album(self,album_id):
    self.c.execute('''
      SELECT al.art_path AS art_path
        FROM album al
       WHERE al.id = ?
    ''', (album_id,))
    return self.c.fetchall()[0]['art_path']

  def art_path_of_artist(self,artist_id):
    self.c.execute('''
      SELECT ar.art_path AS art_path
        FROM artist ar
       WHERE ar.id = ?
    ''', (artist_id,))
    return self.c.fetchall()[0]['art_path']

  def artist_of_album(self,album_id):
    self.c.execute('''
      SELECT al.name AS album
           , ar.name AS artist
           , al.art_path AS art_path
        FROM album  al
        JOIN artist ar ON al.artist_id = ar.id
       WHERE al.id = ?
    ''', (album_id,))
    return self.c.fetchall()[0]['artist']

  def song_of_path(self,path):
    self.c.execute('''
      SELECT s.track     AS track
           , s.title     AS title
           , s.path      AS path
           , al.name     AS album
           , al.art_path AS art_path
           , s.length    AS length
           , ar.name     AS artist
           , al.id       AS album_id
           , s.flags     AS flags
           , ar.id       AS artist_id
           , s.year      AS year
           , g.name      AS genre
        FROM song s
             JOIN album  al ON s.album_id  = al.id
             JOIN artist ar ON s.artist_id = ar.id
             JOIN genre  g  ON s.genre_id  = g.id
       WHERE s.path = ?
    GROUP BY s.id
    ORDER BY s.track ASC
           , s.id ASC
    ''', (path,))
    return self.c.fetchall()

  def songs_of_paths(self,path_list):
    ''' given a list of song paths, return a list of dictionaries containing 
    data for those song paths. If a song doesn't exist in the DB, it simply isn't
    returned. '''
    songs = []
    for path in path_list:
      song_result = self.song_of_path(path)
      if song_result: songs.append(song_result[0])
    return songs

  def get_songs(self,album_id=None,artist_id=None):
    header = '''
      SELECT s.track AS track
           , s.title AS title
           , s.path  AS path
           , al.name     AS album
           , al.art_path AS art_path
           , ar.name AS artist
           , ar.id   AS artist_id
           , s.flags AS flags
           , al.id   AS album_id
        FROM song s
             JOIN album  al ON s.album_id  = al.id
             JOIN artist ar ON s.artist_id = ar.id
      '''
    footer = '''
    GROUP BY s.id
    ORDER BY ar.name ASC
           , al.name ASC
           , s.track ASC
           , s.id ASC
      '''
    if album_id != None:
      self.c.execute(header + '''
       WHERE al.id = ?
      ''' + footer, (album_id,))
    elif artist_id != None:
      self.c.execute(header + '''
       WHERE ar.id = ?
      ''' + footer, (artist_id,))
    else:
      self.c.execute(header + footer)
 
    return self.c.fetchall()

  def get_albums(self,artist_id=None,genre_id=None,sort_by='name'):
    header = '''
      SELECT DISTINCT al.name AS album
           , ar.name AS artist
           , al.art_path AS art_path
           , al.id AS album_id
           , ar.id  AS artist_id
        FROM album  al
        JOIN artist ar ON al.artist_id = ar.id
      '''
    if sort_by == 'year':
      footer = '''
      ORDER BY al.year ASC
             , ar.name ASC
             , al.name ASC
        '''
    else:
      footer = '''
      ORDER BY ar.name ASC
             , al.name ASC
        '''

    if artist_id != None:
      self.c.execute(header + '''
       WHERE ar.id = ?
      ''' + footer, (artist_id,))
    elif genre_id != None:
      self.c.execute(header + '''
       WHERE ar.genre_id = ?
      ''' + footer, (genre_id,))
    else:
      self.c.execute(header + footer)
    return self.c.fetchall()

  def get_m3us(self):
    header = '''
      SELECT id
           , name
           , path
        FROM m3u
      '''
    footer = '''
    ORDER BY name ASC
      '''

    self.c.execute(header + footer)
    return self.c.fetchall()

  def get_genres(self):
    header = '''
      SELECT id
           , name
        FROM genre
      '''
    footer = '''
    ORDER BY name ASC
      '''

    self.c.execute(header + footer)
    return self.c.fetchall()

  def m3u_exists(self, path):
    self.c.execute('''SELECT id FROM m3u WHERE path=?''', (path,))
    for row in self.c:
      return True
    return False

  def sync(self, status=True):
    if status==True:
      self.c.execute('PRAGMA synchronous = NORMAL;')
    else:
      self.c.execute('PRAGMA synchronous = OFF;')

  def insert_m3u(self,name,path):
    self.sync(True) # weird stuff happens if i don't do this, commit() maybe?
    self.c.execute('''
      INSERT INTO m3u (name,path) VALUES (?,?)
    ''',(name,path,))
    self.sync(False)

  def remove_m3u(self,path):
    self.sync(True)
    self.c.execute('''
      DELETE FROM m3u WHERE path=?
    ''',(path,))
    self.sync(False)

  def get_artists(self,genre_id=None):
    header = '''
      SELECT DISTINCT ar.name AS artist
           , ar.id   AS artist_id
        FROM artist ar
        JOIN album a ON ar.id=a.artist_id 
    '''

    footer = '''
    ORDER BY ar.name ASC
    '''

    if genre_id != None:
      self.c.execute(header + '''
       WHERE ar.genre_id = ?
      ''' + footer, (genre_id,))
    else:
      self.c.execute(header + footer)
    return self.c.fetchall()

  def get_album_art(self,album_id):
    self.c.execute('''
      SELECT aa.x AS x
           , aa.y AS y
        FROM album a
             JOIN album_art aa ON a.id = aa.album_id
       WHERE a.id = ?
    ''', (album_id,))
    return self.c.fetchall()

  def get_album_year(self,album_id):
    self.c.execute('''
      SELECT a.year AS year
        FROM album a
       WHERE a.id = ?
    ''', (album_id,))
    year = self.c.fetchall()[0]['year']
    return year

  def get_artist_art(self,artist_id):
    self.c.execute('''
      SELECT aa.x AS x
           , aa.y AS y
        FROM artist a
             JOIN artist_art aa ON a.id = aa.artist_id
       WHERE a.id = ?
    ''', (artist_id,))
    return self.c.fetchall()

  def get_theme_sprite(self,theme,sprite):
    self.c.execute('''
      SELECT *
        FROM theme_sprite ts
             JOIN theme_sprite_type tst ON ts.theme_id = tst.id
       WHERE tst.name = ?
         AND ts.name  = ?
    ''', (theme,sprite))
    return self.c.fetchall()[0]

  def get_theme_path(self,theme):
    self.c.execute('''
      SELECT path
        FROM theme_sprite_type tst
       WHERE tst.name = ?
    ''', (theme,))
    return self.c.fetchall()[0]['path']

db = DB()
