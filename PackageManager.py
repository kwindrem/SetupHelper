#!/usr/bin/env python

#	PackageManager.py
#	Kevin Windrem
#
#
# This program is responsible for
#	downloading, installing and unstalling packages
# 	package monitor also checks SD cards and USB sticks for package archives
#		either automatically or manually via the GUI
#	providing the user with status on installed packages and any updates via the GUI
#
# It runs as /service/PackageManager
#
# Persistent storage for packageManager is stored in dbus Settings:
#
#	com.victronenergy.Settings parameters for each package:
#		/Settings/PackageMonitor/n/PackageName		can be edited by the GUI only when adding a new package
#		/Settings/PackageMonitor/n/GitHubUser		can be edited by the GUI
#		/Settings/PackageMonitor/n/GitHubBranch		can be edited by the GUI
#		/Settings/PackageMonitor/Count				the number of ACTIVE packages (0 <= n < Count)
#		/Settings/PackageMonitor/Edit/...			GUI edit package set
#
#		/Settings/PackageMonitor/GitHubAutoDownload 	set by the GUI to control automatic updates from GitHub
#			0 - no GitHub auto downloads (version checks still occur)
#			1 - normal updates - one download every 10 minutes
#			2 - fast updates - one download update every 10 seconds, then at the normal rate after one pass
#			3 - one update pass at the fast rate, then to no updates
#				changing to one of the fast scans, starts from the first package
#
#		if no download is needed, checks for downloads are fast: every 5 seconds, slow: every 2 minutes

AUTO_DOWNLOADS_OFF = 0
NORMAL_DOWNLOAD = 1
FAST_DOWNLOAD = 2
ONE_DOWNLOAD = 3

#		/Settings/PackageMonitor/AutoInstall
#			0 - no automatic install
#			1 - automatic install after download from GitHub or SD/USB
#
# Additional (volatile) parameters linking packageManager and the GUI are provided in a separate dbus service:
#
#	com.victronenergy.packageMonitor parameters
#		/Package/n/GitHubVersion 					from GitHub
#		/Package/n/PackageVersion 					from /data <packageName>/version from the package directory
#		/Package/n/InstalledVersion 				from /etc/venus/isInstalled-<packageName>
#		/Package/n/RebootNeeded						indicates a reboot is needed to activate this package
#		/Package/n/Incompatible						indicates if package is or is not compatible with the system
#													'' if compatible
#													'VERSION' if the system version is outside the package's acceptable range
#													'PLATFORM' package can not run on this platform
# TODO:												'CMDLINE' setup must be run from command line
#														currently only for Raspberry PI packages only
#
#		for both Settings and the the dbus service:
#			n is a 0-based section used to reference a specific package
#
#
#		/Default/m/PackageName			a dbus copy of the default package list (/data/SetupHelper/defaultPackageList)
#		/Default/m/GitHubUser
#		/Default/m/GitHubBranch
#		/DefaultCount					the number of default packages
#
#		m is a 0-based section used to referene a specific default paclage
#
#		/GuiEditAction is a text string representing the action
#		  set by the GUI to trigger an action in PackageManager
#			'Install' - install package from /data to the Venus working directories
#			'Uninstall' - uninstall package from the working directories
#			'Download" - download package from GutHub to /data
#			'Add' - add package to package list (after GUI sets .../Edit/...
#			'Remove' - remove package from list TBD ?????
# 		 	'Reboot' - reboot
#
#		the GUI must wait for PackageManager to signal completion of one operation before initiating another
#
#		  set by packageMonitor when the task is complete
#	return codes - set by PackageManager
#			'' - action completed without errors (idle)
#			'ERROR' - error during action - error reported in /GuiEditStatus:
#				unknown error
#				not compatible with this version
#				not compatible with this platform
#				no options present - must install from command line
#				GUI choices: OK - closes "dialog"
#			'RebootNeeded' - reboot needed
#				GUI choices:
#					Do it now
#						GUI sends reboot command to PackageMonitor
#					Defer
#						GUI sets action to 0
#
# setup script return codes
EXIT_SUCCESS =				0
EXIT_ERROR =				255 # generic error
EXIT_REBOOT =				123
EXIT_INCOMPATIBLE_VERSION =	254
EXIT_INCOMPATIBLE_PLATFOM =	253
EXIT_FILE_SET_ERROR	=		252
EXIT_OPTIONS_NOT_SET =		251
EXIT_RUN_AGAIN = 			250
#
#
#		/GuiEditStatus 				a text message to report edit status to the GUI
#
#		/GitHubUpdateStatus			as above for automatic GitHub update
#
#		/InstallStatus				as above for automatic install/uninstall
#
#		/MediaUpdateStatus			as above for SD/USB media transfers
#
#
# /Settings/PackageVersion/Edit/ is a section for the GUI to provide information about the a new package to be added
#
# /data/SetupHelper/defaultPackageList provides an initial list of packages
#	It contains a row for each package with the following information:
#		packageName gitHubUser gitHubBranch
#	If present, packages listed will be ADDED to the package list in /Settings
#	existing dbus Settings (GitHubUser and GitHubBranch) will not be changed
#
#	this file is read at program start
#
# Package information is stored in the /data/<packageName> directory
#
# A version file within that directory identifies the version of that package stored on disk but not necessarily installed
#
# When a package is installed, the version in the package directory is written to an "installed flag" file
#		/etc/venus/isInstalled-<packageName>
#	the contents of the file populate InstalledVersion (blank if the file doesn't exist or is empty)
#
# InstalledVersion is displayed to the user and used for tests for automatic updates
#
# GitHubVersion is read from the internet if a connection exists.
#	To minimize local network traffic and GitHub server loads one package's GitHub version is
#		read once every 5 seconds until all package versions have been retrieved
#		then one package verison is read every 10 minutes.
#	Addition of a package or change in GitHubUser or GitHubBranch will trigger a fast
#		update of GitHub versions
#	If the package on GitHub can't be accessed, GitHubVersion will be blank
#
#
# PackageMonitor downloads packages from GitHub based on the GitHub version and package (stored) versions:
#	if the GitHub branch is a specific version, the download occurs if the versions differ
#		otherwise the GitHub version must be newer.
#	the archive file is unpacked to a directory in /data named
# 		 <packageName>-<gitHubBranch>.tar.gz, then moved to /data/<packageName>, replacing the original
#
# PackageMonitor installs the stored verion if the package (stored) and installed versions differ
#
# Manual downloads and installs triggered from the GUI ignore version checks completely
#
#	In this context, "install" means replacing the working copy of Venus OS files with the modified ones
#		or adding new files and system services
#
#	Uninstalling means replacing the original Venus OS files to their working locations
#
#	All operations that access the global package list must do so surrounded by a lock to avoid accessing changing data
#		this is very important when scanning the package list
#			so that packages within that list don't get moved, added or deleted
#
#	Operations that take signficant time are handled in separate threads, decoupled from the package list
#		Operaitons are placed on a queue with all the information a processing routine needs
#			this is imporant because the package in the list involved in the operaiton
#			may no longer be in the package list or be in a different location
#
#		All operations that scan the package list must do so surrounded by
#			DbusIf.LOCK () and DbusIf.UNLOCK ()
#			and must not consume significant time: no sleeping or actions taking seconds or minutes !!!!
#
#	Operations that take little time can usually be done in-line (without queuing) 
#
# PackageMonitor checks removable media (SD cards and USB sticks) for package upgrades or even as a new package
#	File names must be in one of the following forms:
#		<packageName>-<gitHubBranch or version>.tar.gz
#		<packageName>-install.tar.gz
#	The <packageName> portion determines where the package will be stored in /data
#		and will be used as the package name when the package is added to the package list in Settings
#
#	If all criteria are met, the archive is unpacked and the resulting directory replaces /data/<packageName>
#		if not, the unpacked archive directory is deleted
#
#
#	PackageMonitor scans /data looking for new packages
#		directory names must not appear to be an archive
#			(include a GitHub branch or version number) (see rejectList below for specifics)
#		the directory must contain a valid version
#		the package must not have been manually removed (REMOVED flag file set)
#		the file name must be unique to all existing packages
#
#		A new, verified package will be added to the package list and be ready for
#			manual and automtic updates, installs, uninstalls
#
#		This mechanism handles archives extracted from SD/USB media
#
#
#	Packages may optionally include a file containg GitHub user and branch
#		if the package diretory contains the file: gitHubInfo
#			gitHubUser and gitHubBranch are set from the file's content when it is added to the package list
#			making the new package ready for automatic GitHub updates
#		gitHubInfo should have a single line of the form: gitHubUser:gitHubBranch, e.g, kwindrem:latest
#		if the package is already in the package list, gitHubInfo is ignored
#		if no GitHub information is contained in the package, the user must add it manually via the GUI
#			in so automatic downloads from GitHub can occur

# for timing sections of code
# t0 = time.perf_counter()
# code to be timed
# t1 = time.perf_counter()
# logging.info ( "some time %6.3f" % (t1 - t0) )

import platform
import argparse
import logging

# set variables for logging levels:
CRITICAL = 50
ERROR = 40
WARNING = 30
INFO = 20
DEBUG = 10

import sys
import subprocess
import threading
import os
import shutil
import dbus
import time
import re
import queue
import glob

# accommodate both Python 2 and 3
# if the Python 3 GLib import fails, import the Python 2 gobject
try:
    from gi.repository import GLib # for Python 3
except ImportError:
    import gobject as GLib # for Python 2
# add the path to our own packages for import
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'ext', 'velib_python'))
from vedbus import VeDbusService
from settingsdevice import SettingsDevice

global GitHubVersions
global DownloadGitHub
global InstallPackages
global ProcessAction
global MediaScan
global DbusIf
global Platform
global VenusVersion
global SystemReboot


