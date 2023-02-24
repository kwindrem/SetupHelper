#!/usr/bin/env python
#
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
#		/Settings/PackageManager/n/PackageName		can not be edited by the GUI
#		/Settings/PackageManager/n/GitHubUser		can be edited by the GUI
#		/Settings/PackageManager/n/GitHubBranch		can be edited by the GUI
#		/Settings/PackageManager/Count				the number of ACTIVE packages (0 <= n < Count)
#		/Settings/PackageManager/Edit/...			GUI edit package set - all fields editable
#
#		/Settings/PackageManager/GitHubAutoDownload 	set by the GUI to control automatic updates from GitHub
#			0 - no GitHub auto downloads (version checks still occur)
#			1 - updates enabled - one download update every 10 seconds, then one download every 10 minutes
#			3 - one update pass at the fast rate, then to no updates
#				changing to one of the fast scans, starts from the first package

AUTO_DOWNLOADS_OFF = 0
NORMAL_DOWNLOAD = 1
ONE_DOWNLOAD = 2

#		/Settings/PackageManager/AutoInstall
#			0 - no automatic install
#			1 - automatic install after download from GitHub or SD/USB
#
# Additional (volatile) parameters linking packageManager and the GUI are provided in a separate dbus service:
#
#	com.victronenergy.packageManager parameters
#		/Package/n/GitHubVersion 					from GitHub
#		/Package/n/PackageVersion 					from /data <packageName>/version from the package directory
#		/Package/n/InstalledVersion 				from /etc/venus/isInstalled-<packageName>
#		/Package/n/RebootNeeded						indicates a reboot is needed to activate this package
#		/Package/n/Incompatible						indicates if package is or is not compatible with the system
#													'' if compatible
#													'VERSION' if the system version is outside the package's acceptable range
#													'PLATFORM' package can not run on this platform
#													'CMDLINE' setup must be run from command line
#														currently only for Raspberry PI packages only
#
#		for both Settings and the the dbus service:
#			n is a 0-based section used to reference a specific package
#
#	a list of default packages that are not in the main package list
#	these sets are used by the GUI to display a list of packages to be added to the system
#	filled in from /data/SetupHelper/defaultPackageList, but eliminating any packages already in /data
#	the first entry (m = 0) is "new" - for a new package
#	"new" just displays in the packages to add list in the GUI
#	all package additions are done through /Settings/PackageManager/Edit/...
#		/Default/m/PackageName
#		/Default/m/GitHubUser
#		/Default/m/GitHubBranch
#		/DefaultCount					the number of default packages
#
#		m is a 0-based section used to referene a specific default paclage
#
#		/GuiEditAction is a text string representing the action
#		  set by the GUI to trigger an action in PackageManager
#			'install' - install package from /data to the Venus working directories
#			'uninstall' - uninstall package from the working directories
#			'download" - download package from GutHub to /data
#			'add' - add package to package list (after GUI sets .../Edit/...
#			'remove' - remove package from list TBD ?????
# 		 	'reboot' - reboot
#			'restartGui' - restart the GUI
#			'INITIALIZE' - install PackageManager's persistent storage (dbus Settings)
#						so that the storage will be rebuilt when PackageManager restarts
#						PackageManager will exit when this command is received
#			'gitHubScan' - trigger GitHub version update
#						sent when entering the package edit menu or when changing packages within that menu
#
#		the GUI must wait for PackageManager to signal completion of one operation before initiating another
#
#		  set by PackageManager when the task is complete
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
#						GUI sends 'reboot' command to PackageManager
#					Defer
#						GUI sets action to 0
#			'GuiRestartNeeded' - GUI restart needed
#				GUI choices:
#					Do it now
#						GUI sends 'restartGui' command to PackageManager
#					Defer
#						GUI sets action to 0
#
#
#	the following service parameters control settings backup and restore
#		/BackupMediaAvailable		True if suitable SD/USB media is detected by PackageManager
#		/BackupSettingsFileExist	True if PackageManager detected a settings backup file
#		/BackupProgress				used to trigger and provide status of an operation
#									0 nothing happening - set by PackageManager when operaiton completes
#									1 set by the GUI to trigger a backup operation
#									2 set by the GUI to trigger a restore operation
#									3 set by PackageManager to indicate a backup is in progress
#									4 set by PackageManager to indicate a restore is in progress
#
# setup script return codes and install states
EXIT_SUCCESS =				0
EXIT_REBOOT =				123
EXIT_RESTART_GUI =			124
EXIT_INCOMPATIBLE_VERSION =	254
EXIT_INCOMPATIBLE_PLATFOM =	253
EXIT_FILE_SET_ERROR	=		252
EXIT_OPTIONS_NOT_SET =		251
EXIT_RUN_AGAIN = 			250
EXIT_ERROR =				255 # generic error
# install states only
ERROR_NO_SETUP_FILE = 		999
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
#		/Platform					a translated version of the platform (aka machine)
#									machine			Platform
#									ccgx			CCGX
#									einstein		Cerbo GX
#									cerbosgx		Cerbo SGX
#									bealglebone		Venus GX
#									canvu500		CanVu 500
#									nanopi			Multi/Easy Solar GX
#									raspberrypi2	Raspberry Pi 2/3
#									raspberrypi4	Raspberry Pi 4
#
#		/ActionNeeded				informs GUI if further action is needed following a manual operation
#									the operator has the option to defer reboots and GUI restarts (by choosing "Later)
#			''				no action needed
#			'reboot'		reboot needed
#			'guiRestart'	GUI restart needed
#
#			the GUI can respond by setting /GuiEditAction to 'reboot' or 'restartGui'
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
# PackageManager downloads packages from GitHub based on the GitHub version and package (stored) versions:
#	if the GitHub branch is a specific version, the download occurs if the versions differ
#		otherwise the GitHub version must be newer.
#	the archive file is unpacked to a directory in /data named
# 		 <packageName>-<gitHubBranch>.tar.gz, then moved to /data/<packageName>, replacing the original
#
# PackageManager installs the stored verion if the package (stored) and installed versions differ
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
# PackageManager manages flag files in the package folder:
#	DO_NOT_AUTO_ADD				indicates the package was manually removed and PackageManager should not
#								automaticlly add it
#	DO_NOT_AUTO_INSTALL			indicates the package was manually removed and PackageManager should not
#								automatically install it
#
#	these flags are stored in /data/setupOptions/<packageName> which is non-volatile and survives a package download
#
# PackageManager checks removable media (SD cards and USB sticks) for package upgrades or even as a new package
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
#	PackageManager scans /data looking for new packages
#		directory names must not appear to be an archive
#			(include a GitHub branch or version number) (see rejectList below for specifics)
#		the directory must contain a valid version
#		the package must not have been manually removed (DO_NOT_AUTO_ADD flag file set)
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
#
#	PackageManager has a mechnism for backing up and restoring settings:
#		SOME dbus Settings
#		custom icons
#		backing up gui, SetupHelper and PackageManager logs
#
#	PackageManager checks for several flag files on removable media:
#		SETTINGS_AUTO_RESTORE
#			Triggers automatically restore dbus Settings and custom icons
#			A previous settings backup operation must have been performed
#			This creates a settingsBackup fiile and icons folder on the removable media
#			that is used by settings restore (manual or triggered by this flag
#
#		AUTO_INSTALL_PACKAGES
#			If present on the media, any packages found on the media will be automatically installed
#
#		AUTO_UNINSTALL_PACKAGES
#			As above but uninstalls INCLUDING SetupHelper !!!!
#			Only applies if present on media (not in /data or a package direcory)
#
#		AUTO_INSTALL
#			If present in a package directory, the package is installed
#				even if the automatic installs are disabled in the PackageManager menu
#				DO_NOT_AUTO_INSTALL overrides this flag
#
#		ONE_TIME_INSTALL
#			If present in a package directory, the package is automatically installed
#				even if automatic installs are diabled and the DO_NOT_INSTALL flag is set
#			This flag file is removed when the install is performed
#				to prevent repeated installs
#			Packages may be deployed with this flag set to insure it is installed
#				when a new version is transferred from removable media or downloaded from GitHub
#
#		AUTO_EJECT
#			If present, all removable media is ejected after related "automatic" work is finished
#
#		INITIALIZE_PACKAGE_MANAGER
#			If present, the PackageManager's persistent storage (dbus Settings parameters) are initialized
#			and PackageManager restarted
#			On restart, PackageManager will rebuild the dbus Settings from packages found in /data
#			Only custom Git Hub user and branch information is lost.
#
#		A menu item with the same function as INITIALIZE_PACKAGE_MANAGER is also provided
#
# classes/instances/methods:
#	AddRemoveClass
#		AddRemove (thread)
#			StopThread ()
#			run ()
#	DbusIfClass
#		DbusIf
#			SetGuiEditAction ()
#			UpdateStatus ()
#			LocateRawDefaultPackage ()
#			handleGuiEditAction ()
#			UpdatePackageCount ()
#			various Gets and Sets for dbus parameters
#			TransferOldDbusPackageInfo
#			UpdateDefaultPackages ()
#			ReadDefaultPackagelist ()
#			LOCK ()
#			UNLOCK ()
#	PackageClass
#		PackageList [] one per package
#		UpdateDownloadPending ()
#		UpdateInstallPending ()
#		LocatePackage ()
#		RemoveDbusSettings ()
#		settingChangedHandler ()
#		various Gets and Sets
#		AddPackagesFromDbus ()
#		AddStoredPackages ()
#		AddPackage ()
#		RemovePackage ()
#		UpdateFileFlagsAndVersions ()
#		GetAutoAddOk (class method)
#		SetAutoAddOk (class method)
#		AutoInstallOk (class method)
#		UpdateDoNotInstall ()
#		MoveFlagFiles ()
#		InstallVersionCheck ()
#	UpdateGitHubVersionClass
#		UpdateGitHubVersion (thread)
#			updateGitHubVersion ()
#			run ()
#			StopThread ()
#	DownloadGitHubPackagesClass
#		DownloadGitHub (thread)
#			GitHubDownload ()
#			DownloadVersionCheck ()
#			processDownloadQueue ()
#			run ()
#			StopThread ()
#	InstallPackagesClass
#		InstallPackages (thread)
#			InstallPackage ()
#			StopThread ()
#			run ()
#	MediaScanClass
#		MediaScan (thread)
#			transferPackage
#			StopThread ()
#			settingsBackup
#			settingsRestore
#			run ()
#
# global methods:
#	PushAction () 
#	VersionToNumber ()
#	LocatePackagePath ()
#	AutoRebootCheck ()



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
import glob

PythonVersion = sys.version_info
# accommodate both Python 2 and 3
if PythonVersion >= (3, 0):
	import queue
	from gi.repository import GLib
else:
	import Queue as queue
	import gobject as GLib

# add the path to our own packages for import
# use an established Victron service to maintain compatiblity
sys.path.insert(1, os.path.join('/opt/victronenergy/dbus-systemcalc-py', 'ext', 'velib_python'))
from vedbus import VeDbusService
from settingsdevice import SettingsDevice

global DownloadGitHub
global InstallPackages
global AddRemove
global MediaScan
global DbusIf
global Platform
global VenusVersion
global VenusVersionNumber
global SystemReboot
global GuiRestart
global PackageIndex

global AllVersionsRefreshed
	
global InitializePackageManager


#	PushAction
#
# add an action to one of three queues:
#	InstallPackages.InstallQueue for Install and Uninstall actions
#	Download.Download for Download actions
# 	AddRemoveQueue
# commands are added to the queue from the GUI (dbus service change handler)
#	and from the main loop (source = 'AUTO')
# the queue isolates command triggers from processing because processing 
#		can take seconds or minutes
#
# command is a string: action:packageName
#
#	action is a text string: Install, Uninstall, Download, Add, Remove, etc
#	packageName is the name of the package to receive the action
#		for some actions this may be the null string
#
# the command and source are pushed on the queue as a tuple
#
# PushAction sets the ...Pending flag to prevent duplicate operations
#	for a given package
#
# the 'Reboot' and 'restartGui' actions are NOT pushed on any queue
#	they are handled in line since they just set a global flag
#	to be handled in mainLoop

def PushAction (command=None, source=None):
	parts = command.split (":")
	queue = None
	if len (parts) >= 1:
		action = parts[0]
	else:
		action = ""
	if len (parts) >= 2:
		packageName = parts[1]
	else:
		packageName = ""
	if action == 'download':
		DbusIf.LOCK ()
		package = PackageClass.LocatePackage (packageName)
		if package != None:
			package.DownloadPending = True
		DbusIf.UNLOCK ()
		queue = DownloadGitHub.DownloadQueue
		queueText = "Download"
	elif action == 'install' or action == 'uninstall':
		DbusIf.LOCK ()
		package = PackageClass.LocatePackage (packageName)
		if package != None:
			package.InstallPending = True
		DbusIf.UNLOCK ()
		queue = InstallPackages.InstallQueue
		queueText = "Install"
	elif action == 'add' or action == 'remove':
		queue = AddRemove.AddRemoveQueue
		queueText = "AddRemove"
	elif action == 'reboot':
		logging.warning ( "received Reboot request from " + source)
		# set the flag - reboot is done in main_loop
		global SystemReboot
		SystemReboot = True
	elif action == 'restartGui':
		logging.warning ( "received GUI restart request from " + source)
		# set the flag - reboot is done in main_loop
		global GuiRestart
		GuiRestart = True
	elif action == 'INITIALIZE':
		logging.warning ( "received PackageManager INITIALIZE request from " + source)
		# set the flag - Initialize will quit the main loop, then work is done in main
		global InitializePackageManager
		InitializePackageManager = True
	elif action == 'gitHubScan':
		if packageName != "":
			UpdateGitHubVersion.SetPriorityGitHubVersion (packageName)
	# ignore blank action - this occurs when PackageManager changes the action on dBus to 0
	#	which acknowledges a GUI action
	elif action == '':
		return
	else:
		logging.error ("PushAction received unrecognized command: " + command)
		return

	if queue != None:
		try:
			queue.put ( (command, source), block=False )
		except queue.Full:
			logging.error ("command " + command + " from " + source + " lost - " + ququeText + " - queue full")
		except:
			logging.error ("command " + command + " from " + source + " lost - " + ququeText + " - other queue error")
# end PushAction


