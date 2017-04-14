#!/usr/bin/python

import sys
try:
 	import pygtk
  	pygtk.require("2.0")
except:
  	pass
try:
	import gtk
  	import gtk.glade
except:
	sys.exit(1)



class KaguGTK:
	"""This is the KaguGTK application"""

	def __init__(self):
		
		#Set the Glade file
		self.gladefile = "kagu-gtk.glade"  
	        self.wTree = gtk.glade.XML(self.gladefile) 
		
		#Get the Main Window, and connect the "destroy" event
		self.window = self.wTree.get_widget("MainWindow")
		if (self.window):
			self.window.connect("destroy", gtk.main_quit)

if __name__ == "__main__":
	hwg = KaguGTK()
	gtk.main()