#	ProcessActionClass
#	Instances:
#		ProcessAction (a separate thread)
#
#	Methods:
#		PushAction
#		run ( the thread )
#
# actions from the GUI and local methods are processed here
# a queue isolates the caller from processing time
#	and interactions with the dbus object
#		(can't update the dbus object from it's handler !)
# this method runs as a separate thread
# blocking on the next action on the queue
#
# some actions called may take seconds or minutes (based on internet speed) !!!!
#
# the queue entries are: ("action":"packageName", and source (GUI or AUTO)
#	this decouples the action from the current package list which could be changing
#	allowing the operation to proceed without locking the list

class ProcessActionClass (threading.Thread):

	def __init__(self):
		threading.Thread.__init__(self, name = "processEditAction")
		self.editActionQueue = queue.Queue (maxsize = 20)
		self.threadRunning = True

	
	#	PushAction
	#
	# add an action to our queue
	# commands are added to the queue from the GUI (dbus service change handler)
	#		 or from other local methods
	# the same queue is used so all actions can be processed by the same methods
	# the queue isolates command triggers from processing because processing 
	#		can take seconds or minutes
	#
	# command is of the form: "action":"packageName" followed by the source
	#
	#	action is a text string: Install, Uninstall, Download, Add, Remove, etc
	#	packageName is the name of the package to receive the action
	#		for some acitons this may be the null string
	#
	#	source is either 'GUI' or 'AUTO' (local methods pushing auto update commands)
	#		the source is used by the processing routines to identify the correct
	#		status message to update and the correct callback method to call
	#		when the action completes (either success or error)

	def PushAction (self, command=None, source=None):
	
		queueParams = ( command, source )
		try:
			self.editActionQueue.put ( queueParams, block=False )
		except queue.Full:
			logging.error ("command " + command + source + " lost - queue full")
		except:
			logging.error ("command " + command + source + " lost - other queue error")
	# end PushAction


	#	run (the thread), StopThread
	#
	# run  is a thread that pulls actions from a queue and processes them
	# Note: some processing times can be several seconds to a minute or more
	#	due to newtork activity
	#
	# run () checks the threadRunning flag and returns if it is False,
	#	essentially taking the thread off-line
	#	the main method should catch the tread with join ()
	# StopThread () is called to shut down the thread

	def StopThread (self):
		logging.info ("attempting to stop ProcessAction thread")
		self.threadRunning = False
	
	def run (self):
		global InstallPackages
		global SystemReboot
		while self.threadRunning:
			try:
				queueParams = self.editActionQueue.get (timeout=5)
			except queue.Empty:	# queue empty is OK - just allows some time unblocked
				if self.threadRunning == False:
					return
				time.sleep (5.0)
				continue
			except:
				logging.error ("pull from editActionQueue failed")
				continue
			# got new action from queue - decode and process
			command = queueParams[0]
			source = queueParams[1]
			parts = command.split (":")
			if len (parts) >= 1:
				action = parts[0].strip()
			else:
				action = ""
			if len (parts) >= 2:
				packageName = parts[1].strip()
			else:
				packageName = ""

			if action == 'Install':
				InstallPackages.InstallPackage (packageName = packageName, source=source, direction='install' )

			elif action == 'Uninstall':
				InstallPackages.InstallPackage (packageName = packageName, source=source, direction='uninstall' )

			elif action == 'Download': 
				DownloadGitHub.GitHubDownload ( packageName = packageName, source=source )

			elif action == 'Add':
				PackageClass.AddPackage (packageName = packageName, source=source )						

			elif action == 'Remove':
				PackageClass.RemovePackage ( packageName )

			elif action == 'Reboot':
				logging.warning ( "received Reboot request from " + source)
				# set the flag - reboot is done in main_loop
				SystemReboot = True

			# ignore the idle action
			elif action == '':
				pass

			else:
				logging.warning ( "received invalid action " + command + " from " + source + " - discarding" )
		# end while True
	# end run ()
# end ProcessActionClass


#	DbusIfClass
#	Instances:
#		DbusIf
#
#	Methods:
#		UpdateGuiState
#		UpdateStatus
#		LocateDefaultPackage
#		handleGuiEditAction
#		UpdatePackageCount
#		various Gets and Sets for dbus parameters
#		LOCK
#		UNLOCK
#
#	Globals:
#		DbusSettings (for settings that are NOT part of a package)
#		DbusService (for parameters that are NOT part of a package)
#		EditPackage - the dbus Settings used by the GUI to hand off information about
#			a new package
#		DefaultPackages - list of default packages, each a tuple:
#						 ( packageName, gitHubUser, gitHubBranch)
#
# DbusIf manages the dbus Settings and packageManager dbus service parameters
#	that are not associated with any spcific package
#
# unlike those managed in PackageClass which DO have a package association
#	the dbus settings managed here don't have a package association
#	however, the per-package parameters are ADDED to
#	DbusSettings and dBusService created here !!!!
#
# DbusIf manages a lock to prevent data access in one thread
#	while it is being changed in another
#	the same lock is used to protect data in PackageClass also
#	this is more global than it needs to be but simplies the locking
#
#	all methods that access must aquire this lock
#		prior to accessing DbusIf or Package data
#		then must release the lock
#
# default package info is fetched from a file and published to our dbus service
#	for use by the GUI in adding new packages
#	it the default info is also stored in DefaultPackages
#	LocateDefaultPackage is used to retrieve the default from local storage
#		rather than pulling from dbus or reading the file again

class DbusIfClass:
	
	#	UpdateGuiState
	#
	# updates the GUI package editor state when a requested opeation completes
	# The GUI behaves differently for success and failure
	# source allows this method to only update the GUI state
	#	even though it may be the result of

	def UpdateGuiState (self, nextState):

		if nextState != None:
			self.SetGuiEditAction ( nextState )


	#	UpdateStatus
	#
	# updates the status when the operation completes
	# the GUI provides three different areas to show status
	# where specifies which of these are updated
	#	'Download'
	#	'Install'
	#	'Editor'
	#	'Media'
	#	which determines where status is sent
	# message is the text displayed
	# if LogLevel is not 0, message is also written to the PackageManager log
	# logging levels: (can use numeric value or these variables set at head of module
	#	CRITICAL = 50
	#	ERROR = 40
	#	WARNING = 30
	#	INFO = 20
	#	DEBUG = 10
	# if where = None, no GUI status areas are updated


	def UpdateStatus ( self, message=None, where=None, logLevel=0 ):

		if logLevel != 0:
			logging.log ( logLevel, message )

		if where == 'Editor':
			DbusIf.SetEditStatus ( message )
		elif where == 'Install':
			DbusIf.SetInstallStatus ( message )
		elif where == 'Download':
			DbusIf.SetGitHubUpdateStatus (message)
		elif where == 'Media':
			DbusIf.SetMediaStatus (message)


	#	handleGuiEditAction (internal use only)
	#
	# the GUI uses packageMonitor service /GuiEditAction
	# to inform PackageManager of an action
	# a command is formed as "action":"packageName"
	#
	#	action is a text string: install, uninstall, download, etc
	#	packageName is the name of the package to receive the action
	#		for some acitons this may be the null string
	# this handler disposes of the request quickly by pushing
	#	the command onto a queue for later processing

	def handleGuiEditAction (self, path, command):

		global ProcessAction

		ProcessAction.PushAction ( command=command, source='GUI')

		return True	# True acknowledges the dbus change - other wise dbus parameter does not change

	def UpdatePackageCount (self):
		count = len(PackageClass.PackageList)
		self.DbusSettings['packageCount'] = count
	def GetPackageCount (self):
		return self.DbusSettings['packageCount']
	def SetAutoDownload (self, value):
		self.DbusSettings['autoDownload'] = value
	def GetAutoDownload (self):
		return self.DbusSettings['autoDownload']
	def GetAutoInstall (self):
		return self.DbusSettings['autoInstall']
	def SetGitHubUpdateStatus (self, value):
		self.DbusService['/GitHubUpdateStatus'] = value
	def SetInstallStatus (self, value):
		self.DbusService['/InstallStatus'] = value
	def SetMediaStatus (self, value):
		self.DbusService['/MediaUpdateStatus'] = value


	def SetGuiEditAction (self, value):
		self.DbusService['/GuiEditAction'] = value
	def GetGuiEditAction (self):
		return self.DbusService['/GuiEditAction']
	def SetEditStatus (self, message):
		self.DbusService['/GuiEditStatus'] = message

	# search default package list for packageName
	# and return the pointer if found
	#	otherwise return None
	#
	# Note: this method should be called with LOCK () set
	#	and use the returned value before UNLOCK ()
	#	to avoid unpredictable results
	#
	# DefaultPackages is a list of tuples:
	#	(packageName, gitHubUser, gitHubBranch)
	#
	# if a packageName match is found, the tuple is returned
	#	otherwise None is retuned

	def LocateDefaultPackage (self, packageName):
		
		for default in self.defaultPackages:
			if packageName == default[0]:
				return default
		return None
	

	# LOCK and UNLOCK - capitals used to make it easier to identify in the code
	#
	# these protect the package list from changing while the list is being accessed
	
	def LOCK (self):
		self.lock.acquire ()
	def UNLOCK (self):
		self.lock.release ()


	def __init__(self):
		self.lock = threading.RLock()

		settingsList = {'packageCount': [ '/Settings/PackageMonitor/Count', 0, 0, 0 ],
						'autoDownload': [ '/Settings/PackageMonitor/GitHubAutoDownload', 0, 0, 0 ],
						'autoInstall': [ '/Settings/PackageMonitor/AutoInstall', 0, 0, 0 ],
						}
		self.DbusSettings = SettingsDevice(bus=dbus.SystemBus(), supportedSettings=settingsList,
								timeout = 10, eventCallback=None )


		self.DbusService = VeDbusService ('com.victronenergy.packageMonitor', bus = dbus.SystemBus())
		self.DbusService.add_mandatory_paths (
							processname = 'PackageMonitor', processversion = 1.0, connection = 'none',
							deviceinstance = 0, productid = 1, productname = 'Package Monitor',
							firmwareversion = 1, hardwareversion = 0, connected = 1)
		self.DbusService.add_path ('/GitHubUpdateStatus', "")
		self.DbusService.add_path ('/InstallStatus', "")
		self.DbusService.add_path ('/MediaUpdateStatus', "" )
		self.DbusService.add_path ('/GuiEditStatus', "" )
		global Platform
		self.DbusService.add_path ('/Platform', Platform )

		self.DbusService.add_path ('/GuiEditAction', "", writeable = True,
										onchangecallback = self.handleGuiEditAction)

		# publish the default packages list and store info locally for faster access later
		section = 0
		self.defaultPackages = []
		try:
			listFile = open ("/data/SetupHelper/defaultPackageList", 'r')
		except:
			logging.warning ("no defaultPackageList " + listFileName)
		else:
			for line in listFile:
				parts = line.split ()
				if len(parts) < 3 or line[0] == "#":
					continue
				prefix = '/Default/' + str (section) + '/'
				self.DbusService.add_path (prefix + 'PackageName', parts[0] )
				self.DbusService.add_path (prefix + 'GitHubUser', parts[1] )
				self.DbusService.add_path (prefix + 'GitHubBranch', parts[2] )
				
				self.defaultPackages.append ( ( parts[0], parts[1], parts[2] ) )
				section += 1
			listFile.close ()
			self.DbusService.add_path ('/DefaultCount', section )

		# a special package used for editing a package prior to adding it to Package list
		self.EditPackage = PackageClass (section = "Edit")


	#	RemoveDbusService
	#  deletes the dbus service

	def RemoveDbusService (self):
		logging.info ("shutting down com.victronenergy.packageMonitor dbus service")
		self.DbusService.__del__()
	