#	VersionToNumber
#
# convert a version string in the form of vX.Y~Z-large-W to an integer to make comparisions easier
# the ~Z portion indicates a pre-release version so a version without it is later than a version with it
# the -W portion is like the ~Z for large builds
# 	the large portion is IGNORED !!!!
#	note part[0] is always null because there is nothing before v which is used as a separator
#
# the incoming verison string is split on every non-digit character
# the first three of those pieces are combined into a single integer
# additional pieces are ignored
#
#	for example v1.2~3 			would be  1002003
#	for example v11.22.33  		would be 11022033
#	for example v11.22-large-33	would be 11022999
# an empty file or one that contains "unknown" or does not beging with 'v'
# 	has a version number = 0
#
# the separators ~, b, a and d are given special significance
#	indicating beta (~ and b), alpha or develompent releases
#	which are prioritized: release is the highest, then beta, then alpha then development
#	by spliting the third number range into individual ranges
#	a released version is given the highest numerical value: 999
#		none for release	--		999
#		~ or b for beta		0-398	600-998
#		a for alpha 		0-299	300-599
#		d for development	0-299	0-299
#
#	returns the version number

def VersionToNumber (version):
	if version == None or version == "" or version[0] != 'v':
		return 0

	version = version.replace ("large","L")
	parts = re.split ('\D', version[1:])

	preReleasePart = False
	# assemble core version number from major, minor and preRelease parts
	versionNumber = 0
	if len(parts) >= 1:
		if parts[0].isdigit():
			versionNumber += int ( parts[0] ) * 1000000
	if len(parts) >= 2:
		if parts[1].isdigit():
			versionNumber += int ( parts[1] ) * 1000
	if len(parts) >= 3:
		if parts[2].isdigit():
			versionNumber += int ( parts[2] )
			preReleasePart = True

	# adjust based on type
	if '~' in version:
		versionNumber += 600
	elif 'b' in version:
		versionNumber += 600
	elif 'a' in version:
		versionNumber += 300
	# a release version should not contain a third part, but use it as-is if present
	elif not preReleasePart:
		versionNumber += 999
	return versionNumber


#	LocatePackagePath
#
# attempt to locate a package directory
#
# all directories at the current level are checked
#	to see if they contain a file named 'version'
#	indicating a package directory has been found
#
#	further, the version file must begin with 'v'
#
# if so, that path is returned
#
# if a directory NOT containing 'version' is found
#	this method is called again to look inside that directory
#
# if nothing is found, the method returns None
#
# all recursive calls will return with the located package or None
#	so the original caller will have the path to the package or None

def LocatePackagePath (origPath):
	paths = os.listdir (origPath)
	for path in paths:
		newPath = origPath +'/' + path
		if os.path.isdir(newPath):
			# found version file, make sure it is "valid"
			versionFile = newPath + "/version"
			if os.path.isfile( versionFile ):
				fd = open ( versionFile, 'r' )
				version = fd.readline().strip()
				fd.close()
				if version[0] == 'v':
					return newPath
				else:
					logging.error ("version file not a valid version " + versionFile + " = " + version )
			else:
				packageDir = locatePackagePath (newPath)
				# found a package directory
				if packageDir != None:
					return packageDir
				# nothing found - continue looking in this directory
				else:
					continue
	return None


#	AddRemoveClass
#	Instances:
#		AddRemove (a separate thread)
#
#	Methods:
#		run ( the thread )
#		StopThread ()
#
#	Install and Uninstall actions are processed by
# 		the InstallPackages thread
#	Download actions are processed by
#		the DownloadGitHub thread
#	Add and Remove actions are processed in this thread
#
# a queue isolates the caller from processing time
#	and interactions with the dbus object
#		(can't update the dbus object from it's handler !)
#
# some actions called may take seconds or minutes (based on internet speed) !!!!
#
# the queue entries are: ("action":"packageName")
#	this decouples the action from the current package list which could be changing
#	allowing the operation to proceed without locking the list

class AddRemoveClass (threading.Thread):

	def __init__(self):
		threading.Thread.__init__(self)
		self.AddRemoveQueue = queue.Queue (maxsize = 10)
		self.threadRunning = True
		

	
	#	AddRemove run (the thread), StopThread
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
		logging.info ("attempting to stop AddRemove thread")
		self.threadRunning = False
		self.AddRemoveQueue.put ( ('STOP', ''), block=False )

	#	AddRemove run ()
	#
	# process package Add/Remove actions
	def run (self):
		while self.threadRunning:
			try:
				command = self.AddRemoveQueue.get ()
			except:
				logging.error ("pull from AddRemoveQueue failed")
				continue
			if len (command) == 0:
				logging.error ("pull from AddRemove queue failed - empty comand")
				time.sleep (5.0)
				continue
			# thread shutting down
			if command [0] == 'STOP' or self.threadRunning == False:
				return

			# separate command, source tuple
			# and separate action and packageName
			if len (command) >= 2:
				parts = command[0].split (":")
				if len (parts) >= 2:
					action = parts[0].strip ()
					packageName = parts[1].strip ()
				else:
					logging.error ("AddRemoveQueue - no action and/or package name - discarding", command)
					time.sleep (5.0)
					continue
				source = command[1]
			else:
				logging.error ("AddRemoveQueue - no command and/or source - discarding", command)
				time.sleep (5.0)
				continue

			if action == 'add':
				packageDir = "/data/" + packageName
				if source == 'GUI':
					user = DbusIf.EditPackage.GitHubUser
					branch = DbusIf.EditPackage.GitHubBranch
				else:
					user = ""
					branch = ""
				# try to get GitHub info from package directory
				if user == "":
					if os.path.isdir (packageDir):
						gitHubInfoFile = packageDir + "/gitHubInfo"
						try:
							fd = open (gitHubInfoFile, 'r')
							parts = fd.readline().strip ().split (':')
							fd.close()
						except:
							parts = ""
						if len (parts) >= 2:
							user = parts[0]
							branch = parts[1]
				# still nothing - try to get GitHub info from default package list
				if user == "":
					default = DbusIf.LocateRawDefaultPackage (packageName)
					if default != None:
						user = default[1]
						branch = default[2]

				PackageClass.AddPackage (packageName = packageName, source=source,
								gitHubUser=user, gitHubBranch=branch )

			elif action == 'remove':
				PackageClass.RemovePackage ( packageName=packageName )

			else:
				logging.warning ( "received invalid action " + command + " from " + source + " - discarding" )
		# end while True
	# end run ()
# end AddRemoveClass


#	DbusIfClass
#	Instances:
#		DbusIf
#
#	Methods:
#		SetGuiEditAction
#		UpdateStatus
#		LocateRawDefaultPackage
#		handleGuiEditAction
#		UpdatePackageCount
#		RemoveDbusSettings
#		TransferOldDbusPackageInfo
#		UpdateDefaultPackages ()
#		ReadDefaultPackagelist ()
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
#	while it is bein`g changed in another
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
#	LocateRawDefaultPackage is used to retrieve the default from local storage
#		rather than pulling from dbus or reading the file again

