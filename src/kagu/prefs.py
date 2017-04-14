#!/usr/bin/env python

import os, ConfigParser
from manager import manager as manager

PREFSFILE = os.path.expanduser("~/.kagu/preferences")

#
#  Implements storage and retrieval of GMP preferences.
#
class Prefs:
  
  parser = None
  
  defaults = { 
    "continuous" : "True",
    "random"     : "False",
    "autoplay"   : "True",
    "headphone_sense" : "True",
    "sort_albums_by_year" : "False",
    "repeat"     : "False",
    "repeat_one" : "False",
    "sort"       : "0",
    "volume"     : "70",
    "theme"      : "default",
    "download_covers"        : "True",
    "download_hi_res_covers" : "2",
    "heuristic_covers"       : "False",
    "sleep_timer": "0",
    "player"     : "ossoplayer",
    "scrollbars" : "False",
    "now_playing_button_image" : "album",
  }
  
  #
  #  Instantiates a new Prefs with the options from STORE.
  #
  def __init__(self):
    self.parser = ConfigParser.SafeConfigParser(self.defaults)
    
    try:
      self.parser.read([PREFSFILE,])
    except StandardError:
      return
    
  #
  #  A convenience method for retrieving an option.
  #
  def get(self, option):
    return self.parser.get("DEFAULT", option)
    
  #
  #  A convenience method for retrieving an integer option.
  #
  def getInt(self, option):
    return int(self.parser.get("DEFAULT", option))
    
  #
  #  A convenience method for retrieving a boolean option.
  #
  def getBool(self, option):
    return self.parser.get("DEFAULT", option) == "True"
    
  #
  #  A convenience method for setting an option.
  #
  def set(self, option, value):
    self.parser.set("DEFAULT", option, value) 
    
  #
  #  Writes prefs to the specified file, defaulting to PREFSFILE.
  #
  def save(self, prefsFile=PREFSFILE):
    try:
      self.set("continuous", str(manager.playlist.continuous))
      self.set("random", str(manager.playlist.get_random()))
      self.set("autoplay", str(manager.playlist.get_autoplay()))
      self.set("headphone_sense", str(manager.get_headphone_sense()))
      self.set("sort_albums_by_year", str(manager.get_sort_albums_by_year()))
      self.set("repeat", str(manager.playlist.repeat))
      self.set("repeat_one", str(manager.playlist.repeat_one))
      self.set("volume", str(manager.player.volume))
      if manager.sleep_timer==0:
        self.set("sleep_timer", "0")
      else:
        self.set("sleep_timer", str(manager.sleep_timer_dur))
      self.set("player", manager.default_player)
      self.set("scrollbars", str(manager.scrollbar_state))
      self.set("now_playing_button_image", manager.nowplayingbuttonimage)
    except:
      print "prefs: exception accessing manager and friends"
  # do nothing    
    
    try:
      self.parser.write(open(prefsFile, "w"))
    except StandardError:
      return
      
#End of file