# end DbusIf


#	PackageClass
#	Instances:
#		one per package
#
#	Methods:
#		LocatePackage
#		RemoveDbusSettings
#		various Gets and Sets
#		AddPackagesFromDbus (class method)
#		AddDefaultPackages (class method)
#		AddStoredPackages (class method)
#		AddPackage (class method)
#		RemovePackage (class method)
#		GetVersionsFromFiles (class method)
#		updateGitHubInfo
#			called only from AddPackage because behavior depends on who added the package
#
#	Globals:
#		DbusSettings (for per-package settings)
#		DbusService (for per-package parameters)
#		InstallPending 
#		UnnstallPending
#		DownloadPending
#		PackageList - list instances of all packages
#
# a package consits of Settings and version parameters in the package monitor dbus service
# all Settings and parameters are accessible via set... and get... methods
#	so that the caller does not need to understand dbus Settings and service syntax
# the packageName variable maintains a local copy of the dBus parameter for speed in loops
# section passed to init can be either a int or string ('Edit')
#	an int is converted to a string to form the dbus setting paths
#
# the dbus settings and service parameters managed here are on a per-package basis
#	unlike those managed in DbusIf which don't have a package association

class PackageClass:

	# list of instantiated Packages
	PackageList = []

	global GitHubVersions
	

	# search PackageList for packageName
	# and return the package pointer if found
	#	otherwise return None
	#
	# Note: this method should be called with LOCK () set
	#	and use the returned value before UNLOCK ()
	#	to avoid unpredictable results

	def LocatePackage (packageName):
		for package in PackageClass.PackageList:
			if packageName == package.PackageName:
				return package
		return None

	def SetPackageName (self, newName):
		self.DbusSettings['packageName'] = newName
	
	def SetInstalledVersion (self, version):
		if self.installedVersionPath != "":
			DbusIf.DbusService[self.installedVersionPath] = version	
	def GetInstalledVersion (self):
		if self.installedVersionPath != "":
			return DbusIf.DbusService[self.installedVersionPath]
		else:
			return None
	def SetPackageVersion (self, version):
		if self.packageVersionPath != "":
			DbusIf.DbusService[self.packageVersionPath] = version	
	def GetPackageVersion (self):
		if self.packageVersionPath != "":
			return DbusIf.DbusService[self.packageVersionPath]
		else:
			return None
	def SetGitHubVersion (self, version):
		if self.gitHubVersionPath != "":
			DbusIf.DbusService[self.gitHubVersionPath] = version	
	def GetGitHubVersion (self):
		if self.gitHubVersionPath != "":
			return DbusIf.DbusService[self.gitHubVersionPath]
		else:
			return None

	def SetIncompatible(self, value):
		if self.incompatiblePath != "":
			DbusIf.DbusService[self.incompatiblePath] = value	
	def GetIncompatible (self):
		if self.incompatiblePath != "":
			return DbusIf.DbusService[self.incompatiblePath]
		else:
			return None

	def SetRebootNeeded (self, value):
		if self.rebootNeededPath != "":
			DbusIf.DbusService[self.rebootNeededPath] = value	
	def GetRebootNeeded (self):
		if self.rebootNeededPath != "":
			if DbusIf.DbusService[self.rebootNeededPath] == 1:
				return True
			else:
				return False
		else:
			return False

	def SetGitHubUser (self, value):
		self.DbusSettings['gitHubUser'] = value
	def GetGitHubUser (self):
		return self.DbusSettings['gitHubUser']
	def SetGitHubBranch (self, value):
		self.DbusSettings['gitHubBranch'] = value
	def GetGitHubBranch (self):
		return self.DbusSettings['gitHubBranch']

	# remove the dbus settings for this package
	# package Settings are removed
	# package service parameters are just set to ""
	#
	# can't actually remove settings cleanly
	#	so just set contents to null/False

	def RemoveDbusSettings (self):
	
		self.SetPackageName ("")
		self.SetGitHubUser ("")
		self.SetGitHubBranch ("")
		self.SetInstalledVersion ("")
		self.SetPackageVersion ("")
		self.SetGitHubVersion ("")
		self.SetRebootNeeded (False)


	def settingChangedHandler (self, name, old, new):
		# when GitHub information changes, need to refresh GitHub version for this package
		if name == 'packageName':
			self.PackageName = new
		elif name == 'gitHubBranch' or name == 'gitHubUser':
			if self.PackageName != None and self.PackageName != "":
				GitHubVersions.RefreshVersion (self.PackageName )

	def __init__( self, section, packageName = None ):
		# add package versions if it's a real package (not Edit)
		if section != 'Edit':
			section = str (section)
			self.installedVersionPath = '/Package/' + section + '/InstalledVersion'
			self.packageVersionPath = '/Package/' + section + '/PackageVersion'
			self.gitHubVersionPath = '/Package/' + section + '/GitHubVersion'
			self.rebootNeededPath = '/Package/' + section + '/RebootNeeded'
			self.incompatiblePath = '/Package/' + section + '/Incompatible'

			# create paths if they dont currently exist
			try:
				foo = DbusIf.DbusService[self.installedVersionPath]
			except:
				DbusIf.DbusService.add_path (self.installedVersionPath, "" )
			try:
				foo = DbusIf.DbusService[self.gitHubVersionPath]
			except:
				DbusIf.DbusService.add_path (self.gitHubVersionPath, "" )
			try:
				foo = DbusIf.DbusService[self.packageVersionPath]
			except:
				DbusIf.DbusService.add_path (self.packageVersionPath, "" )
			try:
				foo = DbusIf.DbusService[self.rebootNeededPath]
			except:
				DbusIf.DbusService.add_path (self.rebootNeededPath, "" )
			try:
				foo = DbusIf.DbusService[self.incompatiblePath]
			except:
				DbusIf.DbusService.add_path (self.incompatiblePath, "" )


		self.packageNamePath = '/Settings/PackageMonitor/' + section + '/PackageName'
		self.gitHubUserPath = '/Settings/PackageMonitor/' + section + '/GitHubUser'
		self.gitHubBranchPath = '/Settings/PackageMonitor/' + section + '/GitHubBranch'

		settingsList =	{'packageName': [ self.packageNamePath, '', 0, 0 ],
						'gitHubUser': [ self.gitHubUserPath, '', 0, 0 ],
						'gitHubBranch': [ self.gitHubBranchPath, '', 0, 0 ],
						}
		self.DbusSettings = SettingsDevice(bus=dbus.SystemBus(), supportedSettings=settingsList,
				eventCallback=self.settingChangedHandler, timeout = 10)
		# if packageName specified on init, use that name
		if packageName != None:
			self.DbusSettings['packageName'] = packageName
			self.PackageName = packageName
		# otherwise pull name from dBus Settings
		else:
			self.PackageName = self.DbusSettings['packageName']
		
		# these flags are used to insure multiple actions aren't pushed onto the processing queue
		self.section = section
		self.InstallPending = False
		self.UninstallPending = False
		self.DownloadPending = False


	# dbus Settings is the primary non-volatile storage for packageManager
	# upon startup, PackageList [] is empty and we need to populate it
	# from previous dBus Settings in /Settings/PackageMonitor/...
	# this is a special case that can't use AddPackage below:
	#	we do not want to create any new Settings !!
	#	it should be "safe" to limit the serch to 0 to < packageCount
	#	we also don't specify any parameters other than the section (index)
	#
	# NOTE: this method is called before threads are created so do not LOCK
	#
	# returns False if couldn't get the package cound from dbus
	#	otherwise returns True

	@classmethod
	def AddPackagesFromDbus (cls):
		global DbusIf
		packageCount = DbusIf.GetPackageCount()
		if packageCount == None:
			logging.critical ("dbus PackageCount is not defined -- can't continue")
			return False
		i = 0
		while i < packageCount:
			cls.PackageList.append(PackageClass (section = i))
			i += 1
		return True


	# default packages are appended to the package list during program initialization
	#
	# a package may already be in the dbus list and will already have been added
	#	so these are skipped
	#
	# the default list is a tuple with packageName as the first element

	@classmethod
	def AddDefaultPackages (cls, initialList=False):
		for default in DbusIf.defaultPackages:
			packageName = default[0]
			DbusIf.LOCK ()
			package = cls.LocatePackage (packageName)
			DbusIf.UNLOCK ()			
			if package == None:
				cls.AddPackage ( packageName=packageName )


	# packaged stored in /data must also be added to the package list
	#	but package name must be unique
	# in order to qualify as a package:
	#	must be a directory
	#	name must not contain strings in the rejectList
	#	name must not include any spaces
	#	diretory must contain a file named version
	#	first character of version file must be 'v'

	rejectList = [ "-current", "-latest", "-main", "-test", "-debug", "-beta", "-backup1", "-backup2",
					"-0", "-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9", " " ]

	@classmethod
	def AddStoredPackages (cls):

		for path in glob.iglob ("/data/*"):
			file = os.path.basename (path)
			if os.path.isdir (path) == False:
				continue
			rejected = False
			for reject in cls.rejectList:
				if reject in file:
					rejected = True
					break
			if rejected:
				continue
			versionFile = path + "/version"
			if os.path.isfile (versionFile) == False:
				continue
			fd = open (versionFile, 'r')
			version = fd.readline().strip()
			fd.close ()
			if version[0] != 'v':
				logging.warning  (file + " version rejected " + version)
				continue

			# skip if package was manually remove
			if os.path.exists (path + "/REMOVED"):
				continue

			# skip if package is for Raspberry PI only and platform is not
			global Platform
			if os.path.exists (path + "/raspberryPiOnly") and Platform[0:4] != 'Rasp':
				continue

			# continue only if package is unique
			DbusIf.LOCK ()
			package = cls.LocatePackage (file)
			DbusIf.UNLOCK ()			
			if package != None:
				continue
			
			cls.AddPackage ( packageName=file, source='AUTO' )
	
	
	# updateGitHubInfo fetchs the GitHub info and puts it in dbus settings
	#
	# There are three sources for this info:
	#	GUI 'EDIT' section (only used for adds from the GUI)
	#	the stored package (/data/<packageName>)
	#	the default package list
	# 
	# the sources are prioritized in the above order
	
	@classmethod
	def updateGitHubInfo (cls, packageName=None, source=None ):
		# if adding from GUI, get info from EditPackage
		#	check other sources if empty
		if source == 'GUI':
			gitHubUser = DbusIf.EditPackage.GetGitHubUser ()
			gitHubBranch = DbusIf.EditPackage.GetGitHubBranch ()
		# 'AUTO' source
		else:
			gitHubUser = ""
			gitHubBranch = ""

		# attempt to retrieve GitHub user and branch from stored pacakge
		# update only if not already set
		path = "/data/" + packageName + "/gitHubInfo" 
		if os.path.isfile (path):
			fd = open (path, 'r')
			gitHubInfo = fd.readline().strip()
			fd.close ()
			parts = gitHubInfo.split(":")
			if len (parts) >= 2:
				if gitHubUser == "":
					gitHubUser = parts[0]
				if gitHubBranch == "":
					gitHubBranch = parts[1]
			else:
				logging.warning (file + " gitHubInfo not formed properly " + gitHubInfo)

		# finally, pull GitHub info from default package list
		if gitHubUser == "" or gitHubBranch == "":
			default = DbusIf.LocateDefaultPackage (packageName)
			if default != None:
				if gitHubUser == "":
					gitHubUser = default[1]
				if gitHubBranch == "":
					gitHubBranch = default[2]

		# update dbus parameters
		DbusIf.LOCK ()
		package = PackageClass.LocatePackage (packageName)
		if package != None:
			package.SetGitHubUser (gitHubUser)
			package.SetGitHubBranch (gitHubBranch)
		DbusIf.UNLOCK ()
		

	# AddPackage adds one package to the package list
	# packageName must be specified
	# the package names must be unique
	#
	# this method is called from the GUI add package command

	@classmethod
	def AddPackage ( cls, packageName=None, source=None ):
		if source == 'GUI':
			reportStatusTo = 'Editor'
		# 'AUTO' source
		else:
			reportStatusTo = None

		if packageName == None or packageName == "":
			DbusIf.UpdateStatus ( message="no package name for AddPackage - nothing done",
							where=reportStatusTo, logLevel=ERROR )
			if source == 'GUI':
				DbusIf.UpdateGuiState ( 'ERROR' )
			return False


		# insure packageName is unique before adding this new package
		matchFound = False
		DbusIf.LOCK ()
		package = PackageClass.LocatePackage (packageName)

		# new packageName is unique, OK to add it
		if package == None:
			DbusIf.UpdateStatus ( message="Adding package " + packageName, where='Editor', logLevel=INFO )

			section = len(cls.PackageList)
			cls.PackageList.append( PackageClass ( section, packageName = packageName ) )
			DbusIf.UpdatePackageCount ()

			cls.updateGitHubInfo (packageName=packageName, source=source)

			if source == 'GUI':
				DbusIf.UpdateGuiState ( '' )
			# delete the removed flag if the package directory exists
			path = "/data/" + packageName + "/REMOVED"
			if os.path.exists (path):
				os.remove (path)
		else:
			if source == 'GUI':
				DbusIf.UpdateStatus ( message=packageName + " already exists - choose another name", where=reportStatusTo, logLevel=INFO )
				DbusIf.UpdateGuiState ( 'ERROR' )
			else:
				DbusIf.UpdateStatus ( message=packageName + " already exists", where=reportStatusTo, logLevel=INFO )
		
		DbusIf.UNLOCK ()
	# end AddPackage

	# packages are removed as a request from the GUI
	# to remove a package:
	#	1) locate the entry matching package name  (if any)
	#	2) move all packages after that entry the previous slot (if any)
	#	3) erase the last package slot to avoid confusion (by looking at dbus-spy)
	#	3) remove the entry in PackageList (pop)
	#	4) update the package count
	#	5) set REMOVED flag file in the package directory in /data to prevent
	#		package from being re-added to the package list
	#		flag file is deleted when package is manually installed again
	#
	#	returns True if package was removed, False if not
	#
	#	this is all done while the package list is locked !!!!

	@classmethod
	def RemovePackage (cls, packageName ):
		if packageName == "SetupHelper":
			DbusIf.UpdateStatus ( message="can't remove SetupHelper" + packageName, where='Editor', logLevel=INFO )
			return

		DbusIf.UpdateStatus ( message="removing " + packageName, where='Editor', logLevel=INFO )
		DbusIf.LOCK ()
		packages = PackageClass.PackageList

		# locate index of packageName
		toIndex = 0
		listLength = len (packages)
		matchFound = False
		while toIndex < listLength:
			if packageName == packages[toIndex].PackageName:
				matchFound = True
				break
			toIndex += 1

		if matchFound:
			# move packages after the one to be remove down one slot (copy info)
			# each copy overwrites the lower numbered package
			fromIndex = toIndex + 1
			while fromIndex < listLength:
				toPackage = packages[toIndex]
				fromPackage = packages[fromIndex]
				toPackage.SetPackageName (fromPackage.PackageName )
				toPackage.SetGitHubUser (fromPackage.GetGitHubUser() )
				toPackage.SetGitHubBranch (fromPackage.GetGitHubBranch() )
				toPackage.SetGitHubVersion (fromPackage.GetGitHubVersion() )
				toPackage.SetInstalledVersion (fromPackage.GetInstalledVersion() )
				toPackage.SetPackageVersion (fromPackage.GetPackageVersion() )
				toPackage.SetRebootNeeded (fromPackage.GetRebootNeeded() ) 
				toPackage.SetIncompatible (fromPackage.GetIncompatible() ) 
				toIndex += 1
				fromIndex += 1

			# here, toIndex points to the last package in the old list

			# remove the Settings for the package being removed
			packages[toIndex].RemoveDbusSettings ()

			# remove entry from package list
			packages.pop (toIndex)

			# update package count
			DbusIf.UpdatePackageCount ()		

		DbusIf.UNLOCK ()
		# flag this package was manually removed via setting the REMOVED flag file
		#	in the package directory
		if matchFound:
			if os.path.isdir ("/data/" + packageName):
				path = "/data/" + packageName + "/REMOVED"
				# equivalent to unix touch command
				open ("/data/" + packageName + "/REMOVED", 'a').close()

			DbusIf.UpdateStatus ( message="", where='Editor' )
			DbusIf.UpdateGuiState ( '' )
		else:
			DbusIf.UpdateStatus ( message=packageName + " not removed - name not found", where='Editor', logLevel=ERROR )
			DbusIf.UpdateGuiState ( 'ERROR' )


	#	GetVersionsFromFiles
	#
	# retrieves packages versions from the file system
	#	each package contains a file named version in it's root directory
	#		that becomes packageVersion
	#	an "installedFlag" file is associated with installed packages
	#		abesense of the file indicates the package is not installed
	#		presense of the file indicates the package is installed
	#		the contents of the flag file be the actual version installed
	#		in prevous versions of the setup scripts, this file could be empty, 
	#		so we show this as "unknown"
	#
	# also sets incompatible dbus service parameters

	@classmethod
	def GetVersionsFromFiles(cls):
		DbusIf.LOCK ()
		for package in cls.PackageList:
			packageName = package.PackageName

			# fetch installed version
			installedVersionFile = "/etc/venus/installedVersion-" + packageName
			try:
				versionFile = open (installedVersionFile, 'r')
			except:
				installedVersion = ""
			else:
				installedVersion = versionFile.readline().strip()
				versionFile.close()
				# if file is empty, an unknown version is installed
				if installedVersion ==  "":
					installedVersion = "unknown"
			package.SetInstalledVersion (installedVersion)

			# fetch package version (the one in /data/packageName)
			try:
				versionFile = open ("/data/" + packageName + "/version", 'r')
			except:
				packageVersion = ""
			else:
				packageVersion = versionFile.readline().strip()
				versionFile.close()
			package.SetPackageVersion (packageVersion)

			# set the incompatible parameter
			#	to 'PLATFORM' or 'VERSION'
			global Platform
			incompatible = False
			if os.path.exists ("/data/" + packageName + "/raspberryPiOnly" ):
				if Platform[0:4] != 'Rasp':
					package.SetIncompatible ('PLATFORM')
					incompatible = True

			# platform is OK, now check versions
			if incompatible == False:
				# check version compatibility
				try:
					fd = open ("/data/" + packageName + "/firstCompatibleVersion", 'r')
				except:
					firstVersion = "v2.40"
				else:
					firstVersion = fd.readline().strip()
					fd.close ()
				try:
					fd = open ("/data/" + packageName + "/obsoleteVersion", 'r')
				except:
					obsoleteVersion = None
				else:
					obsoleteVersion = fd.readline().strip()
				
				global VersionToNumber
				global VenusVersion
				firstVersionNumber = VersionToNumber (firstVersion)
				obsoleteVersionNumber = VersionToNumber (obsoleteVersion)
				venusVersionNumber = VersionToNumber (VenusVersion)
				if venusVersionNumber < firstVersionNumber:
					self.SetIncompatible ('VERSION')
					incompatible = True
				elif obsoleteVersionNumber != 0 and venusVersionNumber >= obsoleteVersionNumber:
					package.SetIncompatible ('VERSION')
					incompatible = True

			# platform and versions OK, check to see if command line is needed for install
			# the optionsRequired flag in the package directory indicates options must be set before a blind install
			# the optionsSet flag indicates the options HAVE been set already
			# so if optionsRequired == True and optionsSet == False, can't install from GUI
			if incompatible == False:
				if os.path.exists ("/data/" + packageName + "/optionsRequired" ):
					if not os.path.exists ( "/data/setupOptions/" + packageName + "/optionsSet"):
						package.SetIncompatible ('CMDLINE')
						incompatible = True

		DbusIf.UNLOCK ()