class DbusIfClass:

	#		RemoveDbusSettings
	# remove the dbus Settings paths for package
	# package Settings are removed
	# this is called when removing a package
	# settings to be removed are passed as a list (settingsList)
	# this gets reformatted for the call to dbus

	@classmethod
	def RemoveDbusSettings (cls, settingsList):

		# format the list of settings to be removed
		i = 0
		while i < len (settingsList):
			if i == 0:
				settingsToRemove = '%[ "' + settingsList[i]
			else:
				settingsToRemove += '" , "' + settingsList[i]
			i += 1
		settingsToRemove += '" ]'

		# remove the dbus Settings paths - via the command line 
		try:
			proc = subprocess.Popen (['dbus', '-y', 'com.victronenergy.settings', '/', 'RemoveSettings', settingsToRemove  ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		except:
			logging.error ("dbus RemoveSettings call failed")
		else:
			proc.wait()
			# convert from binary to string
			out, err = proc.communicate ()
			stdout = out.decode ().strip ()
			stderr = err.decode ().strip ()
			returnCode = proc.returncode
			if returnCode != 0:
				logging.error ("dbus RemoveSettings failed " + str (returnCode))
				logging.error ("stderr: " + stderr)


	#	TransferOldDbusPackageInfo
	# PackageManager dbus storage was moved
	# from ...PackageMonitor... to ...PackageManager...
	# this method moves the info to the new location and deletes the old Settings
	# this assumes the new dbus environment is already set up
	# the transfer is only done if the new location has no packages
	# should only be called from initialization so we don't LOCK while accessing the package list


	@classmethod
	def TransferOldDbusPackageInfo (cls):
		bus = dbus.SystemBus()
		oldPath = "/Settings/PackageMonitor"
		newPath = "/Settings/PackageManager"
		try:
			oldCount = bus.get_object("com.victronenergy.settings", oldPath + "/Count").GetValue()
		# nothing to tranfer/delete
		except:
			return


		try:
			newCount = bus.get_object("com.victronenergy.settings", newPath + "/Count").GetValue()
		except:
			logging.error ("PackageManager dbus Settings has no package count")
			return

		# if the new dbus info has no packages, transfer them from the old location
		if newCount == 0:
			transferPackages = True
		else:
			transferPackages = False

		logging.warning ("moving PackageManager dbus settings from old location")
		
		# remove package-related Settings
		i = 0
		while i < oldCount:
			oldNamePath = oldPath + '/' + str (i) + "/PackageName"
			oldUserPath = oldPath + '/' + str (i) + "/GitHubUser"
			oldBranchPath = oldPath + '/' + str (i) + "/GitHubBranch"

			# create a new package and transfer old info to it
			try:
				name = bus.get_object("com.victronenergy.settings", oldNamePath).GetValue ()
			except:
				name = None
			if transferPackages and name != None:
				logging.warning ("moving " + name + " settings")

				try:
					user = bus.get_object("com.victronenergy.settings", (oldUserPath)).GetValue ()
				except:
					user = "?"
				try:
					branch = bus.get_object("com.victronenergy.settings", oldBranchPath).GetValue ()
				except:
					branch = "?"

				PackageClass.AddPackage (packageName=name, source='TRANSFER',
						gitHubUser= user, gitHubBranch=branch )

			# remove the old package-related dbus Settings
			cls.RemoveDbusSettings ( [oldNamePath, oldUserPath, oldBranchPath ] )
			i += 1

		# transfer and remove Settings not part of a package
		if transferPackages:
			
			DbusIf.SetAutoInstall ( bus.get_object("com.victronenergy.settings",
							oldPath + "/AutoInstall").GetValue () )
			DbusIf.SetAutoDownload ( bus.get_object("com.victronenergy.settings",
							oldPath + "/GitHubAutoDownload").GetValue () )
		otherSettings = [oldPath + "/AutoInstall",
							oldPath + "/GitHubAutoDownload",
							oldPath + "/Edit/GitHubBranch",
							oldPath + "/Edit/GitHubUser",
							oldPath + "/Edit/PackageName",
							oldPath + "/Count"
						]
		cls.RemoveDbusSettings ( otherSettings )

	
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
	# the GUI uses PackageManager service /GuiEditAction
	# to inform PackageManager of an action
	# a command is formed as "action":"packageName"
	#
	#	action is a text string: install, uninstall, download, etc
	#	packageName is the name of the package to receive the action
	#		for some acitons this may be the null string
	# this handler disposes of the request quickly by pushing
	#	the command onto a queue for later processing

	def handleGuiEditAction (self, path, command):
		global PushAction
		PushAction ( command=command, source='GUI' )

		return True	# True acknowledges the dbus change - other wise dbus parameter does not change

	def UpdatePackageCount (self):
		count = len(PackageClass.PackageList)
		self.DbusSettings['packageCount'] = count
	def GetPackageCount (self):
		return self.DbusSettings['packageCount']
	def SetAutoDownload (self, value):
		self.DbusSettings['autoDownload'] = value
	def GetAutoDownloadMode (self):
		return self.DbusSettings['autoDownload']
	def GetAutoInstall (self):
		return self.DbusSettings['autoInstall']
	def SetAutoInstall (self, value):
		self.DbusSettings['autoInstall'] = value
	def SetGitHubUpdateStatus (self, value):
		self.DbusService['/GitHubUpdateStatus'] = value
	def SetInstallStatus (self, value):
		self.DbusService['/InstallStatus'] = value
	def SetMediaStatus (self, value):
		self.DbusService['/MediaUpdateStatus'] = value

	def SetDefaultCount (self, value):
		self.DbusService['/DefaultCount'] = value
	def GetDefaultCount (self):
		return self.DbusService['/DefaultCount']

	def SetBackupMediaAvailable (self, value):
		if value == True:
			dbusValue = 1
		else:
			dbusValue = 0
		self.DbusService['/BackupMediaAvailable'] = dbusValue
	def GetBackupMediaAvailable (self):
		if self.DbusService['/BackupMediaAvailable'] == 1:
			return True
		else:
			return True

	def SetBackupSettingsFileExist (self, value):
		if value == True:
			dbusValue = 1
		else:
			dbusValue = 0
		self.DbusService['/BackupSettingsFileExist'] = dbusValue
	def GetBackupSettingsFileExist (self):
		if self.DbusService['/BackupSettingsFileExist'] == 1:
			return True
		else:
			return True

	def SetBackupProgress (self, value):
		self.DbusService['/BackupProgress'] = value
	def GetBackupProgress (self):
		return self.DbusService['/BackupProgress']


	#	SetGuiEditAction
	# is part of the PackageManager to GUI communication
	# the GUI set's an action triggering some processing here
	# 	via the dbus change handler
	# PM updates this dbus value when processing completes 
	#	signaling either success or failure
	
	def SetGuiEditAction (self, value):
		self.DbusService['/GuiEditAction'] = value
	def GetGuiEditAction (self):
		return self.DbusService['/GuiEditAction']
	def SetEditStatus (self, message):
		self.DbusService['/GuiEditStatus'] = message

	def SetActionNeeded (self, message):
		self.DbusService['/ActionNeeded'] = message

	# search RAW default package list for packageName
	# and return the pointer if found
	#	otherwise return None
	#
	# Note: the raw default package list is built during init
	#	then never changes so LOCK/UNLOCK is NOT needed
	#
	# rawDefaultPackages is a list of tuples:
	#	(packageName, gitHubUser, gitHubBranch)
	#
	# if a packageName match is found, the tuple is returned
	#	otherwise None is retuned

	def LocateRawDefaultPackage (self, packageName):
		
		for default in self.rawDefaultPackages:
			if packageName == default[0]:
				return default
		return None


	#	UpdateDefaultPackages
	#
	# refreshes the defaultPackageList to include only packages NOT be in PackageList
	# this also updates the dbus default packages used by the GUI Add Package menu
	# skip unless package was added/removed ????
	# alwaysRun forces processing for the init pass from main ()

	def UpdateDefaultPackages (self, alwaysRun = False):
		if alwaysRun == False and self.RefreshDefaultPackages == False:
			return
		self.RefreshDefaultPackages = False
		
		DbusIf.LOCK ()
		# don't touch "new" entry (index 0)
		index = 1
		oldDefaultCount = len (self.defaultPackageList)
		for default in self.rawDefaultPackages:
			# if not in the main package list, add it to the default package list
			name = default[0]
			if PackageClass.LocatePackage (name) == None:
				user = default[1]
				branch = default[2]
				prefix = '/Default/' + str (index) + '/'
				# this entry already exists - update it
				if index < oldDefaultCount:
					# name has changed, update the entry (local and dbus)
					if (name != self.defaultPackageList[index][0]):
						self.defaultPackageList[index] = default
						self.DbusService[prefix + 'PackageName'] = name
						self.DbusService[prefix + 'GitHubUser'] = user
						self.DbusService[prefix + 'GitHubBranch'] = branch
				# path doesn't yet exist, add it	
				else:
					self.defaultPackageList.append (default)
					self.DbusService.add_path (prefix + 'PackageName', name )
					self.DbusService.add_path (prefix + 'GitHubUser', user )
					self.DbusService.add_path (prefix + 'GitHubBranch', branch )

				index += 1

		self.DbusService['/DefaultCount'] = index 

		# clear out any remaining path values
		while index < oldDefaultCount:
			prefix = '/Default/' + str (index) + '/'
			self.defaultPackageList[index] = ( "", "", "" )
			self.DbusService[prefix + 'PackageName'] = ""
			self.DbusService[prefix + 'GitHubUser'] = ""
			self.DbusService[prefix + 'GitHubBranch'] = ""
			index += 1

		DbusIf.UNLOCK ()


	#	ReadDefaultPackagelist
	#
	# read in the default packages list file and store info locally for faster access later
	# this list is only used to populate the defaultPackageList which excludes packages that
	#	are in the main Packagelist

	def ReadDefaultPackagelist (self):

		try:
			listFile = open ("/data/SetupHelper/defaultPackageList", 'r')
		except:
			logging.error ("no defaultPackageList " + listFileName)
		else:
			for line in listFile:
				parts = line.split ()
				if len(parts) < 3 or line[0] == "#":
					continue
				self.rawDefaultPackages.append ( ( parts[0], parts[1], parts[2] ) )
			listFile.close ()


	# LOCK and UNLOCK - capitals used to make it easier to identify in the code
	#
	# these protect the package list from changing while the list is being accessed
	
	def LOCK (self):
		self.lock.acquire ()
	def UNLOCK (self):
		self.lock.release ()


	def __init__(self):
		self.lock = threading.RLock()

		settingsList = {'packageCount': [ '/Settings/PackageManager/Count', 0, 0, 0 ],
						'autoDownload': [ '/Settings/PackageManager/GitHubAutoDownload', 0, 0, 0 ],
						'autoInstall': [ '/Settings/PackageManager/AutoInstall', 0, 0, 0 ],
						}
		self.DbusSettings = SettingsDevice(bus=dbus.SystemBus(), supportedSettings=settingsList,
								timeout = 10, eventCallback=None )

		self.DbusService = VeDbusService ('com.victronenergy.packageManager', bus = dbus.SystemBus())
		self.DbusService.add_mandatory_paths (
							processname = 'PackageManager', processversion = 1.0, connection = 'none',
							deviceinstance = 0, productid = 1, productname = 'Package Manager',
							firmwareversion = 1, hardwareversion = 0, connected = 1)
		self.DbusService.add_path ( '/GitHubUpdateStatus', "", writeable = True )
		self.DbusService.add_path ( '/InstallStatus', "", writeable = True )
		self.DbusService.add_path ( '/MediaUpdateStatus', "", writeable = True )
		self.DbusService.add_path ( '/GuiEditStatus', "", writeable = True )

		global Platform
		self.DbusService.add_path ( '/Platform', Platform )

		self.DbusService.add_path ( '/GuiEditAction', "", writeable = True,
										onchangecallback = self.handleGuiEditAction )

		# initialize default package list to empty - entries will be added later
		self.DbusService.add_path ('/DefaultCount', 0 )

		# a special package used for editing a package prior to adding it to Package list
		self.EditPackage = PackageClass ( section = "Edit", packageName = "new" )
		
		self.rawDefaultPackages = []
		self.defaultPackageList = []

		# create first default package, place where a new package is entered from scratch
		self.defaultPackageList.append ( ("new", "", "") )
		self.DbusService.add_path ( "/Default/0/PackageName", "new" )
		self.DbusService.add_path ( "/Default/0/GitHubUser", "" )
		self.DbusService.add_path ( "/Default/0/GitHubBranch", "" )

		# used to notify the GUI that an action is required to complete a manual installation
		#	the operator has the option to defer reboot and GUI restart operations
		#	if they do, this parameter is set and a button appears on the main Package manager menu

		self.DbusService.add_path ( "/ActionNeeded", '' )

		self.RefreshDefaultPackages = False

		self.DbusService.add_path ( '/BackupMediaAvailable', 0, writeable = True )
		self.DbusService.add_path ( '/BackupSettingsFileExist', 0, writeable = True )
		self.DbusService.add_path ( '/BackupProgress', 0, writeable = True )


	#	RemoveDbusService
	#  deletes the dbus service

	def RemoveDbusService (self):
		logging.warning ("shutting down com.victronenergy.packageManager dbus service")
		self.DbusService.__del__()
	
# end DbusIf


#	PackageClass
#	Instances:
#		one per package
#
#	Methods:
#		LocatePackage
#		various Gets and Sets
#		UpdateDownloadPending () (class method)
#		UpdateInstallPending () (class method)
#		AddPackagesFromDbus (class method)
#		AddStoredPackages (class method)
#		AddPackage (class method)
#		RemovePackage (class method)
#		UpdateFileFlagsAndVersions ()
#		GetAutoAddOk (class method)
#		SetAutoAddOk (class method)
#		AutoInstallOk (class method)
#		UpdateDoNotInstall ()
#		MoveFlagFiles ()
#		InstallVersionCheck ()
#
#	Globals:
#		DbusSettings (for per-package settings)
#		DbusService (for per-package parameters)
#		DownloadPending
#		InstallPending
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

	# search PackageList for packageName
	# and return the package pointer if found
	#	otherwise return None
	#
	# Note: this method should be called with LOCK () set
	#	and use the returned value before UNLOCK ()
	#	to avoid unpredictable results

	@classmethod
	def LocatePackage (cls, packageName):
		for package in PackageClass.PackageList:
			if packageName == package.PackageName:
				return package
		return None


	# this set of methods manages the flag files that control
	#	automaticly adding and installing packages
	# if a package is manually removed, it should not
	#	be readded automatically
	# ditto for manual uninstall
	#

	@classmethod
	def GetAutoAddOk (cls, packageName):
		if packageName == None:
			logging.error ("GetAutoAddOk - no packageName")
			return False

		flagFile = "/data/setupOptions/" + packageName + "/DO_NOT_AUTO_ADD"
		if os.path.exists (flagFile):
			return False
		else:
			return True


	@classmethod
	def SetAutoAddOk (cls, packageName, state):
		if packageName == None:
			logging.error ("SetAutoAddOk - no packageName")
			return

		# if package options directory exists set/clear auto add flag
		# directory may not exist if package was never downloaded or transferred from media
		#	or if package was added manually then never acted on
		optionsDir = "/data/setupOptions/" + packageName
		if os.path.exists (optionsDir):
			flagFile = optionsDir + "/DO_NOT_AUTO_ADD"
			# permit auto add
			if state == True:
				if os.path.exists (flagFile):
					os.remove (flagFile)
			# block auto add
			else:
				if not os.path.exists (flagFile):
					# equivalent to unix touch command
					open (flagFile, 'a').close()


	def UpdateDoNotInstall (self, state):
		packageName = self.PackageName
		if packageName == None:
			logging.error ("UpdateDoNotInstall - no packageName")
			return

		# if package options directory exists set/clear auto install flag
		# directory may not exist if package was never downloaded or transferred from media
		#	or if package was added manually then never acted on
		optionsDir = "/data/setupOptions/" + packageName
		if os.path.exists (optionsDir):
			flagFile = optionsDir + "/DO_NOT_AUTO_INSTALL"
			# permit auto installs
			if state == True:
				if os.path.exists (flagFile):
					os.remove (flagFile)
			# block auto install
			else:
				if not os.path.exists (flagFile):
					open (flagFile, 'a').close()
	
	# move flag files that prevent automatic downloads or installs
	#	from <package> to /setupOptions/<package>
	# called only during init

	def MoveFlagFiles (self):
		packageName = self.PackageName
		if packageName == None:
			logging.error ("MoveFlagFiles - no packageName")
			return

		# nothing to do if package directory doesn't exist
		packageDir = "/data/" + packageName
		if not os.path.isdir (packageDir):
			return

		# create setupOptions directory if it doesn't already exist
		#	this would happen if the package was being added / installed for the first time
		optionsDir = "/data/setupOptions/"
		optionsPath = optionsDir + packageName
		if not os.path.isdir (optionsDir):
			os.mkdir (optionsDir)
		if not os.path.isdir (optionsPath):
			os.mkdir (optionsPath)

		# move auto add block flag
		oldFlag = packageDir + "/REMOVED"
		flagFile = optionsPath +  "/DO_NOT_AUTO_ADD"
		if os.path.exists (oldFlag):
			open (flagFile, 'a').close()
			os.remove (oldFlag)

		# move auto install block flag
		oldFlag = packageDir + "/DO_NOT_AUTO_INSTALL"
		flagFile = optionsPath +  "/DO_NOT_AUTO_INSTALL"
		if os.path.exists (oldFlag):
			open (flagFile, 'a').close()
			os.remove (oldFlag)
		

	#	InstallVersionCheck
	#
	# compares versions to determine if an install is needed
	#	returns True if an update is needed, False of not
	#
	# called from main loop
	
	def InstallVersionCheck (self):

		if self.Incompatible != "":
			return False

		packageVersion = self.PackageVersion
		# skip further checks if package version string isn't filled in
		if packageVersion == "" or packageVersion[0] != 'v':
			return False

		# skip install if versions are the same
		if self.PackageVersionNumber == self.InstalledVersionNumber:
			return False
		else:
			return True


	def SetPackageName (self, newName):
		self.DbusSettings['packageName'] = newName
		self.PackageName = newName

	def SetInstalledVersion (self, version):
		global VersionToNumber
		self.InstalledVersion = version
		self.InstalledVersionNumber = VersionToNumber (version)
		if self.installedVersionPath != "":
			DbusIf.DbusService[self.installedVersionPath] = version	

	def SetPackageVersion (self, version):
		global VersionToNumber
		self.PackageVersion = version
		self.PackageVersionNumber = VersionToNumber (version)
		if self.packageVersionPath != "":
			DbusIf.DbusService[self.packageVersionPath] = version	

	def SetGitHubVersion (self, version):
		global VersionToNumber
		self.GitHubVersion = version
		self.GitHubVersionNumber = VersionToNumber (version)
		if self.gitHubVersionPath != "":
			DbusIf.DbusService[self.gitHubVersionPath] = version

	def SetGitHubUser (self, user):
		self.GitHubUser = user
		self.DbusSettings['gitHubUser'] = user

	def SetGitHubBranch (self, branch):
		self.GitHubBranch = branch
		self.DbusSettings['gitHubBranch'] = branch

	def SetIncompatible (self, value):
		self.Incompatible = value
		if self.incompatiblePath != "":
			DbusIf.DbusService[self.incompatiblePath] = value	

	def SetRebootNeeded (self, value):
		self.RebootNeeded = value
		if self.rebootNeededPath != "":
			if value == True:
				DbusIf.DbusService[self.rebootNeededPath] = 1
			else:
				DbusIf.DbusService[self.rebootNeededPath] = 0
	def SetGuiRestartNeeded (self, value):
		self.GuiRestartNeeded = value
		if self.guiRestartNeededPath != "":
			if value == True:
				DbusIf.DbusService[self.guiRestartNeededPath] = 1
			else:
				DbusIf.DbusService[self.guiRestartNeededPath] = 0


	def settingChangedHandler (self, name, old, new):
		# when dbus information changes, need to refresh local mirrors
		if name == 'packageName':
			self.PackageName = new
		elif name == 'gitHubBranch':
			self.GitHubBranch = new
			if self.PackageName != None and self.PackageName != "":
				UpdateGitHubVersion.SetPriorityGitHubVersion ( self.PackageName )
		elif name == 'gitHubUser':
			self.GitHubUser = new
			if self.PackageName != None and self.PackageName != "":
				UpdateGitHubVersion.SetPriorityGitHubVersion ( self.PackageName )

	def __init__( self, section, packageName = None ):
		# add package versions if it's a real package (not Edit)
		if section != 'Edit':
			section = str (section)
			self.gitHubVersionPath = '/Package/' + section + '/GitHubVersion'
			self.packageVersionPath = '/Package/' + section + '/PackageVersion'
			self.installedVersionPath = '/Package/' + section + '/InstalledVersion'
			self.rebootNeededPath = '/Package/' + section + '/RebootNeeded'
			self.guiRestartNeededPath = '/Package/' + section + '/GuiRestartNeeded'
			self.incompatiblePath = '/Package/' + section + '/Incompatible'

			# create service paths if they don't already exist
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
				DbusIf.DbusService.add_path (self.rebootNeededPath, False )
			try:
				foo = DbusIf.DbusService[self.guiRestartNeededPath]
			except:
				DbusIf.DbusService.add_path (self.guiRestartNeededPath, False )
			try:
				foo = DbusIf.DbusService[self.incompatiblePath]
			except:
				DbusIf.DbusService.add_path (self.incompatiblePath, "" )


		self.packageNamePath = '/Settings/PackageManager/' + section + '/PackageName'
		self.gitHubUserPath = '/Settings/PackageManager/' + section + '/GitHubUser'
		self.gitHubBranchPath = '/Settings/PackageManager/' + section + '/GitHubBranch'

		# mirror of dbus parameters to speed access
		self.InstalledVersion = ""
		self.InstalledVersionNumber = 0
		self.PackageVersion = ""
		self.PackageVersionNumber = 0
		self.GitHubVersion = ""
		self.GitHubVersionNumber = 0
		self.GitHubUser = "?"
		self.GitHubBranch = "?"
		self.Incompatible = ''
		self.RebootNeeded = ''
		self.GuiRestartNeeded = ''

		# needed because settingChangeHandler may be called as soon as SettingsDevice is called
		#	which is before actual package name is set below
		#	so this avoids a crash
		self.PackageName = ""

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
		#	 this happens when adding a package when it is already in dbus
		else:
			self.PackageName = self.DbusSettings['packageName']
		self.GitHubUser = self.DbusSettings['gitHubUser']
		self.GitHubBranch = self.DbusSettings['gitHubBranch']
		
		self.section = section
		# these flags are used to insure multiple actions aren't executed on top of each other
		self.DownloadPending = False
		self.InstallPending = False

		self.AutoInstallOk = False
		self.FileSetOk = False

		self.lastGitHubVersionUpdate = 0

	# dbus Settings is the primary non-volatile storage for packageManager
	# upon startup, PackageList [] is empty and we need to populate it
	# from previous dBus Settings in /Settings/PackageManager/...
	# this is a special case that can't use AddPackage below:
	#	we do not want to create any new Settings !!
	#	it should be "safe" to limit the serch to 0 to < packageCount
	#	we also don't specify any parameters other than the section (index)
	#
	# NOTE: this method is called before threads are created so do not LOCK
	#
	# returns False if couldn't get the package count from dbus
	#	otherwise returns True
	# no package count on dbus is an error that would prevent continuing
	# this should never happen since the DbusIf is instantiated before this call
	#	which creates /Count if it does not exist

	@classmethod
	def AddPackagesFromDbus (cls):
		global DbusIf
		packageCount = DbusIf.GetPackageCount()
		if packageCount == None:
			logging.critical ("dbus PackageManager Settings not set up -- can't continue")
			return False
		i = 0
		while i < packageCount:
			# no package name tells PackageClas init to pull package name from dbus
			cls.PackageList.append (PackageClass ( section = i ) )
			i += 1
		return True


	#	PackageNameValid
	# checks the package name to see if it is valid
	#
	# invalid names contain strings in the rejectList
	#
	# returns true if name is OK, false if in the reject list

	rejectList = [ "-current", "-latest", "-main", "-test", "-temp", "-debug", "-beta", "-backup1", "-backup2",
					"-blind", "-0", "-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9", "ccgx", " " ]

	@classmethod
	def PackageNameValid (cls, packageName):

		if packageName == None or packageName == "":
			return False

		for reject in cls.rejectList:
			if reject in packageName:
				return False

		return True


	#	AddStoredPackages
	# add packages stored in /data to the package list
	# in order to qualify as a package:
	#	must be a directory
	#	name must not contain strings in the rejectList
	#	name must not include any spaces
	#	diretory must contain a file named version
	#	first character of version file must be 'v'
	#	name must be unique - that is not match any existing packages

	@classmethod
	def AddStoredPackages (cls):
		for path in os.listdir ("/data"):
			packageDir = "/data/" + path
			if not os.path.isdir (packageDir):
				continue
			packageName = path
			if not PackageClass.PackageNameValid (packageName):
				continue

			# skip if package was manually removed
			if not PackageClass.GetAutoAddOk (packageName):
				continue
			# skip if package is for Raspberry PI only and platform is not
			global Platform
			if os.path.exists (packageDir + "/raspberryPiOnly") and Platform[0:4] != 'Rasp':
				continue

			# check for a setup file - skip if none
			if not os.path.exists (packageDir + "/setup"):
				continue

			# check for a valid version file - skip if no file or not a valid version
			versionFile = packageDir + "/version"
			try:
				fd = open (versionFile, 'r')
				version = fd.readline().strip()
				fd.close ()
			except:
				continue
			if version[0] != 'v':
				continue

			# continue only if package is unique
			DbusIf.LOCK ()
			package = cls.LocatePackage (packageName)
			DbusIf.UNLOCK ()			
			if package == None:
				PushAction (command='add:' + packageName, source='AUTO')
	
	# the DownloadPending and InstallPending flags prevent duplicate actions for the same package
	#	and holds off reboots and GUI resets until all actions are complete
	#
	# packageName rather than a package list reference (index)
	# 	is used because the latter can change when packages are removed
	# if you have a package pointer, set the parameter directly to save time
	
	@classmethod
	def UpdateDownloadPending (self, packageName, state):
		DbusIf.LOCK ()
		package = PackageClass.LocatePackage (packageName)
		if package != None:
			package.DownloadPending = state
		DbusIf.UNLOCK ()

	@classmethod
	def UpdateInstallPending (cls, packageName, state):
		DbusIf.LOCK ()
		package = PackageClass.LocatePackage (packageName)
		if package != None:
				package.InstallPending = state
		DbusIf.UNLOCK ()

		

	# AddPackage adds one package to the package list
	# packageName must be specified
	# the package names must be unique
	#
	# this method is called from the GUI add package command

	@classmethod
	def AddPackage ( cls, packageName=None, gitHubUser=None, gitHubBranch=None, source=None ):
		if source == 'GUI':
			reportStatusTo = 'Editor'
		# AUTO or DEFAULT source
		else:
			reportStatusTo = None

		if packageName == None or packageName == "":
			DbusIf.UpdateStatus ( message="no package name for AddPackage - nothing done",
							where=reportStatusTo, logLevel=ERROR )
			if source == 'GUI':
				DbusIf.SetGuiEditAction ( 'ERROR' )
			return False

		# insure packageName is unique before adding this new package
		matchFound = False
		DbusIf.LOCK ()
		package = PackageClass.LocatePackage (packageName)

		# new packageName is unique, OK to add it
		if package == None:
			DbusIf.UpdateStatus ( message="adding " + packageName, where='Editor', logLevel=WARNING )

			section = len(cls.PackageList)
			cls.PackageList.append( PackageClass ( section, packageName = packageName ) )
			DbusIf.UpdatePackageCount ()
			DbusIf.RefreshDefaultPackages = True

			# add user/branch from caller
			package = PackageClass.LocatePackage (packageName)
			if package != None:
				if gitHubUser == None:
						gitHubUser = "?"
				if gitHubBranch == None:
						gitHubBranch = "?"
				package.SetGitHubUser (gitHubUser)
				package.SetGitHubBranch (gitHubBranch)

			if source == 'GUI':
				DbusIf.SetGuiEditAction ( '' )
				DbusIf.UpdateStatus ( message = "", where='Editor')
				# package added from the GUI (aka, manually)
				#	allow auto adds
				PackageClass.SetAutoAddOk (packageName, True)
		else:
			if source == 'GUI':
				DbusIf.UpdateStatus ( message=packageName + " already exists - choose another name", where=reportStatusTo, logLevel=WARNING )
				DbusIf.SetGuiEditAction ( 'ERROR' )
			else:
				DbusIf.UpdateStatus ( message=packageName + " already exists", where=reportStatusTo, logLevel=WARNING )
		
		DbusIf.UNLOCK ()
	# end AddPackage


	# packages are removed as a request from the GUI (packageName specified)
	# or during system initialization (packageIndex specified)
	# to remove a package:
	#	1) locate the entry matching package name  (if any)
	#	2) move all packages after that entry to the previous slot (if any)
	#	3) erase the last package slot to avoid confusion (by looking at dbus-spy)
	#	3) remove the entry in PackageList (pop)
	#	4) update the package count
	#	5) set DO_NOT_AUTO_ADD flag file to prevent
	#		package from being re-added to the package list
	#		flag file is deleted when package is manually installed again
	#
	#	Remove package must be passed either the package name or an index into PackageList
	#
	#	returns True if package was removed, False if not
	#
	#	this is all done while the package list is locked !!!!

	@classmethod
	def RemovePackage (cls, packageName=None, packageIndex=None ):
		# packageName specified so this is a call from the package editor
		if packageName != None:
			manualRemove = True
			if packageName == "SetupHelper":
				DbusIf.UpdateStatus ( message="REMOVING SetupHelper" + packageName, where='Editor', logLevel=CRITICAL )
			else:
				DbusIf.UpdateStatus ( message="removing " + packageName, where='Editor', logLevel=WARNING )
		# no package name specified, so this is a call from system initialization - messages to log only
		elif packageIndex != None:
			manualRemove = False
			name = PackageClass.PackageList [packageIndex].PackageName
			if name == None or name == "":
				logging.error ( "RemovePackage: removing package without a name" )
			else:
				logging.error ( "RemovePackage: removing " + name )
		# neither package name nor package instance passed - can't do anything
		else:
			logging.error ( "RemovePackage: no package info passed - nothing done" )
			return

		DbusIf.LOCK ()
		packages = PackageClass.PackageList
		listLength = len (packages)
		if len (packages) == 0:
			DbusIf.UNLOCK ()
			return

		# locate index of packageName
		if manualRemove:
			toIndex = 0
			matchFound = False
			while toIndex < listLength:
				if packageName == packages[toIndex].PackageName:
					matchFound = True
					break
				toIndex += 1
		# called from init - already have index
		else:
			toIndex = packageIndex
			matchFound = True

		if matchFound:
			# move packages after the one to be remove down one slot (copy info)
			# each copy overwrites the lower numbered package
			fromIndex = toIndex + 1
			while fromIndex < listLength:
				# dbus Settings
				toPackage = packages[toIndex]
				fromPackage = packages[fromIndex]
				toPackage.SetPackageName (fromPackage.PackageName )
				toPackage.SetGitHubUser (fromPackage.GitHubUser )
				toPackage.SetGitHubBranch (fromPackage.GitHubBranch )

				# dbus service params
				toPackage.SetGitHubVersion (fromPackage.GitHubVersion )
				toPackage.SetPackageVersion (fromPackage.PackageVersion )
				toPackage.SetInstalledVersion (fromPackage.InstalledVersion )
				toPackage.SetRebootNeeded (fromPackage.RebootNeeded )
				toPackage.SetGuiRestartNeeded (fromPackage.GuiRestartNeeded )
				toPackage.SetIncompatible (fromPackage.Incompatible )

				# package variables
				toPackage.DownloadPending = fromPackage.DownloadPending
				toPackage.InstallPending = fromPackage.InstallPending

				toIndex += 1
				fromIndex += 1

			# here, toIndex points to the last package in the old list
			toPackage = packages[toIndex]

			# can't actually remove service paths cleanly
			#	so just set contents to null/False
			# 	they will disappear after PackageManager is started the next time
			toPackage.SetGitHubVersion ("?")
			toPackage.SetInstalledVersion ("?")
			toPackage.SetPackageVersion ("?")
			toPackage.SetRebootNeeded (False)
			toPackage.SetGuiRestartNeeded (False)
			toPackage.SetIncompatible (False)

			# remove the Settings and service paths for the package being removed
			DbusIf.RemoveDbusSettings ( [toPackage.packageNamePath, toPackage.gitHubUserPath, toPackage.gitHubBranchPath] )

			# remove entry from package list
			packages.pop (toIndex)

			DbusIf.RefreshDefaultPackages = True

			# update package count
			DbusIf.UpdatePackageCount ()		

		DbusIf.UNLOCK ()
		# this package was manually removed block automatic adds
		#	in the package directory
		if manualRemove:
			if matchFound:
				# block automatic adds
				PackageClass.SetAutoAddOk (packageName, False)

				DbusIf.UpdateStatus ( message="", where='Editor' )
				DbusIf.SetGuiEditAction ( '' )
			else:
				DbusIf.UpdateStatus ( message=packageName + " not removed - name not found", where='Editor', logLevel=ERROR )
				DbusIf.SetGuiEditAction ( 'ERROR' )


	#	UpdateFileFlagsAndVersions
	#
	# retrieves packages versions from the file system
	#	each package contains a file named version in it's root directory
	#		that becomes packageVersion
	#	the installedVersion-... file is associated with installed packages
	#		abesense of the file indicates the package is not installed
	#		presense of the file indicates the package is installed
	#		the content of the file is the actual version installed
	#		in prevous versions of the setup scripts, this file could be empty, 
	#		so we show this as "unknown"
	#
	# also sets incompatible parameter and AutoInstallOk local variable to save time in other loops
	#
	# the single package variation is broken out so it can be called from other methods
	#	to insure version information is up to date before proceeding with an operaiton
	#
	# must be called while LOCKED !!

	def UpdateFileFlagsAndVersions (self):
		global VersionToNumber
		global VenusVersion
		global VenusVersionNumber

		packageName = self.PackageName

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
		self.SetInstalledVersion (installedVersion)

		packageDir = "/data/" + packageName

		# no package directory - null out all params
		if not os.path.isdir (packageDir):
			self.SetPackageVersion ("")
			self.AutoInstallOk = False
			self.FileSetOk = False
			self.SetIncompatible ('')
			return

		# fetch package version (the one in /data/packageName)
		try:
			versionFile = open (packageDir + "/version", 'r')
			packageVersion = versionFile.readline().strip()
			versionFile.close()
		except:
			packageVersion = ""
		self.SetPackageVersion (packageVersion)

		# set the incompatible parameter
		#	to 'PLATFORM' or 'VERSION'
		global Platform
		incompatible = False
		if os.path.exists (packageDir + "/raspberryPiOnly" ):
			if Platform[0:4] != 'Rasp':
				self.SetIncompatible ('PLATFORM')
				incompatible = True

		# update local auto install flag based on DO_NOT_AUTO_INSTALL
		flagFile = "/data/setupOptions/" + packageName + "/DO_NOT_AUTO_INSTALL"
		if os.path.exists (flagFile):
			self.AutoInstallOk = False
		else:
			self.AutoInstallOk = True

		# also check to see if file set has errors
		flagFile = packageDir + "/FileSets/" + VenusVersion + "/INCOMPLETE"
		if os.path.exists (flagFile):
			self.FileSetOk = False
		else:
			self.FileSetOk = True

		# platform is OK, now check versions
		if incompatible == False:
			try:
				fd = open (packageDir + "/firstCompatibleVersion", 'r')
			except:
				firstVersion = "v2.40" # TODO: change to v2.66 ??????????????????????????
			else:
				firstVersion = fd.readline().strip()
				fd.close ()
			try:
				fd = open (packageDir + "/obsoleteVersion", 'r')
			except:
				obsoleteVersion = None
			else:
				obsoleteVersion = fd.readline().strip()
			
			firstVersionNumber = VersionToNumber (firstVersion)
			obsoleteVersionNumber = VersionToNumber (obsoleteVersion)
			if VenusVersionNumber < firstVersionNumber:
				self.SetIncompatible ('VERSION')
				incompatible = True
			elif obsoleteVersionNumber != 0 and VenusVersionNumber >= obsoleteVersionNumber:
				self.SetIncompatible ('VERSION')
				incompatible = True

		# platform and versions OK, check to see if command line is needed for install
		# the optionsRequired flag in the package directory indicates options must be set before a blind install
		# the optionsSet flag indicates the options HAVE been set already
		# so if optionsRequired == True and optionsSet == False, can't install from GUI
		if incompatible == False:
			if os.path.exists ("/data/" + packageName + "/optionsRequired" ):
				if not os.path.exists ( "/data/setupOptions/" + packageName + "/optionsSet"):
					self.SetIncompatible ('CMDLINE')
					incompatible = True
	# end UpdateFileFlagsAndVersions
# end Package


#	UpdateGitHubVersionClass
#
# downloads the GitHub version of all packages
# this work is done in a separate thread so network activity can be spaced out
# 
# a queue is used to trigger a priority update for a specific package
#	this is used when the operator changes GitHub user/branch so the version
#	updates rapidly
# the queue is also used to wake the thread from a potentially long sleep period
# to exit or speed up the refresh rate
#
#	Instances:
#		UpdateGitHubVersion (a separate thread)
#
#	Methods:
#		updateGitHubVersion 
#		run ()
#		StopThread ()
#

class UpdateGitHubVersionClass (threading.Thread):

	#	updateGitHubVersion
	#
	# fetches the GitHub version from the internet and stores it in the package
	#
	# this is called from the background thread run () below
	#
	# if the wget fails, the GitHub version is set to ""
	# this will happen if the name, user or branch are not correct
	# or if there is no internet connection
	#
	# the package GitHub version is upated
	# but the version is also returned to the caller
	#
	#	Instances:
	#		UpdateGitHubVersion (thread)
	#
	#	Methods:
	#		updateGitHubVersion
	#		SetPriorityGitHubVersion
	#		run (the thread)

	def updateGitHubVersion (self, packageName, gitHubUser, gitHubBranch):

		url = "https://raw.githubusercontent.com/" + gitHubUser + "/" + packageName + "/" + gitHubBranch + "/version"
		try:
			proc = subprocess.Popen (["wget", "--timeout=10", "-qO", "-", url],
							stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		except:
			logging.error ("wget for version failed " + packageName)
			gitHubVersion = ""
		else:
			proc.wait()
			# convert from binary to string
			stdout, stderr = proc.communicate ()
			stdout = stdout.decode ().strip ()
			stderr = stderr.decode ().strip ()
			returnCode = proc.returncode
			if proc.returncode == 0:
				gitHubVersion = stdout
			else:
				gitHubVersion = ""

		# locate the package with this name and update it's GitHubVersion
		# if not in the list discard the information
		DbusIf.LOCK ()
		package = PackageClass.LocatePackage (packageName)
		if package != None:
			package.SetGitHubVersion (gitHubVersion)
			package.lastGitHubVersionUpdate = time.time ()
		DbusIf.UNLOCK ()
		return gitHubVersion


	def __init__(self):
		threading.Thread.__init__(self)
		self.GitHubVersionQueue = queue.Queue (maxsize = 50)
		self.threadRunning = True
		# package needing immediate update
		self.priorityPackageName = None


	#	SetPriorityGitHubVersion
	# pushes a priority package version update onto our queue
	
	def SetPriorityGitHubVersion (self, packageName):
		self.GitHubVersionQueue.put (packageName)


	#	UpdateGitHubVersion run ()
	#
	# updates GitHub versions
	# GitHub access is spaced out to minimize network traffic
	# a priority update is pushed onto our que when GitHub info changes
	#
	# StopThread () is called to shut down the thread when PackageManager is quitting
	# "STOP" is pushed on to the queue by StopThread to cause the run thread to detect
	#	detect the stop request immediately
	#
	# run () blocks on reading from our queue
	#	the timeout for the queue pull paces the version fetches
	#	normally, the timeout will occur with the queue empty
	#		in which case we update the next GitHub version for the next package
	#	the time between version fetches changes
	#		for the first pass, a shorter delay is used
	#		after all packages have been updated, the delay is increased
	#		the shorter delay is used again when we pull "FAST" off the queue
	#
	#	when the que returns an item, it is checked to see if it is either a
	#		prioirty package to update it's GitHub version 
	#		"STOP" - indicating run should return
	#		"FAST" - indicating the loop should speed up
	#			this is used when download refresh mode/rates change
	#		checks the threadRunning flag and returns if it is False,
	#	when run returns, the main method should catch the tread with join ()

	def StopThread (self):
		logging.info ("attempting to stop UpdateGitHubVersion thread")
		self.threadRunning = False
		self.GitHubVersionQueue.put ( 'STOP', block=False )


	def run (self):
		global AllVersionsRefreshed

		delay = 2.0
		gitHubVersionPackageIndex = 0
		AllVersionsRefreshed = False
		
		while self.threadRunning:
			command = ""
			# queue gets STOP and FAST commands or priority package name
			# empty queue signals it's time for a background update
			# queue timeout is used to pace background updates
			try:
				command = self.GitHubVersionQueue.get (timeout = delay)
			except queue.Empty:	# means get() timed out as expected - not an error
				# timeout indicates it's time to do a background update
				pass
			except:
				logging.error ("pull from GitHubVersionQueue failed")

			if command == 'STOP' or self.threadRunning == False:
				return

			refreshGitHubVersion = DbusIf.GetAutoDownloadMode () != AUTO_DOWNLOADS_OFF

			# the FAST command speeds up the loop and starts with the first package
			if (command == 'FAST'):
				delay = 2.0
				gitHubVersionPackageIndex = 0
				AllVersionsRefreshed = False
			# command contains a package name for priority update
			elif command != "":
				DbusIf.SetGuiEditAction ('')
				priorityPackageName = command
				DbusIf.LOCK ()
				package = PackageClass.LocatePackage (priorityPackageName)
				if package != None:
					user = package.GitHubUser
					branch = package.GitHubBranch
				DbusIf.UNLOCK ()
				if package != None:
					# update the GigHub version here
					self.updateGitHubVersion (priorityPackageName, user, branch)
				else:
					logging.error ("can't fetch GitHub version - " + priorityPackageName + " not in package list")

			# do one background update
			DbusIf.LOCK ()
			length = len (PackageClass.PackageList)
			if length > 0:
				# reached end of list - switch to slow scan 
				if gitHubVersionPackageIndex >= length:
					gitHubVersionPackageIndex = 0
					# notify the main loop that all versions have been refreshed and
					# download modes can now be changed if appropriate
					AllVersionsRefreshed = True
					delay = 60.0
				package = PackageClass.PackageList[gitHubVersionPackageIndex]
				gitHubVersionPackageIndex += 1

				packageName = package.PackageName
				user = package.GitHubUser
				branch = package.GitHubBranch
				
				# expire version if check has not been done in 20 minutes
				if not refreshGitHubVersion and package.GitHubVersion != ""\
							and time.time () > package.lastGitHubVersionUpdate + (1200):
					package.SetGitHubVersion ("")

				DbusIf.UNLOCK () # unlock now because updateGitHubVersion makes internet call

				# get GitHub version only if downloads are turned on
				if refreshGitHubVersion:
					self.updateGitHubVersion (packageName, user, branch)
			else:
				DbusIf.UNLOCK ()


#	DownloadGitHubPackagesClass
#
# downloads packages from GitHub, replacing the existing package
# 	if versions indicate a newer version
#
# the GUI and auto download code (in main loop) push download
#	actions onto our queue
#	the thread blocks when the queue is empty
#
# a STOP command is also pushed onto the queue when PackageManager
#	is shutting down. This unblocks this thread which immediately
#	reads threadRunning. If false, run () returns
#
#	Instances:
#		DownloadGitHub (a separate thread)
#
#	Methods:
#		GitHubDownload
#		DownloadVersionCheck
#		processDownloadQueue
#		run
#		StopThread
#
# the run () thread is only responsible for pacing automatic downloads from the internet
#	commands are pushed onto the processing queue (PushAction)
#

class DownloadGitHubPackagesClass (threading.Thread):

	def __init__(self):
		threading.Thread.__init__(self)
		self.DownloadQueue = queue.Queue (maxsize = 50)
		self.threadRunning = True


	# this method downloads a package from GitHub
	# it is called from run() below
	# also, download requests are pushed for automatic downloads from mainloop
	# and also for a manual download triggered from the GUI
	# statusMethod provides text status to the caller
	# callBack provides notificaiton of completion (or error)
	# automatic downloads that fail are logged but otherwise not reported

	def GitHubDownload (self, packageName= None, source=None):
		if source == 'GUI':
			where = 'Editor'
		elif source == 'AUTO':
			where = 'Download'
		else:
			where = None

		# to avoid confilcts, create a temp directory that
		# is unque to this program and this method
		# and make sure it is empty
		tempDirectory = "/var/run/packageManager" + str(os.getpid ()) + "GitHubDownload"
		if os.path.exists (tempDirectory):
			shutil.rmtree (tempDirectory)
		os.mkdir (tempDirectory)

		DbusIf.LOCK ()
		package = PackageClass.LocatePackage (packageName)
		gitHubUser = package.GitHubUser
		gitHubBranch = package.GitHubBranch
		DbusIf.UNLOCK ()

		DbusIf.UpdateStatus ( message="downloading " + packageName, where=where, logLevel=WARNING )

		# create temp directory specific to this thread
		tempArchiveFile = tempDirectory + "/temp.tar.gz"
		# download archive
		if os.path.exists (tempArchiveFile):
			os.remove ( tempArchiveFile )

		url = "https://github.com/" + gitHubUser + "/" + packageName  + "/archive/" + gitHubBranch  + ".tar.gz"
		try:
			proc = subprocess.Popen ( ['wget', '--timeout=120', '-qO', tempArchiveFile, url ],\
										stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		except:
			DbusIf.UpdateStatus ( message="could not access archive on GitHub " + packageName,
										where=where, logLevel=ERROR )
			if source == 'GUI':
				DbusIf.SetGuiEditAction ( 'ERROR' )
			return False
		else:
			proc.wait()
			stdout, stderr = proc.communicate ()
			# convert from binary to string
			stdout = stdout.decode ().strip ()
			stderr = stderr.decode ().strip ()
			returnCode = proc.returncode
			
		if returnCode != 0:
			DbusIf.UpdateStatus ( message="could not access " + packageName + ' ' + gitHubUser + ' '\
										+ gitHubBranch + " on GitHub", where=where, logLevel=WARNING )
			logging.error ("returnCode" + str (returnCode) +  "stderr" + stderr)
			if source == 'GUI':
				DbusIf.SetGuiEditAction ( 'ERROR' )
			PackageClass.UpdateDownloadPending (packageName, False)
			shutil.rmtree (tempDirectory)
			return False
		try:
			proc = subprocess.Popen ( ['tar', '-xzf', tempArchiveFile, '-C', tempDirectory ],
										stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		except:
			DbusIf.UpdateStatus ( message="could not unpack " + packageName + ' ' + gitHubUser + ' ' + gitHubBranch,
										where=where, logLevel=ERROR )
			if source == 'GUI':
				DbusIf.SetGuiEditAction ( 'ERROR' )
			PackageClass.UpdateDownloadPending (packageName, False)
			shutil.rmtree (tempDirectory)
			return False

		proc.wait()
		stdout, stderr = proc.communicate ()
		# convert from binary to string
		stdout = stdout.decode ().strip ()
		stderr = stderr.decode ().strip ()
		returnCode = proc.returncode

		if returnCode != 0:
			DbusIf.UpdateStatus ( message="could not unpack " + packageName + ' ' + gitHubUser + ' ' + gitHubBranch,
										where=where, logLevel=ERROR )
			logging.error ("stderr: " + stderr)
			if source == 'GUI':
				DbusIf.SetGuiEditAction ( 'ERROR' )
			PackageClass.UpdateDownloadPending (packageName, False)
			shutil.rmtree (tempDirectory)
			return False

		# attempt to locate a directory that contains a version file
		# the first directory in the tree starting with tempDicrectory
		# is returnd
		unpackedPath = LocatePackagePath (tempDirectory)
		if unpackedPath == None:
			PackageClass.UpdateDownloadPending (packageName, False)
			shutil.rmtree (tempDirectory)
			logging.error ( "GitHubDownload: no archive path for " + packageName)
			return False

		# move unpacked archive to package location
		# LOCK this critical section of code to prevent others
		#	from accessing the directory while it's being updated
		packagePath = "/data/" + packageName
		tempPackagePath = packagePath + "-temp"
		DbusIf.LOCK ()
		if os.path.exists (packagePath):
			os.rename (packagePath, tempPackagePath)
		shutil.move (unpackedPath, packagePath)
		if os.path.exists (tempPackagePath):
			shutil.rmtree (tempPackagePath, ignore_errors=True)	# like rm -rf
		DbusIf.UNLOCK ()
		PackageClass.UpdateDownloadPending (packageName, False)
		DbusIf.UpdateStatus ( message="", where=where )
		if source == 'GUI':
			DbusIf.SetGuiEditAction ( '' )
		shutil.rmtree (tempDirectory)
		return True
	# end GitHubDownload


	#	DownloadVersionCheck
	#
	# compares versions to determine if a download is needed
	# returns: True if a download is needed, False otherwise
	# must be called with package list LOCKED !!

	
	def DownloadVersionCheck (self, package):
		gitHubUser = package.GitHubUser
		gitHubBranch = package.GitHubBranch
		gitHubVersion = package.GitHubVersion
		packageVersion = package.PackageVersion

		# versions not initialized yet - don't allow the download
		if gitHubVersion == None or gitHubVersion == "" or gitHubVersion[0] != 'v' or packageVersion == '?':
			return False

		packageVersionNumber = package.PackageVersionNumber
		gitHubVersionNumber = package.GitHubVersionNumber

		# if GitHubBranch is a version number, a download is needed if the versions differ
		if gitHubBranch[0] == 'v':
			if gitHubVersionNumber != packageVersionNumber:
				return True
			else:
				return False
		# otherwise the download is needed if the gitHubVersion is newer
		else:
			if gitHubVersionNumber > packageVersionNumber:
				return True
			else:
				return False


	#	DownloadGitHub run (the thread)
	#
	# StopThread () is called to shut down the thread

	def StopThread (self):
		logging.info ("attempting to stop DownloadGitHub thread")
		self.threadRunning = False
		self.DownloadQueue.put ( ('STOP', ''), block=False )

	#	DownloadGitHub run (the thread)
	#
	# downloads packages placed on its queue from
	#	GUI requests
	#	a background loop in mainLoop
	#
	# run () checks the threadRunning flag and returns if it is False,
	#	essentially taking the thread off-line
	#	the main method should catch the tread with join ()

	def run (self):
		while self.threadRunning:	# loop forever
			# process one GUI download request
			# if there was one, skip auto downloads until next pass
			try:
				command = self.DownloadQueue.get () # block forever
			except:
				logging.error ("pull from DownloadQueue queue failed")
				time.sleep (5.0)
				continue
			if command[0] == 'STOP' or self.threadRunning == False:
				return

			# separate command, source tuple
			# and separate action and packageName
			if len (command) >= 2:
				parts = command[0].split (":")
				if len (parts) >= 2:
					action = parts[0].strip ()
					packageName = parts[1].strip ()
				else:
					logging.error ("DownloadQueue - no action and/or package name - discarding", command)
					time.sleep (5.0)
					continue
				source = command[1]
			else:
				logging.error ("DownloadQueue - no command and/or source - discarding", command)
				time.sleep (5.0)
				continue

			# invalid action for this queue
			if action != 'download':
				logging.error ("received invalid command from Install queue: ", command )
				time.sleep (5.0)
				continue

			# do the download here
			downloadStartTime = time.time()
			self.GitHubDownload (packageName=packageName, source=source )

			# sleep twice the time it took to download the archive to avoid flooding internet connection
			downloadTime = (time.time() - downloadStartTime) * 2
			time.sleep (downloadTime)
		# end while True
	# end run
# end DownloadGitHubPackagesClass
					

#	InstallPackagesClass
#	Instances:
#		InstallPackages (a separate thread)
#
#	Methods:
#		InstallPackage
#		run (the thread)
#		StopThread
#		run
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
		threading.Thread.__init__(self)
		DbusIf.SetInstallStatus ("")
		self.threadRunning = True
		self.InstallQueue = queue.Queue (maxsize = 10)

	
	#	InstallPackage
	#
	# this method either installs or uninstalls a package
	# the choice is the direction value:
	# 		'install' or 'uninstall'
	# the operation can take many seconds
	# 	i.e., the time it takes to run the package's setup script
	#	do not call from a thread that should not block

	def InstallPackage ( self, packageName=None, source=None , direction='install' ):

		# refresh versions, then check to see if an install is possible
		DbusIf.LOCK ()
		package = PackageClass.LocatePackage (packageName)

		if source == 'GUI':
			sendStatusTo = 'Editor'
			# uninstall sets the uninstall flag file to prevent auto install
			if direction == 'uninstall':
				package.UpdateDoNotInstall (False)
				logging.warning (packageName + " was manually uninstalled - auto install for that package will be skipped")
			# manual install removes the flag file
			else:
				package.UpdateDoNotInstall (True)
				logging.warning (packageName + " was manually installed - allowing auto install for that package")
		elif source == 'AUTO':
			sendStatusTo = 'Install'

		packageDir = "/data/" + packageName
		if not os.path.isdir (packageDir):
			logging.error ("InstallPackage - no package directory " + packageName)
			package.InstallPending = False
			DbusIf.UNLOCK ()
			if source == 'GUI':
				DbusIf.SetGuiEditAction ( 'ERROR' )
			return
			
		setupFile = packageDir + "/setup"
		if os.path.isfile(setupFile):
			if os.access(setupFile, os.X_OK) == False:
				DbusIf.UpdateStatus ( message="setup file for " + packageName + " not executable",
												where=sendStatusTo, logLevel=ERROR )
				if source == 'GUI':
					DbusIf.SetGuiEditAction ( 'ERROR' )
				package.InstallPending = False
				DbusIf.UNLOCK ()
				return
		else:
			DbusIf.UpdateStatus ( message="setup file for " + packageName + " doesn't exist",
											where=sendStatusTo, logLevel=ERROR )
			if source == 'GUI':
				DbusIf.SetGuiEditAction ( 'ERROR' )
			package.InstallPending = False
			DbusIf.UNLOCK ()
			return

		DbusIf.UNLOCK ()

		# provide an innitial status message for the action since it takes a while for PackageManager
		#	to fill in EditStatus
		# this provides immediate user feedback that the button press was detected
		DbusIf.UpdateStatus ( message=direction + "ing " + packageName,
								where=sendStatusTo, logLevel=WARNING )
		try:
			proc = subprocess.Popen ( [ setupFile, direction, 'deferReboot', 'deferGuiRestart', 'auto' ],
										stdout=subprocess.PIPE, stderr=subprocess.PIPE )
			proc.wait()
			stdout, stderr = proc.communicate ()
			# convert from binary to string
			stdout = stdout.decode ().strip ()
			stderr = stderr.decode ().strip ()
			returnCode = proc.returncode
			setupRunFail = False
		except:
			setupRunFail = True

		# manage the result of the setup run while locked just in case
		DbusIf.LOCK ()

		package = PackageClass.LocatePackage (packageName)
		package.InstallPending = False

		if setupRunFail:
			DbusIf.UpdateStatus ( message="could not run setup file for " + packageName,
										where=sendStatusTo, logLevel=ERROR )
			if source == 'GUI':
				DbusIf.SetGuiEditAction ( 'ERROR' )
		elif returnCode == EXIT_SUCCESS:
			package.SetIncompatible ('')	# this marks the package as compatible
			DbusIf.UpdateStatus ( message="", where=sendStatusTo )
			if source == 'GUI':
				DbusIf.SetGuiEditAction ( '' )
		elif returnCode == EXIT_REBOOT:
			# set package RebootNeeded so GUI can show the need - does NOT trigger a reboot
			package.SetRebootNeeded (True)

			DbusIf.UpdateStatus ( message=packageName + " " + direction + " requires REBOOT",
											where=sendStatusTo, logLevel=WARNING )
			if source == 'GUI':
				DbusIf.SetGuiEditAction ( 'RebootNeeded' )
			# auto install triggers a reboot by setting the global flag - reboot handled in main_loop
			else:
				global SystemReboot
				SystemReboot = True
		elif returnCode == EXIT_RESTART_GUI:
			# set package GuiRestartNeeded so GUI can show the need - does NOT trigger a restart
			package.SetGuiRestartNeeded (True)

			if source == 'GUI':
				DbusIf.UpdateStatus ( message=packageName + " " + direction + " requires GUI restart",
											where=sendStatusTo, logLevel=WARNING )
				DbusIf.SetGuiEditAction ( 'GuiRestartNeeded' )
			# auto install triggers a GUI restart by setting the global flag - restart handled in main_loop
			else:
				logging.warning ( packageName + " " + direction + " requires GUI restart" )
				global GuiRestart
				GuiRestart = True
		elif returnCode == EXIT_RUN_AGAIN:
			if source == 'GUI':
				DbusIf.UpdateStatus ( message=packageName + " run install again to complete install",
											where=sendStatusTo, logLevel=WARNING )
				DbusIf.SetGuiEditAction ( 'ERROR' )
			else:
				DbusIf.UpdateStatus ( message=packageName + " setup must be run again",
											where=sendStatusTo, logLevel=WARNING )
		elif returnCode == EXIT_INCOMPATIBLE_VERSION:
			global VenusVersion
			package.SetIncompatible ('VERSION')
			DbusIf.UpdateStatus ( message=packageName + " not compatible with Venus " + VenusVersion,
											where=sendStatusTo, logLevel=WARNING )
			if source == 'GUI':
				DbusIf.SetGuiEditAction ( 'ERROR' )
		elif returnCode == EXIT_INCOMPATIBLE_PLATFOM:
			global Platform
			package.SetIncompatible ('PLATFORM')
			DbusIf.UpdateStatus ( message=packageName + " " + direction + " not compatible with " + Platform,
											where=sendStatusTo, logLevel=WARNING )
			if source == 'GUI':
				DbusIf.SetGuiEditAction ( 'ERROR' )
		elif returnCode == EXIT_OPTIONS_NOT_SET:
			DbusIf.UpdateStatus ( message=packageName + " " + direction + " setup must be run from the command line",
											where=sendStatusTo, logLevel=WARNING )
			if source == 'GUI':
				DbusIf.SetGuiEditAction ( 'ERROR' )
		elif returnCode == EXIT_FILE_SET_ERROR:
			DbusIf.UpdateStatus ( message=packageName + " file set incomplete",
											where=sendStatusTo, logLevel=ERROR )
			if source == 'GUI':
				DbusIf.SetGuiEditAction ( 'ERROR' )
		# unknown error
		elif returnCode != 0:
			DbusIf.UpdateStatus ( message=packageName + " " + direction + " unknown error " + str (returnCode),
											where=sendStatusTo, logLevel=ERROR )
			logging.error ("stderr: " + stderr)
			if source == 'GUI':
				DbusIf.SetGuiEditAction ( 'ERROR' )

		DbusIf.UNLOCK ()
	# end InstallPackage ()


	#	InstallPackage run (the thread)
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
		self.InstallQueue.put ( ('STOP', ''), block=False )

	def run (self):
		while self.threadRunning:
			try:
				command = self.InstallQueue.get ()
			except:
				logging.error ("pull from Install queue failed")
				continue
			if len (command) == 0:
				logging.error ("pull from Install queue failed - empty comand")
				time.sleep (5.0)
				continue
			# thread shutting down
			if command[0] == 'STOP' or self.threadRunning == False:
				return

			# separate command, source tuple
			# and separate action and packageName
			if len (command) >= 2:
				parts = command[0].split (":")
				if len (parts) >= 2:
					action = parts[0].strip ()
					packageName = parts[1].strip ()
				else:
					logging.error ("InstallQueue - no action and/or package name - discarding", command)
					time.sleep (5.0)
					continue
				source = command[1]
			else:
				logging.error ("InstallQueue - no command and/or source - discarding", command)
				time.sleep (5.0)
				continue

			if action == 'install':
				self.InstallPackage (packageName=packageName, source=source , direction='install' )
				time.sleep (5.0)
			elif action == 'uninstall':
				self.InstallPackage (packageName=packageName, source=source , direction='uninstall' )
				time.sleep (5.0)
			# invalid action for this queue
			else:
				logging.error ("received invalid command from Install queue: ", command )
				time.sleep (5.0)
				continue
	# end run
# end InstallPackagesClass



#	MediaScanClass
#	Instances:
#		MediaScan (a separate thread)
#	Methods:
#		transferPackage
#		StopThread
#		settingsBackup
#		settingsRestore
#		run
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
	#
	#	if true, autoInstallOverride causes the ONE_TIME_INSTALL flag to be set
	#		this happens if the caller detects the AUTO_INSTALL_PACKAGES flag on removable media

	def transferPackage (self, path, autoInstallOverride=False):
		packageName = os.path.basename (path).split ('-', 1)[0]

		# create an empty temp directory in ram disk
		#	for the following operations
		# directory is unique to this process and thread
		tempDirectory = "/var/run/packageManager" + str(os.getpid ()) + "Media"
		if os.path.exists (tempDirectory):
			shutil.rmtree (tempDirectory)
		os.mkdir (tempDirectory)

		# unpack the archive - result is placed in tempDirectory
		try:
			proc = subprocess.Popen ( ['tar', '-xzf', path, '-C', tempDirectory ],
										stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		except:
			DbusIf.UpdateStatus ( message="tar failed for " + packageName,
									where='Media', logLevel=ERROR)
			time.sleep (5.0)
			DbusIf.UpdateStatus ( message="", where='Media')
			return False
		proc.wait()
		stdout, stderr = proc.communicate ()
		# convert from binary to string
		stdout = stdout.decode ().strip ()
		stderr = stderr.decode ().strip ()
		returnCode = proc.returncode
		if returnCode != 0:
			DbusIf.UpdateStatus ( message="could not unpack " + packageName + " from SD/USB media",
									where='Media', logLevel=ERROR)
			logging.error ("stderr: " + stderr)
			shutil.rmtree (tempDirectory)
			time.sleep (5.0)
			DbusIf.UpdateStatus ( message="", where='Media')
			return False

		# attempt to locate a package directory in the tree below tempDirectory
		unpackedPath = LocatePackagePath (tempDirectory)

		if unpackedPath == None:
			logging.warning (packageName + " archive doesn't contain a package directory - rejected" )
			shutil.rmtree (tempDirectory)
			time.sleep (5.0)
			DbusIf.UpdateStatus ( message="", where='Media')
			return False

		# compare versions and proceed only if they are different
		packagePath = "/data/" + packageName
		try:
			fd = open (packagePath + "/version", 'r')
		except:
			packageVersion = 0
		else:
			packageVersion = VersionToNumber (fd.readline().strip())
			fd.close ()
		try:
			fd = open (unpackedPath + "/version", 'r')
		except:
			unpackedVersion = 0
		else:
			unpackedVersion = VersionToNumber (fd.readline().strip())
			fd.close ()
		if packageVersion == unpackedVersion:
			logging.warning ("transferPackages: " + packageName + " versions are the same - skipping transfer")
			shutil.rmtree (tempDirectory)
			DbusIf.UpdateStatus ( message="", where='Media')
			return False

		# move unpacked archive to package location
		# LOCK this critical section of code to prevent others
		#	from accessing the directory while it's being updated
		DbusIf.UpdateStatus ( message="transfering " + packageName + " from SD/USB", where='Media', logLevel=WARNING )
		tempPackagePath = packagePath + "-temp"
		DbusIf.LOCK () 
		if os.path.exists (tempPackagePath):
			shutil.rmtree (tempPackagePath, ignore_errors=True)	# like rm -rf
		if os.path.exists (packagePath):
			os.rename (packagePath, tempPackagePath)
		shutil.move (unpackedPath, packagePath)
		if os.path.exists (tempPackagePath):
			shutil.rmtree (tempPackagePath, ignore_errors=True)	# like rm -rf
		# set package one-time install flag so this package is installed regardless of other flags
		#	this flag is removed when the install is preformed
		if autoInstallOverride:
			logging.warning ("Auto Install - setting ONE_TIME_INSTALL for " + packageName )
			open ( packagePath + "/ONE_TIME_INSTALL", 'a').close()

		DbusIf.UNLOCK ()
		shutil.rmtree (tempDirectory, ignore_errors=True)
		time.sleep (5.0)
		DbusIf.UpdateStatus ( message="", where='Media')
		return True
	# end transferPackage


	def __init__(self):
		threading.Thread.__init__(self)
		self.MediaQueue = queue.Queue (maxsize = 10) # used only for STOP
		self.threadRunning = True
		self.AutoUninstall = False

	#
	#	settingsBackup
	#	settingsRestore
	#
	# extracts / restores dbus settings and custom icons
	# copies log files to the removable media
	#	/data/log/SetupHelper
	#	/data/log/PackageManager
	#	/data/log/gui
	#
	# settingsList contains the list of dbus /Settings parameters to save and restore
	#

	def settingsBackup (self, backupPath):
		settingsCount = 0
		settingsListFile = "/data/SetupHelper/settingsList"
		backupFile = backupPath + "/settingsBackup"
		try:
			if not os.path.exists (settingsListFile):
				logging.error (settingsListFile + " does not exist - can't backup settings")
				return

			# backup settings
			backupSettings = open (backupFile, 'w')
			bus = dbus.SystemBus()
			with open (settingsListFile, 'r') as listFile:
				for line in listFile:
					setting = line.strip()
					try:
						value =  bus.get_object("com.victronenergy.settings", setting).GetValue()
						attributes = bus.get_object("com.victronenergy.settings", setting).GetAttributes()
					except:
						continue
					dataType = type (value)
					if dataType is dbus.Double:
						typeId = 'f'
					elif dataType is dbus.Int32 or dataType is dbus.Int64:
						typeId = 'i'
					elif dataType is dbus.String:
						typeId = 's'
					else:
						typeId = ''
						logging.error ("settingsBackup - invalid data type " + typeId + " - can't include parameter attributes " + setting)

					value = str ( value )
					default = str (attributes[0])
					min = str (attributes[1])
					max = str (attributes[2])
					silent = str (attributes[3])
					
					# create entry with just settng path and value without a valid data type
					if typeId == '':
						line = ','.join ( [ setting, value ]) + '\n'
					else:
						line = ','.join ( [ setting, value, typeId, default, min, max, silent ]) + '\n'

					backupSettings.write (line)
					settingsCount += 1

			backupSettings.close ()
			listFile.close ()
		except:
			logging.error ("settings backup - settings write failure")
		
		# backup logo overlays
		overlaySourceDir = "/data/themes/overlay"
		overlayDestDir = backupPath + "/logoBackup"

		
		# remove any previous logo backups
		if os.path.isdir (overlayDestDir):
			shutil.rmtree (overlayDestDir)

		overlayCount = 0
		try:
			if os.path.isdir (overlaySourceDir):
				overlayFiles = os.listdir (overlaySourceDir)
				if len (overlayFiles) > 0:
					# create overlay direcory on backkup device, then copy files
					if not os.path.isdir (overlayDestDir):
						os.mkdir (overlayDestDir)
					for overlay in overlayFiles:
						if overlay[0] == ".":
							continue
						shutil.copy ( overlaySourceDir + "/" + overlay, overlayDestDir )
						overlayCount += 1
		except:
			logging.error ("settings backup - logo write failure")

		# copy log files
		logsWritten = "no logs"
		try:
			# remove any previous log backups
			logDestDir = backupPath + "/logs"
			if os.path.isdir (logDestDir):
				shutil.rmtree (logDestDir)

			proc = subprocess.Popen ( [ 'zip', '-rq', backupPath + "/logs.zip", "/data/log" ],
										stdout=subprocess.PIPE, stderr=subprocess.PIPE )
			proc.wait()
			stdout, stderr = proc.communicate ()
			# convert from binary to string
			stdout = stdout.decode ().strip ()
			stderr = stderr.decode ().strip ()
			returnCode = proc.returncode
			logsWritten = "logs"
		except:
			logging.error ("settings backup - log write failure")
			logsWritten = "no logs"



		# backup setup script options
		optionsSourceDir = "/data/setupOptions"
		optionsDestDir = backupPath + "/setupOptions"

		try:
			# remove any previous options backups
			if os.path.isdir (optionsDestDir):
				shutil.rmtree (optionsDestDir)

			if os.path.isdir (optionsSourceDir):
				shutil.copytree ( optionsSourceDir, optionsDestDir )
		except:
			logging.error ("settings backup - overlays write failure")
		
		logging.warning ("settings backup completed - " + str(settingsCount) + " settings, " + str (overlayCount) + " logos, "
							+ logsWritten )


	def settingsRestore (self, backupPath):
		backupFile = backupPath + "/settingsBackup"
		if not os.path.exists (backupFile):
			logging.error (backupFile + " does not exist - can't restore settings")
		bus = dbus.SystemBus()
		settingsCount = 0
		with open (backupFile, 'r') as fd:
			for line in fd:
				parameterExists = False
				# ( setting path, value, attributes)
				parts = line.strip().split (',')
				numberOfParts = len (parts)
				# full entry with attributes
				if numberOfParts == 7:
					typeId = parts[2]
					default = parts[3]
					min = parts[4]
					max = parts[5]
					silent = parts[6]
				# only path and name - old settings file format
				elif numberOfParts == 2:
					typeId = ''
					default = ''
					min = ''
					max = ''
					silent = ''
				else:
					logging.error ("settingsRestore: invalid line in file " + line)
					continue
				
				path = parts[0]
				value = parts[1]
				try:
					bus.get_object("com.victronenergy.settings", path).GetValue()
					parameterExists = True
				except:
					pass

				if not parameterExists:
					if typeId == '':
						logging.error ("settingsRestore: no attributes in settingsBackup file - can't create " + path)
					# parameter does not yet exist, create it
					else:
						# silent uses a different method
						if silent == 1:
							method = 'AddSettingSilent'
						else:
							method = 'AddSetting'

						try:
							proc = subprocess.Popen ( [ 'dbus', '-y', 'com.victronenergy.settings', '/', method, '',
											path, default, typeId, min, max ], 
											stdout=subprocess.PIPE, stderr=subprocess.PIPE)
							proc.wait()
							parameterExists = True
							logging.warning ("settingsRestore: creating " + path)
						except:
							logging.error ("settingsRestore: settings create failed for " + path)

				# update parameter's value if it exists (or was just created)
				if parameterExists:
					bus.get_object("com.victronenergy.settings", path).SetValue (value)
					settingsCount += 1

		# restore logo overlays
		overlaySourceDir = backupPath + "/logoBackup"
		overlayDestDir = "/data/themes/overlay"
		overlayCount = 0
		if os.path.isdir (overlaySourceDir):
			overlayFiles = os.listdir (overlaySourceDir)
			if len (overlayFiles) > 0:
				# create overlay direcory in /data, then copy files
				if not os.path.isdir (overlayDestDir):
					os.mkdir (overlayDestDir)
				for overlay in overlayFiles:
					if overlay[0] == ".":
						continue
					shutil.copy ( overlaySourceDir + "/" + overlay, overlayDestDir )
					overlayCount += 1

		# restore setup script options
		optionsSourceDir = backupPath + "/setupOptions"
		optionsDestDir = "/data/setupOptions"

		# remove any previous options backups
		if os.path.isdir (optionsDestDir):
			shutil.rmtree (optionsDestDir)

		if os.path.isdir (optionsSourceDir):
			shutil.copytree ( optionsSourceDir, optionsDestDir )
		
		logging.warning ("settings restore completed - " + str(settingsCount) + " settings and " + str (overlayCount) + " overlays")


	#	Media Scan run (the thread)
	#
	# run () checks the threadRunning flag and returns if it is False,
	#	essentially taking the thread off-line
	#	the main method should catch the tread with join ()
	# StopThread () is called to shut down the thread

	def StopThread (self):
		logging.info ("attempting to stop MediaScan thread")
		self.threadRunning = False
		self.MediaQueue.put  ( "STOP", block=False )

	def run (self):
		separator = '/'
		root = "/media"
		archiveSuffix = ".tar.gz"
		autoRestore = False
		autoRestoreComplete = False
		autoEject = False
		bus = dbus.SystemBus()

		# list of accepted branch/version substrings
		acceptList = [ "-current", "-latest", "-main", "-test", "-debug", "-beta", "-install", 
							"-0", "-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9" ]

		# keep track of all media that's been scanned so it isn't scanned again
		# media removal removes it from this list
		alreadyScanned = []
		while self.threadRunning:
			# use queue to receive stop command and also to space operations
			command = ""
			try:
				command = self.MediaQueue.get (timeout = 5.0)
			except queue.Empty:	# queue empty is OK
				# timeout indicates it's time to make one pass through the code below
				pass
			except:
				logging.error ("pull from MediaQueue failed")
				time.sleep (5.0)
			if command == 'STOP' or self.threadRunning == False:
				return

			# automaticTransfers is used to signal when anything is AUTOMATICALLY
			# transferred from or to removable media
			# this includes:
			#	transfrring a package from removable media to /data
			#	performing an automatic settings restore
			# Manually triggered operations do not update these operations
			#	manually triggered settings backup
			#	manually triggered settings restore
			automaticTransfers = False

			try:
				drives = os.listdir (root)
			except:
				drives = []

			if len (drives) == 0:
				DbusIf.SetBackupMediaAvailable (False)
				DbusIf.SetBackupSettingsFileExist (False)
				backupMediaExists = False
			else:
				DbusIf.SetBackupMediaAvailable (True)
				backupMediaExists = True

			# if previously detected media is removed,
			#	allow it to be scanned again when reinserted
			for scannedDrive in alreadyScanned:
				if not scannedDrive in drives:
					alreadyScanned.remove (scannedDrive)

			for drive in drives:
				drivePath = separator.join ( [ root, drive ] )
				self.AutoUninstall = False

				# process settings backup and restore
				# check for settings backup file
				mediaSettingsBackupPath = root + "/" + drive
				if os.path.exists (mediaSettingsBackupPath + "/settingsBackup"):
					DbusIf.SetBackupSettingsFileExist (True)
					backupSettingsFileExists = True
				else:
					DbusIf.SetBackupSettingsFileExist (False)
					backupSettingsFileExists = False

				if backupMediaExists:
					autoRestoreFile = mediaSettingsBackupPath + "/SETTINGS_AUTO_RESTORE"
					if os.path.exists (autoRestoreFile):
						autoRestore = True

					autoEjectFile = mediaSettingsBackupPath + "/AUTO_EJECT"
					if os.path.exists (autoEjectFile):
						autoEject = True

					initializeFile = mediaSettingsBackupPath + "/INITIALIZE_PACKAGE_MANAGER"
					if os.path.exists (initializeFile):
						global InitializePackageManager
						InitializePackageManager = True

					
					# set the auto install flag for use elsewhere
					autoInstallOverride = False
					autoUnInstallFile = mediaSettingsBackupPath + "/AUTO_UNINSTALL_PACKAGES"
					if os.path.exists (autoUnInstallFile):
						self.AutoUninstall = True

					# set the auto install flag for use elsewhere
					# auto Uninstall overrides auto install
					if not self.AutoUninstall:
						# check for auto install on media
						autoInstallFile = mediaSettingsBackupPath + "/AUTO_INSTALL_PACKAGES"
						if os.path.exists (autoInstallFile):
							autoInstallOverride = True 	
					
					backupProgress = DbusIf.GetBackupProgress ()
					# GUI triggered backup
					if backupProgress == 1:
						DbusIf.SetBackupProgress (3)
						self.settingsBackup (mediaSettingsBackupPath)
						DbusIf.SetBackupProgress (0)
					elif backupProgress == 2 or ( autoRestore and not autoRestoreComplete ):
						if backupSettingsFileExists:
							DbusIf.SetBackupProgress (4)
							self.settingsRestore (mediaSettingsBackupPath)
							if autoRestore:
								autoRestoreComplete = True
								automaticTransfers = True
						DbusIf.SetBackupProgress (0)

				# if we've scanned this drive previously, it won't have any new packages to transfer
				# 	so skip it to avoid doing it again
				if drive not in alreadyScanned:
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
								if self.transferPackage (path, autoInstallOverride):
									automaticTransfers = True
								if self.threadRunning == False:
									return
							else:
								logging.warning (path + " not a valid archive name - rejected")
					# mark this drive so it won't get scanned again
					#	this prevents repeated installs
					alreadyScanned.append (drive)
					# end if drive not in alreadyScanned
				# end for path
			#end for drive

			# we have arrived at a point where all removable media has been scanned
			# and all possible work has been done

			# eject removable media if work has been done and the
			# the AUTO_EJECT flag file was fouund on removable media during the most recent scan
			# NOTE: this ejects ALL removable media whether or not they are involved in transfers
			if automaticTransfers and autoEject:
				logging.warning ("automatic media transfers have occured, ejecting ALL removable media")
				bus.get_object("com.victronenergy.logger", "/Storage/MountState").SetValue (2)

			if not backupMediaExists:
				autoRestore = False
				autoEject = False
				autoRestoreComplete = False
				InitializePackageManager = False

		# end while
	# end run ()
# end MediaScanClass

global noActionCount

def mainLoop():
	global mainloop
	global SystemReboot
	global GuiRestart
	global PackageIndex # initialized in main
	global PushAction
	global AllVersionsRefreshed  # initialized main and set in UpdateGitHubVersion 
	global lastDownloadMode # initialized in main
	global currentDownloadMode # initialized in main
	global noActionCount
	global MediaScan
	global InitializePackageManager
	global SetupHelperUninstall
	global LastAutoDownloadTime # initialized in main
	global PackageScanComplete # initialized in main
	global downloadDelay # initialized in main

	# auto uninstall triggered by AUTO_UNINSTALL_PACKAGES flag file on removable media
	# exit mainLoop and do uninstall in main, then reboot
	# skip all processing below !
	if MediaScan.AutoUninstall:
		mainloop.quit()
		return False
	SetupHelperUninstall = False
	statusMessage = ""

	# detect download mode changes and switch back to fast scan
	lastDownloadMode = currentDownloadMode
	currentDownloadMode = DbusIf.GetAutoDownloadMode ()
	autoInstall = DbusIf.GetAutoInstall ()

	# UpdateGitHubVersion is responsible for fetching GitHub versions
	#	when it has checked all versions it sets AllVersionsRefreshed
	#	so we can update the download mode
	# skip all package processing until the update is complete

	# setup status messages
	if currentDownloadMode == AUTO_DOWNLOADS_OFF:
		if autoInstall:
			idleMessage = "checking for installs"
		else:
			idleMessage = ""
	elif not AllVersionsRefreshed:
		idleMessage = "refreshing GitHub version information"
		PackageScanComplete = False
		PackageIndex = 0	# make sure new scan starts at beginning
	else:
		idleMessage = "checking for downloads"
		if autoInstall:
			idleMessage += " and installs"
	actionMessage = ""
	statusMessage = ""

	# after a complete scan, change modes if appropirate
	if PackageScanComplete:
		# set GitHub download delay to background rate
		downloadDelay = 600.0
		if currentDownloadMode == ONE_DOWNLOAD:
			DbusIf.SetAutoDownload (AUTO_DOWNLOADS_OFF)
		PackageScanComplete = False

	if currentDownloadMode != lastDownloadMode:
		# signal mode change to the GitHub threads
		if currentDownloadMode == ONE_DOWNLOAD or lastDownloadMode == AUTO_DOWNLOADS_OFF:
			# reset index to start of package list when mode changes
			PackageIndex = 0
			PackageScanComplete = False
			AllVersionsRefreshed = False
			UpdateGitHubVersion.GitHubVersionQueue.put ('FAST')
			downloadDelay = 10.0

	PackageClass.AddStoredPackages ()

	DbusIf.UpdateDefaultPackages ()

	# process one package per pass of mainloop
	DbusIf.LOCK ()	
	packageListLength = len (PackageClass.PackageList)
	if packageListLength > 0:
		if PackageIndex >= packageListLength:
			PackageIndex = 0
			PackageScanComplete = True
	else:
		PackageIndex = 0
		PackageScanComplete = False

	if AllVersionsRefreshed:
		package = PackageClass.PackageList [PackageIndex]
		packageName = package.PackageName
		PackageIndex += 1

		package.UpdateFileFlagsAndVersions ()
		# disallow operations on this package if anything is pending
		packageOperationOk = not package.DownloadPending and not package.InstallPending

		if packageOperationOk and currentDownloadMode != AUTO_DOWNLOADS_OFF\
					and DownloadGitHub.DownloadVersionCheck (package):
			# don't allow install if download is needed
			packageOperationOk = False

			timeToGo = downloadDelay + LastAutoDownloadTime - time.time()
			# it's time - queue the download request
			if timeToGo <= 0:
				actionMessage = "downloading " + packageName + " ..."
				PushAction ( command='download' + ':' + packageName, source='AUTO' )
				LastAutoDownloadTime = time.time ()
			# it's not time to download yet - update status message with countdown
			if timeToGo > 90:
				actionMessage = packageName + " download begins in " + "%0.1f minutes" % ( timeToGo / 60 )
			elif  timeToGo > 1.0:
				actionMessage = packageName + " download begins in " + "%0.0f seconds" % ( timeToGo )

		# validate package for install
		if packageOperationOk and package.FileSetOk and package.Incompatible == '':
			oneTimeInstallFile = "/data/" + packageName + "/ONE_TIME_INSTALL"
			installOk = False

			# check for one time install flag to force installation, overriding auto install conditions and DO_NOT_INSTALL flag - but DO check versions
			if os.path.exists (oneTimeInstallFile):
				if package.InstallVersionCheck ():
					installOk = True
				else:
					logging.warning ("One-time install - versions are the same - skipping " + packageName )
				
				# but remove the one time install flag even if install won't be performed
				os.remove (oneTimeInstallFile)

			# auto install is enabled and it's OK to auto install this package
			elif package.AutoInstallOk and package.InstallVersionCheck ():
				if DbusIf.GetAutoInstall ():
					installOk = True
				else:
					autoInstallFile = "/data/" + packageName + "/AUTO_INSTALL"
					if os.path.exists (autoInstallFile):
						installOk = True
				
			if installOk:
				actionMessage = "installing " + packageName + " ..."
				PushAction ( command='install' + ':' + packageName, source='AUTO' )
	# end if PackageScanComplete

	# check all packages before looking for reboot or GUI restart
	rebootNeeded = False
	guiRestartNeeded = False
	actionsPending = False
	for package in PackageClass.PackageList:
		if package.DownloadPending or package.InstallPending:
			actionsPending = True
		if package.GuiRestartNeeded:
			guiRestartNeeded = True
		if package.RebootNeeded:
			rebootNeeded = True
	DbusIf.UNLOCK ()
	if rebootNeeded:
		DbusIf.SetActionNeeded ('reboot')
	elif guiRestartNeeded:
		DbusIf.SetActionNeeded ('guiRestart')

	if actionsPending:
		noActionCount = 0
	else:
		noActionCount += 1

	# wait for two complete passes with nothing happening
	# 	before triggering reboot, GUI restart or initializing PackageManager Settings
	if noActionCount >= 2:
		if SystemReboot:
			statusMessage = "rebooting ..."
			# exit the main loop
			mainloop.quit()
			return False
		if InitializePackageManager:
			statusMessage = "restarting PackageManager ..."
			# exit the main loop
			mainloop.quit()
			return False
		if SetupHelperUninstall:
			statusMessage = "uninstalling SetupHelper ..."
			# exit the main loop
			mainloop.quit()
			return False
		elif GuiRestart:
			logging.warning ("restarting GUI")
			statusMessage = "restarting GUI ..."
			try:
				proc = subprocess.Popen ( [ 'svc', '-t', '/service/gui' ] )
			except:
				logging.critical ("GUI restart failed")
			GuiRestart = False
			DbusIf.SetEditStatus ("")
			DbusIf.SetGuiEditAction ('')
			# clear all package GUI restart needed flags
			# that flag is only used by the GUI to show a restart is needed for that package
			for package in PackageClass.PackageList:
				package.SetGuiRestartNeeded (False)
			# the ActionNeeded flag could be 'reboot' but that's addressed in main below anyway
			DbusIf.SetActionNeeded ('')

	if statusMessage != "":
		DbusIf.UpdateStatus ( statusMessage, where='Download' )
	elif actionMessage != "":
		DbusIf.UpdateStatus ( actionMessage, where='Download' )
	else:
		DbusIf.UpdateStatus ( idleMessage, where='Download' )

	# continue the main loop
	return True


# uninstall a package with a direct call to it's setup script
# used to do a blind uninstall in main () below

def	directUninstall (packageName):
	try:
		setupFile = "/data/" + packageName + "/setup"
		if os.path.isfile(setupFile)and os.access(setupFile, os.X_OK):
			proc = subprocess.Popen ( [ setupFile, 'uninstall', 'deferReboot', 'deferGuiRestart', 'auto' ],
										stdout=subprocess.PIPE, stderr=subprocess.PIPE )
			proc.wait()
			stdout, stderr = proc.communicate ()
			# convert from binary to string
			stdout = stdout.decode ().strip ()
			stderr = stderr.decode ().strip ()
			returnCode = proc.returncode
	except:
		pass


# remove all packages found in /data
# package must be a directory with a file named version
# with the first character of that file 'v'
# and an executale file named 'setup' must exist in the directory
# no other checks are made
# SetupHelper is NOT removed since it's running this service
# if found, returns true if it was found so it can be done later
#	just before the program ends

def removeAllPackages ():
	deferredSetupHelperRemove = False
	for path in os.listdir ("/data"):
		packageDir = "/data/" + path
		if not os.path.isdir (packageDir):
			continue
		packageName = path

		versionFile = packageDir + "/version"
		try:
			fd = open (versionFile, 'r')
			version = fd.readline().strip()
			fd.close ()
		except:
			continue
		if version[0] != 'v':
			continue
		if packageName == "SetupHelper":
			deferredSetupHelperRemove = True
		else:
			directUninstall (packageName)

	return deferredSetupHelperRemove

#	main
#
# ######## code begins here
# responsible for initialization and starting main loop and threads
# also deals with clean shutdown when main loop exits
#
def main():
	global mainloop
	global SystemReboot
	global GuiRestart
	global PackageIndex
	global noActionCount
	global InitializePackageManager
	global SetupHelperUninstall
	global LastAutoDownloadTime
	global PackageScanComplete
	global AllVersionsRefreshed  # set in UpdateGitHubVersion used in mainLoop
	global downloadDelay
	PackageScanComplete = False
	SystemReboot = False
	GuiRestart = False
	InitializePackageManager = False
	SetupHelperUninstall = False
	PackageIndex = 0
	noActionCount = 0
	LastAutoDownloadTime = 0.0
	AllVersionsRefreshed = False
	downloadDelay = 600.0

	# set logging level to include info level entries
	logging.basicConfig( format='%(levelname)s:%(message)s', level=logging.WARNING )

	# fetch installed version
	installedVersionFile = "/etc/venus/installedVersion-SetupHelper"
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

	logging.warning (">>>> PackageManager " + installedVersion + " starting")

	from dbus.mainloop.glib import DBusGMainLoop

	# Have a mainloop, so we can send/receive asynchronous calls to and from dbus
	DBusGMainLoop(set_as_default=True)
	global PythonVersion
	if PythonVersion < (3, 0):
		GLib.threads_init()

	# get venus version
	global VenusVersion
	global VenusVersionNumber
	global VersionToNumber
	versionFile = "/opt/victronenergy/version"
	try:
		file = open (versionFile, 'r')
	except:
		VenusVersion = ""
	else:
		VenusVersion = file.readline().strip()
		file.close()
	VenusVersionNumber = VersionToNumber (VenusVersion)

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
		if machine == "cerbosgx":
			Platform = "Cerbo SGX"
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

	# initialze dbus Settings and com.victronenergy.packageManager
	global DbusIf
	DbusIf = DbusIfClass ()
	
	PackageClass.AddPackagesFromDbus ()

	DbusIf.TransferOldDbusPackageInfo ()
	
	# clean up package list - eliminate any packages if its name is not valid
	#	invalid package names may be left over from a previous version
	for (index, package) in enumerate (PackageClass.PackageList):
		if not PackageClass.PackageNameValid (package.PackageName):
			PackageClass.RemovePackage (packageIndex=index)

	global UpdateGitHubVersion
	UpdateGitHubVersion = UpdateGitHubVersionClass ()

	global DownloadGitHub
	DownloadGitHub = DownloadGitHubPackagesClass ()
	
	global InstallPackages
	InstallPackages = InstallPackagesClass ()

	global AddRemove
	AddRemove = AddRemoveClass ()

	global MediaScan
	MediaScan = MediaScanClass ()

	# initialze package list
	#	and refresh versions before starting threads
	#	and the background loop

	DbusIf.ReadDefaultPackagelist ()

	PackageClass.AddStoredPackages ()
	
	DbusIf.UpdateDefaultPackages (alwaysRun = True)

	DbusIf.LOCK ()
	for package in PackageClass.PackageList:
		package.MoveFlagFiles ()
		package.UpdateFileFlagsAndVersions ()
	DbusIf.UNLOCK ()

	UpdateGitHubVersion.start()
	DownloadGitHub.start()
	InstallPackages.start()
	AddRemove.start()
	MediaScan.start ()

	global	lastDownloadMode
	global	currentDownloadMode
	lastDownloadMode = AUTO_DOWNLOADS_OFF
	currentDownloadMode = AUTO_DOWNLOADS_OFF

	# call the main loop - every 2 seconds
	# this section of code loops until mainloop quits
	GLib.timeout_add(2000, mainLoop)
	mainloop = GLib.MainLoop()
	mainloop.run()


	# this section of code runs only after the mainloop quits

	# auto uninstall triggered by AUTO_UNINSTALL_PACKAGES flag file on removable media
	if MediaScan.AutoUninstall:
		DbusIf.UpdateStatus ( message="UNINSTALLING ALL PACKAGES & REBOOTING ...", where='Download')
		DbusIf.UpdateStatus ( message="UNINSTALLING ALL PACKAGES & REBOOTING ...", where='Editor' )
		logging.warning (">>>> UNINSTALLING ALL PACKAGES & REBOOTING...")


		# remove all pacakges - returns True if SetupHelper was found and skipped
		#	 so it can be done later
		SetupHelperUninstall = removeAllPackages ()

	elif SystemReboot:
		DbusIf.UpdateStatus ( message="REBOOTING ...", where='Download')
		DbusIf.UpdateStatus ( message="REBOOTING ...", where='Editor' )
		logging.warning (">>>> REBOOTING: to complete package installation")


	# stop threads, remove service from dbus
	logging.warning ("stopping threads")
	UpdateGitHubVersion.StopThread ()
	DownloadGitHub.StopThread ()
	InstallPackages.StopThread ()
	AddRemove.StopThread ()
	MediaScan.StopThread ()

	try:
		UpdateGitHubVersion.join (timeout=30.0)
		DownloadGitHub.join (timeout=30.0)
		InstallPackages.join (timeout=10.0)
		AddRemove.join (timeout=10.0)
	except:
		logging.critical ("attempt to join threads failed - one or more threads failed to exit")
		pass

	# if initializing PackageManager persistent storage, set PackageCount to 0
	#	which will cause the package list to be rebuilt from packages found in /data
	#	user-specified Git Hub user and branch are lost
	if InitializePackageManager:
		DbusIf.DbusSettings['packageCount'] = 0

	DbusIf.RemoveDbusService ()

	# reboot with SetupHelper uninstall
	if SetupHelperUninstall:
		try:
			logging.critical (">>>> uninstalling SetupHelper and exiting")
			# schedule reboot for 30 seconds later since this script will die during the ininstall
			# this should give enough time for the uninstall to finish before reboot
			subprocess.Popen ( [ 'nohup', 'bash', '-c', 'sleep 30; shutdown -r now', '&' ], stdout=subprocess.PIPE, stderr=subprocess.PIPE  )
		except:
			pass

		directUninstall ("SetupHelper")

	# check for reboot
	elif SystemReboot:
		try:
			proc = subprocess.Popen ( [ 'shutdown', '-r', 'now', 'rebooting to complete package installation' ] )
			# for debug:    proc = subprocess.Popen ( [ 'shutdown', '-k', 'now', 'simulated reboot - system staying up' ] )
		except:
			logging.critical ("shutdown failed")

	if SystemReboot or SetupHelperUninstall:
		# insure the package manager service doesn't restart when we exit
		#	it will start up again after the reboot
		try:
			proc = subprocess.Popen ( [ 'svc', '-o', '/service/PackageManager' ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		except:
			logging.critical ("svc to shutdown PackageManager failed")

	logging.critical (">>>> PackageManager exiting")

	# program exits here

# Always run our main loop so we can process updates
main()