# end Package


#	GetGitHubVersionsClass
#	Instances:
#		GitHubVersions (a separate thread)
#
#	Methods:
#		RefreshVersion
#		run ( the thread )
#		updateGitHubVersion
#
# retrieves GitHub versions over the network
#	runs as a separate thread because it takes time
#	and so we can space out network access over time

class GetGitHubVersionsClass (threading.Thread):

	# package needing immediate update
	priorityPackageName = None

	def __init__(self):
		threading.Thread.__init__(self, name = "GetGitHubVersion")
		self.threadRunning = True


	def updateGitHubVersion (self, packageName, gitHubUser = None, gitHubBranch = None):
		matchFound = False
		# if user and branch aren't specified, get from package list
		if gitHubUser == None or gitHubBranch == None:
			DbusIf.LOCK ()
			package = PackageClass.LocatePackage (packageName)
			if package != None:
				gitHubUser = package.GetGitHubUser()
				gitHubBranch = package.GetGitHubBranch()
			DbusIf.UNLOCK ()

			# packageName no longer in list - do nothing
			if matchFound == False:
				return None

		url = "https://raw.githubusercontent.com/" + gitHubUser + "/" + packageName + "/" + gitHubBranch + "/version"

		cmdReturn = subprocess.run (["wget", "-qO", "-", url],\
				text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if cmdReturn.returncode == 0:
			gitHubVersion = cmdReturn.stdout.strip()
		else:
			gitHubVersion = ""
		# locate the package with this name and update it's GitHubVersion
		# if not in the list discard the information
		DbusIf.LOCK ()
		packageToUpdate = None
		try:
			if packageName == package.PackageName:
				packageToUpdate = package
		except:
			package = PackageClass.LocatePackage (packageName)
			if package != None:
				packageToUpdate = package
		if packageToUpdate != None:
			packageToUpdate.SetGitHubVersion (gitHubVersion)
		DbusIf.UNLOCK ()


	#	RefreshVersion
	#
	# schedules the refresh of the GitHub version for a specific section
	#	called when the gitHubBranch changes in Settings
	#	so must return immediately
	# the refresh is performed in the run thread

	def RefreshVersion (self, packageName):
		self.priorityPackageName = packageName

	#	run() - the thread
	#
	# pulls the GitHub version for all packages from the internet
	#	so this loop runs slowly and must be paced to minimize network traffic
	#
	# the first loop at start is a 5 seconds per package
	# then the loop slows to 60 seconds per pacakge to save bandwidth
	# priorityPackage is tested while waiting and updated next if defined
	#
	# loop extracts a packageName from the package list
	# 	then operates on that name
	# if the name is still in the list after fetching the GitHub version
	#	the package list is updated
	# if not, the version is discarded
	#
	# this complication is due to the need to lock the packageList
	#	while updating it
	#
	# run () checks the threadRunning flag and returns if it is False,
	#	essentially taking the thread off-line
	#	the main method should catch the tread with join ()
	# StopThread () is called to shut down the thread

	def StopThread (self):
		logging.info ("attempting to stop GetGitHubVersions thread")
		self.threadRunning = False

	def run (self):
		updateRate = 5.0
		index = 0
		while self.threadRunning:
			# end of package list - assume all packages have been scanned once
			# and slow loop to one verion every 1 minute
			DbusIf.LOCK ()
			if index >= len (PackageClass.PackageList):
				index = 0
				updateRate = 60.0
			package = PackageClass.PackageList[index]
			name = package.PackageName
			user = package.GetGitHubUser ()
			branch = package.GetGitHubBranch ()
			DbusIf.UNLOCK ()

			self.updateGitHubVersion (packageName = name, gitHubUser = user,  gitHubBranch = branch)
			index += 1

			delayTime = updateRate
			while delayTime > 0.0:
				if self.threadRunning == False:
					return
				if self.priorityPackageName != None:
					DbusIf.LOCK ()
					package = PackageClass.LocatePackage (self.priorityPackageName)
					if package != None:
						user = package.GetGitHubUser ()
						branch = package.GetGitHubBranch ()
					DbusIf.UNLOCK ()
					if package != None:
						self.updateGitHubVersion (packageName = self.priorityPackageName, gitHubUser = user,  gitHubBranch = branch)
					else:
						logging.error ("can't fetch GitHub version - " + self.priorityPackageName + " not in list")
					self.priorityPackageName = None
				time.sleep (5.0)
				delayTime -= 5.0
			
#	VersionToNumber
#
# convert a version string in the form of vX.Y~Z-large-W to an integer to make comparisions easier
# the ~Z portion indicates a pre-release version so a version without it is later than a version with it
# the -W portion is like the ~Z for large builds
# 	the -W portion is IGNORED !!!!
#	note part[0] is always null because there is nothing before v which is used as a separator
#
# each section of the version is given 3 decimal digits
#	for example v1.2~3 			would be  1002003
#	for example v11.22   		would be 11022999
#	for example v11.22-large-33	would be 11022999
# an empty file or one that contains "unknown" or does not beging with 'v'
# 	has a version number = 0
#
#	returns the version number

def VersionToNumber (version):
	if version == None or version == "" or version[0] != 'v':
		return 0

	parts = re.split ('v|\.|\~|\-', version)
	versionNumber = 0
	if len(parts) >= 2:
		versionNumber += int ( parts[1] ) * 1000000
	if len(parts) >= 3:
		versionNumber += int ( parts[2] ) * 1000
	if len(parts) >= 4:
		versionNumber += int ( parts[3] )
	else:
		versionNumber += 999
	return versionNumber


#	DownloadGitHubPackagesClass
#	Instances:
#		DownloadGitHub (a separate thread)
#
#	Methods:
#		SetDownloadPending
#		ClearDownloadPending
#		GitHubDownload
#		downloadNeeded
#		wait
#		run  ( the thread )
#
# downloads packages from GitHub, replacing the existing package
# 	if versions indicate a newer version
#
# the run () thread is only responsible for pacing automatic downloads from the internet
#	commands are pushed onto the processing queue (PushAction)
#
# the actual download (GitHubDownload) is called in the context of ProcessAction
#

class DownloadGitHubPackagesClass (threading.Thread):

	def __init__(self):
		threading.Thread.__init__(self, name = "downloadGitHubPackages")
		self.lastMode = 0
		self.lastAutoDownloadTime = 0.0
		self.threadRunning = True

	# the ...Pending flag prevents duplicate actions from piling up
	# automatic downloads are not queued if there is one pending
	#	for a specific package
	#
	# packageName rather than a package list reference (index, etc)
	# 	because the latter can change when packages are removed
	#
	# the pending flag is set at the beginning of the operation
	# 	because the GUI can't do that
	#	this doesn't close the window but narrows it a little

	
	def SetDownloadPending (self, packageName):
		package = PackageClass.LocatePackage (packageName)
		if package != None:
			package.downloadPending = True

	
	def ClearDownloadPending (self, packageName):
		package = PackageClass.LocatePackage (packageName)
		if package != None:
			package.downloadPending = False

	# this method downloads a package from GitHub
	# it is called from the queue command processor ProcessAction.run()
	# also, download requests are pushed for automatic downloads from the loop below in run() method
	# and also for a manual download triggered from the GUI
	# statusMethod provides text status to the caller
	# callBack provides notificaiton of completion (or error)
	# automatic downloads that fail are logged but otherwise not reported
		
	def GitHubDownload (self, packageName= None, source=None):
		if source == 'GUI':
			where = 'Editor'
		elif source == 'AUTO':
			where = 'Download'

		# to avoid thread confilcts, create a temp directory that
		# is unque to this program and this method
		# and make sure it is empty
		tempDirectory = "/var/run/packageManager" + str(os.getpid ()) + "GitHubDownload"
		if os.path.exists (tempDirectory):
			shutil.rmtree (tempDirectory)
		os.mkdir (tempDirectory)
		packagePath = "/data/" + packageName

		DbusIf.LOCK ()
		package = PackageClass.LocatePackage (packageName)
		gitHubUser = package.GetGitHubUser ()
		gitHubBranch = package.GetGitHubBranch ()
		DbusIf.UNLOCK ()

		DbusIf.UpdateStatus ( message="downloading " + packageName, where=where, logLevel=INFO )
		self.SetDownloadPending (packageName)

		url = "https://github.com/" + gitHubUser + "/" + packageName  + "/archive/" + gitHubBranch  + ".tar.gz"
		# create temp directory specific to this thread
		tempArchiveFile = tempDirectory + "/temp.tar.gz"
		# download archive
		if os.path.exists (tempArchiveFile):
			os.remove ( tempArchiveFile )
		cmdReturn = subprocess.run ( ['wget', '-qO', tempArchiveFile, url ],\
						text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if cmdReturn.returncode != 0:
			DbusIf.UpdateStatus ( message="can't access" + packageName + ' ' + gitHubUser + ' ' + gitHubBranch + " on GitHub",
										where=where, logLevel=WARNING )
			if source == 'GUI':
				DbusIf.UpdateGuiState ( 'ERROR' )
			self.ClearDownloadPending (packageName)
			# log stderr also
			logging.warning (cmdReturn.stderr)
			shutil.rmtree (tempDirectory)
			return False
		cmdReturn = subprocess.run ( ['tar', '-xzf', tempArchiveFile, '-C', tempDirectory ],
										text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if cmdReturn.returncode != 0:
			DbusIf.UpdateStatus ( message="can't unpack " + packageName + ' ' + gitHubUser + ' ' + gitHubBranch,
										where=where, logLevel=WARNING )
			if source == 'GUI':
				DbusIf.UpdateGuiState ( 'ERROR' )
			self.ClearDownloadPending (packageName)
			# log stderr also
			logging.warning (cmdReturn.stderr)
			shutil.rmtree (tempDirectory)
			return False

		# unpacked archive path is anything beginning with the packageName
		# should only be one item in the list, discard any others
		searchPath = tempDirectory + '/' + packageName + '*'
		tempPaths = glob.glob (searchPath)
		if len (tempPaths) > 0:
			archivePath = tempPaths[0]
		else:
			logging.error ( "GitHubDownload: no archive path for " + packageName + " can't download")
			return False

		if os.path.isdir(archivePath) == False:
		
			DbusIf.UpdateStatus ( message="archive path for " + packageName + " not valid - can't use it",
										where=where, logLevel=ERROR )
			if source == 'GUI':
				DbusIf.UpdateGuiState ( 'ERROR' )
			self.ClearDownloadPending (packageName)
			shutil.rmtree (tempDirectory)
			return False
		# move unpacked archive to package location
		# LOCK this critical section of code to prevent others
		#	from accessing the directory while it's being updated
		tempPackagePath = packagePath + "-temp"
		DbusIf.LOCK ()
		if os.path.exists (packagePath):
			os.rename (packagePath, tempPackagePath)
		shutil.move (archivePath, packagePath)
		if os.path.exists (tempPackagePath):
			shutil.rmtree (tempPackagePath, ignore_errors=True)	# like rm -rf
		DbusIf.UNLOCK ()
		DbusIf.UpdateStatus ( message="", where=where )
		if source == 'GUI':
			DbusIf.UpdateGuiState ( 'ERROR' )
		shutil.rmtree (tempDirectory)
		return True
	# end GitHubDownload

	# compares versions to determine if a download is needed
	#	returns:
	#		'skipped' if versions were not available and couldn't be checked
	#		'download' if a download is needed
	#		'' if download is NOT needed
	
	def downloadNeeded (self, package):
		gitHubVersion = package.GetGitHubVersion ()
		packageVersion = package.GetPackageVersion ()
		gitHubBranch = package.GetGitHubBranch ()
		# no gitHubVersion - skip further checks
		if gitHubVersion == '' or packageVersion == '':
			return 'skipped'

		packageVersionNumber = VersionToNumber( packageVersion )
		gitHubVersionNumber = VersionToNumber( gitHubVersion )
		# if GitHubBranch is a version number then the match must be exact to skip the download
		if gitHubBranch[0] == 'v':
			if gitHubVersionNumber != packageVersionNumber:
				return 'download'
			else:
				return ''
		# otherwise the download is skipped if the gitHubVersion is older
		else:
			if gitHubVersionNumber > packageVersionNumber:
				return 'download'
			else:
				return ''

	# downloads and version checks are spaced out to minimize network traffic
	#	the wait time depends on the download mode:
	#		fast or one pass delays 10 seconds
	#		slow (normal) delays 10 minutes
	#	the time is broken into 5 second intervals so we can check for mode changes
	#		and update download status on the GUI
	#
	#	if the download mode changes while we are waiting, we want to restart the scan
	#
	#	if startTime is specified, it is used to calculate the time for the delay
	#		if not, the current time is used as the start
	#
	#	this routine returns True if the process should continue
	#		or False if we want to reset the loop to the first package

	def wait (self, fastDelay = 5, slowDelay = 30, startTime = None, statusMessage = ""):
		# sleep until it's time to download
		# break into 5 second delays so we can check for mode changes
		# and update status
		if startTime == None:
			startTime = time.perf_counter()
		while True:
			currentMode = DbusIf.GetAutoDownload ()
			# auto-downloads disabled or speeding up loop - start scan with first package
			if currentMode == AUTO_DOWNLOADS_OFF \
						or (currentMode >= FAST_DOWNLOAD and self.lastMode == NORMAL_DOWNLOAD):
				return False	# return with no delay

			# set delay: single pass or fast check
			# does NOT affect delay if no download
			if currentMode == FAST_DOWNLOAD or currentMode == ONE_DOWNLOAD:
				delayTime = fastDelay
			# slow check
			else:
				delayTime = slowDelay
			timeToGo = delayTime + startTime - time.perf_counter()
			
			# normal exit here - wait for download expired, time to do it
			if timeToGo <= 0:
				return True

			time.sleep (5.0)
			if self.threadRunning == False:
				return False	# return with no delay
		
			if timeToGo > 90:
				DbusIf.UpdateStatus ( message=statusMessage + "%0.1f minutes" % ( timeToGo / 60 ), where='Download' )
			elif  timeToGo > 1.0:
				DbusIf.UpdateStatus ( message=statusMessage + "%0.0f seconds" % ( timeToGo ), where='Download' )

		return True


	#	run (the thread)
	#
	# scan packages looking for downloads from GitHub
	# this process paces automatic downloads to minimize network traffic
	#
	# rather than processing the action, it places them on a queue
	# this same queue receives actions from the GUI
	# and from the sister thread that paces automatic installs
	#
	# the actual download occurs from the InstallPackagessThread
	# which pulls actions from a queue
	#
	# run () checks the threadRunning flag and returns if it is False,
	#	essentially taking the thread off-line
	#	the main method should catch the tread with join ()
	# StopThread () is called to shut down the thread

	def StopThread (self):
		logging.info ("attempting to stop DownloadGitHub thread")
		self.threadRunning = False

	def run (self):
		# give time for first GitHub version to be retrieved
		time.sleep (6.0)

		global GitHubVersions
		self.lastMode = AUTO_DOWNLOADS_OFF
		currentMode = AUTO_DOWNLOADS_OFF
		continueLoop = True
		i = 0
		while self.threadRunning:	# loop forever
			self.lastMode = currentMode
			currentMode = DbusIf.GetAutoDownload ()				
			if currentMode == AUTO_DOWNLOADS_OFF:
				# idle message
				DbusIf.UpdateStatus ( message="", where='Download' )
				time.sleep (5.0)
				if self.threadRunning == False:
					return
				continue

			DbusIf.LOCK ()
			packageLength = len (PackageClass.PackageList)

			# loop continues until a download is needed or the end of the list is reached
			# after processing a download, returns here to check the next package
			#
			if i >= packageLength:
				i = 0
			package = PackageClass.PackageList[i]
			packageName = package.PackageName
			DbusIf.UpdateStatus (message="Checking " + packageName, where='Download')

			# update for next pass - DO NOT use i inside the loop after this
			i += 1
			# don't create another download action if one is already pending
			if package.DownloadPending:
				downloadNeeded = ''
			else:
				downloadNeeded = self.downloadNeeded (package)
			DbusIf.UNLOCK ()

			if downloadNeeded == 'download':
				package.DownloadPending = True
				continueLoop =  self.wait (fastDelay = 10, slowDelay = 600, startTime = self.lastAutoDownloadTime,
											statusMessage = packageName + " download begins in " )
				if continueLoop:
					ProcessAction.PushAction ( command="Download:" + packageName, source='AUTO')
					self.lastAutoDownloadTime = time.perf_counter()
				# start loop at beginning because wait () detected a mode change
				else:
					i = 0
			# no download needed - pause then move on to next package
			else:
				if self.threadRunning == False:
					return
				if downloadNeeded == 'skipped':
					message = packageName + " skipped, next in "
				else:
					message = packageName + " checked, next in "
				continueLoop = self.wait (fastDelay = 5, slowDelay = 180, statusMessage = message)
				# start loop at beginning because wait () detected a mode change
				if continueLoop == False:
					i = 0
			
			# end of the package list - need to start with first package in same mode
			# note the reset of i = 0 indicates the loop was restarted in the middle
			# so do not change modes
			if i >= len( PackageClass.PackageList ):
				# change fast loop to slow
				currentMode = DbusIf.GetAutoDownload ()
				if currentMode == FAST_DOWNLOAD:
					DbusIf.SetAutoDownload (NORMAL_DOWNLOAD)
				# disable after one pass
				elif currentMode == ONE_DOWNLOAD:
					DbusIf.SetAutoDownload (AUTO_DOWNLOADS_OFF)
		# end while True
	# end run
# end DownloadGitHubPackagesClass
					

#	InstallPackagesClass
#	Instances:
#		InstallPackages (a separate thread)
#		autoInstallNeeded
#
#	Methods:
#		InstallPackage
#		run (the thread)
#		autoInstallNeeded
#		setInstallPending
#		clearInstallPending
#		setUninstallPending
#		clearUninstallPending
#
# install and uninstall packages
# 	if versions indicate a newer version
# runs as a separate thread since the operations can take a long time
# 	and we need to space them to avoid consuming all CPU resources
#
# packages are automatically installed only
#	if the autoInstall Setting is active
#	package version is newer than installed version
#			or if nothing is installed
#
#	a manual install is performed regardless of versions

class InstallPackagesClass (threading.Thread):

	def __init__(self):
		threading.Thread.__init__(self, name = "InstallPackages")
		DbusIf.SetInstallStatus ("")
		self.threadRunning = True


	#	setInstallPending
	#	clearInstallPending
	#	setUninstallPending
	#	clearUninstallPending

	# the ...Pending flag prevents duplicate actions from piling up
	# automatic downloads are not queued if there is one pending
	#	for a specific package
	#
	# packageName rather than a package list reference (index, etc)
	# 	must be used because the latter can change when packages are removed
	#
	# the pending flag is set at the beginning of the operation
	# 	because the GUI can't do that
	#	this doesn't close the window but narrows it a little
	
	def setInstallPending (self, packageName):
		package = PackageClass.LocatePackage (packageName)
		if package != None:
			package.InstallPending = True

	def clearInstallPending (self, packageName):
		package = PackageClass.LocatePackage (packageName)
		if package != None:
			package.InstallPending = False

	def setUninstallPending (self, packageName):
		package = PackageClass.LocatePackage (packageName)
		if package != None:
			package.UninstallPending = True

	def clearUninstallPending (self, packageName):
		package = PackageClass.LocatePackage (packageName)
		if package != None:
			package.UninstallPending = False

	
	#	InstallPackage
	#
	# this method either installs or uninstalls a package
	# the choice is the direction value:
	# 		'install' or 'uninstall'
	# the operation can take many seconds
	# 	i.e., the time it takes to run the package's setup script
	#	do not call from a thread that should not block

	def InstallPackage ( self, packageName=None, source=None , direction='install' ):
		self.setInstallPending (packageName)
		setupFile = "/data/" + packageName + "/setup"

		if source == 'GUI':
			sendStatusTo = 'Editor'
		elif source == 'AUTO':
			sendStatusTo = 'Install'
			callBack = None

		if os.path.isfile(setupFile) == False:
			DbusIf.UpdateStatus ( message=packageName + "setup file doesn't exist",
											where=sendStatusTo, logLevel=WARNING )
			if source == 'GUI':
				DbusIf.UpdateGuiState ( 'ERROR' )
			DbusIf.LOCK ()
			self.clearInstallPending (packageName)
			DbusIf.UNLOCK ()
			return
		DbusIf.UpdateStatus ( message=direction + "ing " + packageName, where=sendStatusTo )
		cmdReturn = subprocess.run ( [ setupFile, direction, 'deferReboot' ], timeout=120,
				text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
		DbusIf.LOCK ()
		self.clearInstallPending (packageName)
		package = PackageClass.LocatePackage (packageName)
		# reboot requested
		if cmdReturn.returncode == EXIT_SUCCESS:
			package.SetIncompatible ('')	# this marks the package as compatible
			DbusIf.UpdateStatus ( message="", where=sendStatusTo )
			if source == 'GUI':
				DbusIf.UpdateGuiState ( '' )
		elif cmdReturn.returncode == EXIT_REBOOT:
			# set package RebootNeeded so GUI can show the need - does NOT trigger a reboot
			package.SetRebootNeeded (True)

			DbusIf.UpdateStatus ( message=packageName + " " + direction + " requires REBOOT",
											where=sendStatusTo, logLevel=INFO )
			if source == 'GUI':
				DbusIf.UpdateGuiState ( 'RebootNeeded' )
			# auto install triggers a reboot by setting the global flag - reboot handled in main_loop
			else:
				global SystemReboot
				SystemReboot = True
				return
		elif cmdReturn.returncode == EXIT_RUN_AGAIN:
			DbusIf.UpdateStatus ( message=packageName + " setup must be run from command line",
											where=sendStatusTo, logLevel=WARNING )
			if source == 'GUI':
				DbusIf.UpdateGuiState ( 'ERROR' )
		elif cmdReturn.returncode == EXIT_INCOMPATIBLE_VERSION:
			global VenusVersion
			package.SetIncompatible ('VERSION')
			DbusIf.UpdateStatus ( message=packageName + " not compatible with Venus " + VenusVersion,
											where=sendStatusTo, logLevel=WARNING )
			if source == 'GUI':
				DbusIf.UpdateGuiState ( 'ERROR' )
		elif cmdReturn.returncode == EXIT_INCOMPATIBLE_PLATFOM:
			global Platform
			package.SetIncompatible ('PLATFORM')
			DbusIf.UpdateStatus ( message=packageName + " " + direction + " not compatible with " + Platform,
											where=sendStatusTo, logLevel=WARNING )
			if source == 'GUI':
				DbusIf.UpdateGuiState ( 'ERROR' )
		elif cmdReturn.returncode == EXIT_OPTIONS_NOT_SET:
			DbusIf.UpdateStatus ( message=packageName + " " + direction + " setup must be run from the command line",
											where=sendStatusTo, logLevel=WARNING )
			if source == 'GUI':
				DbusIf.UpdateGuiState ( 'ERROR' )
		elif cmdReturn.returncode == EXIT_FILE_SET_ERROR:
			DbusIf.UpdateStatus ( message=packageName + " file set error incomplete",
											where=sendStatusTo, logLevel=WARNING )
			if source == 'GUI':
				DbusIf.UpdateGuiState ( 'ERROR' )
		# unknown error
		elif cmdReturn.returncode != 0:
			DbusIf.UpdateStatus ( message=packageName + " " + direction + " unknown error " + str (cmdReturn.returncode),
											where=sendStatusTo, logLevel=WARNING )
			if source == 'GUI':
				DbusIf.UpdateGuiState ( 'ERROR' )
		DbusIf.UNLOCK ()
	# end InstallPackage ()


	#	autoInstallNeeded
	#
	# compares versions to determine if an install is needed
	#	returns True if an update is needed, False of not
	#
	# called from run() below - package list already locked
	
	def autoInstallNeeded (self, package):
		incompatible = package.GetIncompatible ()
		if incompatible != "":
			return False
		packageVersion = package.GetPackageVersion ()
		installedVersion = package.GetInstalledVersion ()
		# skip further checks if package version string isn't filled in
		updateNeeded = True
		if packageVersion == '':
			packageVersion = "--"
			return False

		if installedVersion == '':
			installedVersion = "--"

		packageVersionNumber = VersionToNumber( packageVersion )
		installedVersionNumber = VersionToNumber( installedVersion )
		# skip install if versions are the same
		if packageVersion == installedVersion:
			return False
		else:
			return True


	#	run (the thread)
	#
	# automatic install packages
	#	pushes request on queue for processing later in another thread
	#		this allows this to run quickly while the package list is locked
	#
	# run () checks the threadRunning flag and returns if it is False,
	#	essentially taking the thread off-line
	#	the main method should catch the tread with join ()
	# StopThread () is called to shut down the thread

	def StopThread (self):
		logging.info ("attempting to stop InstallPackages thread")
		self.threadRunning = False

	def run (self):

		while self.threadRunning:
			DbusIf.LOCK ()
			for package in PackageClass.PackageList:
				if DbusIf.GetAutoInstall() == 1 and self.autoInstallNeeded (package):
					if package.InstallPending == False:
						ProcessAction.PushAction ( command='Install:' + package.PackageName, source='AUTO')
						package.InstallPending = True
			DbusIf.UNLOCK ()
			time.sleep (5.0)

# end InstallPackagesClass



#	MediaScanClass
#	Instances:
#		MediaScan (a separate thread)
#
#	scan removable SD and USB media for packages to be installed
#
#	run () is a separate thread that looks for removable
#	SD cards and USB sticks that appear in /media as separate directories
#	these directories come and go with the insertion and removable of the media
#
#	when new media is detected, it is scanned once then ignored
#	when media is removed, then reinserted, the scan begins again
#
#	packages must be located in the root of the media (no subdirecoties are scanned)
#	and must be an archive with a name ending in .tar.gz
#
#	archives are unpacked to a temp directory in /var/run (a ram disk)
#	verified, then moved into position in /data/<packageName>
#	where the name comes from the unpacked directory name
#	of the form <packageName>-<branch or version>
#
#	actual installation is handled in the InstallPackages run() thread

class MediaScanClass (threading.Thread):


	# transferPackage unpacks the archive and moves it into postion in /data
	#
	#	path is the full path to the archive

	def transferPackage (self, path):
		packageName = os.path.basename (path).split ('-', 1)[0]

		# create an empty temp directory in ram disk
		#	for the following operations
		# directory is unique to this process and thread
		tempDirectory = "/var/run/packageManager" + str(os.getpid ()) + "Media"
		if os.path.exists (tempDirectory):
			shutil.rmtree (tempDirectory)
		os.mkdir (tempDirectory)

		# unpack the archive - result is placed in tempDirectory
		cmdReturn = subprocess.run ( ['tar', '-xzf', path, '-C', tempDirectory ],
										text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if cmdReturn.returncode != 0:
			logging.warning ( "can't unpack " + packageName + " from SD/USB media" )
			shutil.rmtree (tempDirectory)
			return False

		unpackedPath = glob.glob (tempDirectory + '/' + packageName + "*" )[0]
		if os.path.isdir(unpackedPath) == False:
			logging.warning (packageName + " archive not a directory - rejected" )
			shutil.rmtree (tempDirectory)
			return False

		#check for version file
		versionFile = unpackedPath + "/version"
		if not os.path.isfile (versionFile):
			logging.warning (packageName + " version file does not exist - archive rejected" )
			shutil.rmtree (tempDirectory)
			return False
		fd = open (versionFile, 'r')
		version = fd.readline().strip()
		if version[0] != 'v':
			logging.warning (packageName + "invalid version" + version + " - archive rejected")
			shutil.rmtree (tempDirectory)
			return False

		# TODO: do we want to compare versions and only replace the stored version if
		# TODO:		the media version is newer or not an exact match ?????

		# move unpacked archive to package location
		# LOCK this critical section of code to prevent others
		#	from accessing the directory while it's being updated
		DbusIf.UpdateStatus ( message="transfering " + packageName + " from SD/USB", where='Media', logLevel=INFO )
		packagePath = "/data/" + packageName
		tempPackagePath = packagePath + "-temp"
		DbusIf.LOCK () 
		if os.path.exists (tempPackagePath):
			shutil.rmtree (tempPackagePath, ignore_errors=True)	# like rm -rf		
		if os.path.exists (packagePath):
			os.rename (packagePath, tempPackagePath)
		shutil.move (unpackedPath, packagePath)
		if os.path.exists (tempPackagePath):
			shutil.rmtree (tempPackagePath, ignore_errors=True)	# like rm -rf		
		DbusIf.UNLOCK ()
		shutil.rmtree (tempDirectory, ignore_errors=True)
		time.sleep (5.0)
		DbusIf.UpdateStatus ( message="", where='Media')
		return True
	# end transferPackage


	def __init__(self):
		threading.Thread.__init__(self, name = "InstallPackages")
		self.threadRunning = True


	#	run (the thread)
	#
	# run () checks the threadRunning flag and returns if it is False,
	#	essentially taking the thread off-line
	#	the main method should catch the tread with join ()
	# StopThread () is called to shut down the thread

	def StopThread (self):
		logging.info ("attempting to stop MediaScan thread")
		self.threadRunning = False

	def run (self):
		separator = '/'
		root = "/media"
		archiveSuffix = ".tar.gz"

		# list of accepted branch/version substrings
		acceptList = [ "-current", "-latest", "-main", "-test", "-debug", "-beta", "-install", 
							"-0", "-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9" ]

		# keep track of all media that's been scanned so it isn't scanned again
		# media removal removes it from this list
		alreadyScanned = []

		while self.threadRunning:
			drives = os.listdir (root)

			# if previously detected media is removed,
			#	allow it to be scanned again when reinserted
			for scannedDrive in alreadyScanned:
				if not scannedDrive in drives:
					alreadyScanned.remove (scannedDrive)

			for drive in drives:
				drivePath = separator.join ( [ root, drive ] )
				if drive in alreadyScanned:
					continue
				# check any file name ending with the achive suffix
				#	all others are skipped
				for path in glob.iglob (drivePath + "/*" + archiveSuffix):
					accepted = False
					if os.path.isdir (path):
						continue
					else:
						accepted = False
						baseName = os.path.basename (path)
						# verify the file name contains one of the accepted branch/version identifiers
						#	if not found in the list, the archive is rejected
						for accept in acceptList:
							if accept in baseName:
								accepted = True
								break
						# discovered what appears to be a valid archive
						# unpack it, do further tests and move it to /data 
						if accepted:
							self.transferPackage (path)
							if self.threadRunning == False:
								return
						else:
							logging.warning (path + " not a valid archive name - rejected")
				# end for path

				# mark this drive so it won't get scanned again
				#	this prevents repeated installs
				alreadyScanned.append (drive)
			#end for drive

			time.sleep (5.0)
			if self.threadRunning == False:
				return
	# end run ()
# end MediaScanClass


#	AutoRebootCheck
#
# packing installation and uninstallation may require
# 	a system reboot to fully activate it's resources
#
# this method scans the avalilable packages looking
#	for any pending operations (install, uninstall, download)
# it then checks the global RebootNeeded flag
# that is set if a setup script returns EXIT_REBOOT
#
# if no actions are pending and a reboot is needed,
#	AutoRebootCheck returns True

mainloop = None

def	AutoRebootCheck ():
	global SystemReboot
	
	actionsPending = False
	for package in PackageClass.PackageList:
		# check for operations pending
		if package.InstallPending:
			actionsPending = True
		if package.UninstallPending:
			actionsPending = True
		if package.DownloadPending:
			actionsPending = True
	if SystemReboot and actionsPending == False:
		logging.warning ("package install/uninstall requeted a system reboot")
		return True
	else:
		return False


def mainLoop():
	global mainloop
	global rebootNow

	PackageClass.AddStoredPackages ()
	
	PackageClass.GetVersionsFromFiles ()

	AutoRebootCheck ()

	# reboot checks indicates it's time to reboot
	# quit the mainloop which will cause main to continue past mainloop.run () call in main
	if AutoRebootCheck ():
		DbusIf.UpdateStatus ( message="REBOOTING ...", where='Download' )
		DbusIf.UpdateStatus ( message="REBOOTING ...", where='Editor' )

		mainloop.quit()
		return False
	# don't exit
	else:
		return True

#	main
#
# ######## code begins here
# responsible for initialization and starting main loop and threads
# also deals with clean shutdown when main loop exits
#

def main():
	global mainloop
	global SystemReboot
	
	SystemReboot = False

	# set logging level to include info level entries
	logging.basicConfig( format='%(levelname)s:%(message)s', level=logging.WARNING ) # TODO: change to INFO, etc for debug

	logging.warning (">>>> Package Monitor starting")

	from dbus.mainloop.glib import DBusGMainLoop

	# Have a mainloop, so we can send/receive asynchronous calls to and from dbus
	DBusGMainLoop(set_as_default=True)

	# get venus version
	global VenusVersion
	versionFile = "/opt/victronenergy/version"
	try:
		file = open (versionFile, 'r')
	except:
		VenusVersion = ""
	else:
		VenusVersion = file.readline().strip()
		file.close()

	# get platform
	global Platform
	platformFile = "/etc/venus/machine"
	try:
		file = open (platformFile, 'r')
	except:
		Platform = "???"
	else:
		machine = file.readline().strip()
		if machine == "einstein":
			Platform = "Cerbo GX"
		elif machine == "bealglebone":
			Platform = "Venus GX"
		elif machine == "ccgx":
			Platform = "CCGX"
		elif machine == "canvu500":
			Platform = "CanVu 500"
		elif machine == "nanopi":
			Platform = "Multi/Easy Solar GX"
		elif machine == "raspberrypi2":
			Platform = "Raspberry Pi 2/3"
		elif machine == "raspberrypi4":
			Platform = "Raspberry Pi 4"
		else:
			Platform = machine
		file.close()

	# initialze dbus Settings and com.victronenergy.packageMonitor
	global DbusIf
	DbusIf = DbusIfClass ()

	okToProceed = PackageClass.AddPackagesFromDbus ()
	
	if okToProceed:
		PackageClass.AddDefaultPackages ()
		PackageClass.AddStoredPackages ()

		global GitHubVersions
		GitHubVersions = GetGitHubVersionsClass()
		GitHubVersions.start()
		
		global DownloadGitHub
		DownloadGitHub = DownloadGitHubPackagesClass ()
		DownloadGitHub.start()
		
		global InstallPackages
		InstallPackages = InstallPackagesClass ()
		InstallPackages.start()

		global ProcessAction
		ProcessAction = ProcessActionClass ()
		ProcessAction.start()

		global MediaScan
		MediaScan = MediaScanClass ()
		MediaScan.start ()

		# set up main loop - every 5 seconds
		GLib.timeout_add(5000, mainLoop)
		mainloop = GLib.MainLoop()
		mainloop.run()

	# this section of code runs only after the mainloop quits
	#	or if the debus Settings could not be set up (AddPackagesFromDbus fails)

	# stop threads, remove service from dbus
	logging.warning ("stopping threads")
	GitHubVersions.StopThread ()
	DownloadGitHub.StopThread ()
	InstallPackages.StopThread ()
	ProcessAction.StopThread ()
	DbusIf.RemoveDbusService ()
	try:
		GitHubVersions.join (timeout=10.0)
		DownloadGitHub.join (timeout=30.0)
		InstallPackages.join (timeout=10.0)
		ProcessAction.join (timeout=10.0)
	except:
		logging.critical ("attempt to join threads failed - one or more threads failed to exit")
		pass

	# check for reboot
	if SystemReboot:
		logging.critical ("REBOOTING: to complete package installation")

		subprocess.run ( [ 'shutdown', '-r', 'now', 'rebooting to complete package installation' ] )
		# TODO: for debug    subprocess.run ( [ 'shutdown', '-k', 'now', 'simulated reboot - system staying up' ] )

		# insure the package manager service doesn't restart when we exit
		#	it will start up again after the reboot
		subprocess.run ( [ 'svc', '-o', '/service/PackageManager' ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if cmdReturn.returncode != 0:
			logging.warning ("svc to once failed")
			logging.warning (cmdReturn.stderr)


	logging.critical (">>>> PackageMonitor exiting")

	# program exits here

# Always run our main loop so we can process updates
main()





