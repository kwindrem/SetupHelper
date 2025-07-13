#!/usr/bin/env python
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
HOURLY_DOWNLOAD = 2
DAILY_DOWNLOAD = 3
ONE_DOWNLOAD = 99

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
#		/Package/n/Incompatible						indicates the reason the package not compatible with the system
#													"" if compatible
#													any other text if not compatible
#		/Package/n/FileSetOK						indicates if the file set for the current version is usable
#													based on the INCOMPLETE flag in the file set
#													the GUI uses this to enable/disable the Install button
#		/Package/n/PackageConflicts					 (\n separated) list of reasons for a package conflict (\n separated)
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
#			'RESTART_PM' - restart PackageManager
#			'gitHubScan' - trigger GitHub version update
#						sent when entering the package edit menu or when changing packages within that menu
#						also used to trigger a Git Hub version refresh of all packages when entering the Active packages menu
#
#		the GUI must wait for PackageManager to signal completion of one operation before initiating another
#
#		  set by PackageManager when the task is complete
#		return codes - set by PackageManager
#			'' - action completed without errors (idle)
#			'ERROR' - error during action - error reported in /GuiEditStatus:
#				unknown error
#				not compatible with this version
#				not compatible with this platform
#				no options present - must install from command line
#				GUI choices: OK - closes "dialog"
#
#	the following service parameters control settings backup and restore
#		/BackupMediaAvailable		True if suitable SD/USB media is detected by PackageManager
#		/BackupSettingsFileExist	True if PackageManager detected a settings backup file
#		/BackupSettingsLocalFileExist	True if PackageManager detected a settings backup file in /data
#		/BackupProgress				used to trigger and provide status of an operation
#									0 nothing happening - set by PackageManager when operaiton completes
#									1 set by the GUI to trigger a backup operation media
#									2 set by the GUI to trigger a restore operation media
#									3 set by PackageManager to indicate a backup to media is in progress
#									4 set by PackageManager to indicate a restore from media is in progress
#									21 set by the GUI to trigger a backup operation to /data
#									22 set by the GUI to trigger a restore operation from /data
#									23 set by PackageManager to indicate a backup is in progress to /data
#									24 set by PackageManager to indicate a restore from /data is in progress
#
# setup script return codes
EXIT_SUCCESS =				0
EXIT_REBOOT =				123
EXIT_RESTART_GUI =			124
EXIT_INCOMPATIBLE_VERSION =	254
EXIT_INCOMPATIBLE_PLATFORM = 253
EXIT_FILE_SET_ERROR	=		252
EXIT_OPTIONS_NOT_SET =		251
EXIT_RUN_AGAIN = 			250
EXIT_ROOT_FULL =			249
EXIT_DATA_FULL =			248
EXIT_NO_GUI_V1 =			247
EXIT_PACKAGE_CONFLICT =		246
EXIT_PATCH_ERROR =			245
EXIT_ERROR =				255 # generic error
#
#
#		/GuiEditStatus 				a text message to report edit status to the GUI
#
#		/PmStatus					as above for main Package Manager status
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
#									ekrano			Ekrano GX
#
#		/ActionNeeded				informs GUI if further action is needed following a manual operation
#									the operator has the option to defer reboots and GUI restarts (by choosing "Later")
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
# A version file within that directory identifies the version of that package stored on disk
#	but not necessarily installed
#
# When a package is installed, the version in the package directory is written to an "installed version" file:
#		/etc/venus/installedVersion-<packageName>
#	this file does not exist if the package is not installed
#	/etc/venus is chosen to store the installed version because it does NOT survive a firmware update
#	this will trigger an automatic reinstall following a firmware update
#
# InstalledVersion is displayed to the user and used for tests for automatic updates
#
# GitHubVersion is read from the internet if a connection exists.
#	Once the GitHub versions have been refreshed for all packages,
#		the rate of refresh is reduced so that all packages are refreshed every 10 minutes.
#		So if there are 10 packages, one refresh occurs every 60 seconds
#	Addition of a package or change in GitHubUser or GitHubBranch will trigger a fast
#		update of GitHub versions
#	If the package on GitHub can't be accessed, GitHubVersion will be blank
#	The GUI's Package editor menu will refresh the GitHub version of the current package
#		when navagating to a new package. This insures the displayed version isn't out of date
#	GitHub version information is erased 10 minutes after it was last refreshed.
#	Entering the Package versions menu wil trigger a fast refresh, again to insure the info is up to date.
#
#
# PackageManager downloads packages from GitHub based on the GitHub version and package (stored) versions:
#	if the GitHub branch is a specific version, automatic download occurs if the versions differ
#		otherwise the GitHub version must be newer.
#	the archive file is unpacked to a directory in /data named
# 		 <packageName>-<gitHubBranch>.tar.gz, then moved to /data/<packageName>, replacing the original
#
# PackageManager automatically installs the stored verion if the package (stored) and installed versions differ
#
# Automatic downloads and installs can be enabled separately.
#	Downloads checks can occur all the time, run once or be disabled
#
# Package reinstalls following a firmware update are handled as follows:
#	During system boot, reinstallMods reinstalls SetupHelper if needed
#		it then sets /etc/venus/REINSTALL_PACKAGES
# 	PackageManager tests this flag and if set, will reinstall all packages
#		even if automatic installs are disabled.
#
# Manual downloads and installs triggered from the GUI ignore version checks completely
#
#	In this context, "install" means replacing the working copy of Venus OS files with the modified ones
#		or adding new files and system services
#
#	Uninstalling means replacing the original Venus OS files to their working locations
#
#	Removed packages won't be checked for automatic install or download
#		and do not appear in the active package list in the GUI
#
#	Operations that take signficant time are handled in separate threads, decoupled from the package list
#		Operaitons are placed on a queue with all the information a processing routine needs
#
#	All operations that scan the package list must do so surrounded by
#		DbusIf.LOCK () and DbusIf.UNLOCK ()
#		and must not consume significant time: no sleeping or actions taking seconds or minutes !!!!
#		information extracted from the package list must be used within LOCK / UNLOCK to insure
#			that data is not changed by another thread.
#
# PackageManager manages flag files in the package's setup options folder:
#	DO_NOT_AUTO_INSTALL			indicates the package was manually removed and PackageManager should not
#								automatically install it
#	DO_NOT_AUTO_ADD				indicates the package was manually removed and PackageManager should not
#								automaticlly add it
#	FORCE_REMOVE				instructs PackageManager to remove the package from active packages list
#								Used rarely, only case is GuiMods setup forcing GeneratorConnector to be removed
#								this is done only at boot time.
#
#	these flags are stored in /data/setupOptions/<packageName> which is non-volatile
#		and survives a package download and firmware updates
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
#	Packages may optionally include the gitHubInfo file containg GitHub user and branch
#		gitHubInfo should have a single line of the form: gitHubUser:gitHubBranch, e.g, kwindrem:latest
#		gitHubUser and gitHubBranch are set from the file's content when it is added to the package list
#		if the package is already in the package list, gitHubInfo is ignored
#		if no GitHub information is contained in the package, 
#		an attempt is made to extract it from the defaultPackages list
#		failing that, the user must add it manually via the GUI
#		without the GitHub info, no automatic or manual downloads are possible
#
#		alternate user / branch info can be entered for a package
#		user info probalby should not change
#		branch info can be changed however to access specific tags/releases
#		or other branches (e.g., a beta test branch)
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
#				even if automatic installs are diabled and the DO_NOT_AUTO_INSTALL flag is set
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
# classes/instances:
#	AddRemoveClass
#		AddRemove runs as a separate thread
#
#	DbusIfClass
#		DbusIf
#
#	PackageClass
#		PackageList [] one per package
#
#	UpdateGitHubVersionClass
#		UpdateGitHubVersion runs as a separate thread
#
#	DownloadGitHubPackagesClass
#		DownloadGitHub runs as a separate thread
#
#	InstallPackagesClass
#		InstallPackages runs as a separate thread
#
#	MediaScanClass
#		MediaScan runs as a separate thread
#
# global methods:
#	PushAction () 
#	VersionToNumber ()
#	LocatePackagePath ()
#	AutoRebootCheck ()

import platform
import argparse
import logging

# constants for logging levels:
CRITICAL = 50
ERROR = 40
WARNING = 30
INFO = 20
DEBUG = 10

import sys
import signal
import subprocess
import threading
import os
import shutil
import dbus
import time
import re
import glob
import queue
from gi.repository import GLib
# add the path to our own packages for import
sys.path.insert(1, "/data/SetupHelper/velib_python")
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
global SystemReboot	# initialized/used in main, set in mainloop
global GuiRestart	# initialized in main, set in PushAction and InstallPackage, used in mainloop
global WaitForGitHubVersions # initialized in main, set in UpdateGitHubVersion used in mainLoop 
global InitializePackageManager # initialized/used in main, set in PushAction, MediaScan run, used in mainloop


# convert a version string to an integer to make comparisions easier
# the Victron format for version numbers is: vX.Y~Z-large-W
# the ~Z portion indicates a pre-release version so a version without it is "newer" than a version with it
# the -W portion has been abandoned but was like the ~Z for large builds and is IGNORED !!!!
#	large builds now have the same version number as the "normal" build
#
# the version string passed to this function allows for quite a bit of flexibility
#	any alpha characters are permitted prior to the first digit
#	up to 3 version parts PLUS a prerelease part are permitted
#		each with up to 4 digits each -- MORE THAN 4 digits is indeterminate
#	that is: v0.0.0d0  up to v9999.9999.9999b9999 and then v9999.9999.9999 as the highest priority
#	any non-numeric character can be used to separate main versions
#	special significance is assigned to single caracter separators between the numeric strings
#		b or ~ indicates a beta release
#		a indicates an alpha release
#		d indicates an development release
# 		these offset the pre-release number so that b/~ has higher numeric value than any a
#			and a has higher value than d separator
#
# a blank version or one without at least one number part is considered invalid
# alpha and beta seperators require at least two number parts
#	if only one number part is found the prerelease seperator is IGNORED
#
#	returns the version number or 0 if string does not parse into needed sections

def VersionToNumber (version):
	version = version.replace ("large","L")
	numberParts = re.split (r'\D+', version)
	otherParts = re.split (r'\d+', version)
	# discard blank elements
	#	this can happen if the version string starts with alpha characters (like "v")
	# 	of if there are no numeric digits in the version string
	try:
		while numberParts [0] == "":
			numberParts.pop(0)
	except:
		pass

	numberPartsLength = len (numberParts)

	if numberPartsLength == 0:
		return 0
	versionNumber = 0
	releaseType='release'
	if numberPartsLength >= 2:
		if 'b' in otherParts or '~' in otherParts:
			releaseType = 'beta'
			versionNumber += 60000
		elif 'a' in otherParts:
			releaseType = 'alpha'
			versionNumber += 30000
		elif 'd' in otherParts:
			releaseType = 'develop'

	# if release all parts contribute to the main version number
	#	and offset is greater than all prerelease versions
	if releaseType == 'release':
		versionNumber += 90000
	# if pre-release, last part will be the pre release part
	#	and others part will be part the main version number
	else:
		numberPartsLength -= 1
		if numberParts [numberPartsLength] != "":
			versionNumber += int (numberParts [numberPartsLength])

	# include core version number
	if numberPartsLength >= 1 and numberParts [0] != "":
		versionNumber += int (numberParts [0]) * 10000000000000
	if numberPartsLength >= 2 and numberParts [1] != "":
		versionNumber += int (numberParts [1]) * 1000000000
	if numberPartsLength >= 3 and numberParts [2] != "":
		versionNumber += int (numberParts [2]) * 100000

	return versionNumber


# get venus version
versionFile = "/opt/victronenergy/version"
try:
	file = open (versionFile, 'r')
except:
	VenusVersion = ""
	VenusVersionNumber = 0
else:
	VenusVersion = file.readline().strip()
	VenusVersionNumber = VersionToNumber (VenusVersion)
	file.close()

#	PushAction
#
# some actions are pushed to one of three queues:
#	InstallPackages.InstallQueue for install, uninstall, check and resolveConflicts actions
#	Download.Download for download actions
# 	AddRemoveQueue for add and remove actions
#	GitHubVersion for gitHubScan (GitHub version refresh requiests)
#
# other actions are handled in line since they just set a global flag
#		(not pused on any queue)
#		which is then handled elsewere
#
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
# returns True if command was accepted, False if not

def PushAction (command=None, source=None):
	parts = command.split (":")
	theQueue = None
	if len (parts) >= 1:
		action = parts[0]
	else:
		action = ""
	if len (parts) >= 2:
		packageName = parts[1]
	else:
		packageName = ""

	if action == 'download':
		DbusIf.LOCK ("PushAction 1")
		package = PackageClass.LocatePackage (packageName)
		if package != None:
			package.DownloadPending = True
			theQueue = DownloadGitHub.DownloadQueue
			queueText = "Download"
			# clear the install failure because package contents are changing
			#	this allows an auto install again
			#	but will be disableed if that install fails
			if source == 'GUI':
				DbusIf.UpdateStatus ( message=action  + " pending " + packageName, where='Editor' )
		else:
			theQueue = None
			queueText = ""
			errorMessage = "PushAction Download: " + packageName + " not in package list"
			logging.error (errorMessage)
			if source == 'GUI':
				DbusIf.UpdateStatus ( message=errorMessage, where='Editor' )
				DbusIf.AcknowledgeGuiEditAction ( 'ERROR', defer=True )
		DbusIf.UNLOCK ("PushAction 1")

	elif action == 'install' or action == 'uninstall' or action == 'check':
		DbusIf.LOCK ("PushAction 2")
		package = PackageClass.LocatePackage (packageName)
		# SetupHelper uninstall is processed later as PackageManager exists
		if packageName == "SetupHelper" and action == 'uninstall':
			global SetupHelperUninstall
			SetupHelperUninstall = True
		elif package != None:
			package.InstallPending = True
			theQueue = InstallPackages.InstallQueue
			queueText = "Install"
			if source == 'GUI':
				DbusIf.UpdateStatus ( message=action  + " pending " + packageName, where='Editor' )
		else:
			theQueue = None
			queueText = ""
			errorMessage = "PushAction Install: " + packageName + " not in package list"
			logging.error (errorMessage)
			if source == 'GUI':
				DbusIf.UpdateStatus ( message=errorMessage, where='Editor' )
				DbusIf.AcknowledgeGuiEditAction ( 'ERROR', defer=True )
		DbusIf.UNLOCK ("PushAction 2")

	elif action == 'resolveConflicts':
		theQueue = InstallPackages.InstallQueue
		queueText = "Install"
		if source == 'GUI':
			# note this message will be overwritten by the install and uninstall actions
			#	triggered by this action
			DbusIf.UpdateStatus ( "resolving conflicts for " + packageName, where='Editor' )

	elif action == 'add' or action == 'remove':
		theQueue = AddRemove.AddRemoveQueue
		queueText = "AddRemove"
		if source == 'GUI':
			DbusIf.UpdateStatus ( message=action  + " pending " + packageName, where='Editor' )

	elif action == 'gitHubScan':
		theQueue = UpdateGitHubVersion.GitHubVersionQueue
		queueText = "GitHubVersion"

	# the remaining actions are handled here (not pushed on a queue)
	elif action == 'reboot':
		global SystemReboot
		SystemReboot = True
		logging.warning ( "received Reboot request from " + source)
		if source == 'GUI':
			DbusIf.UpdateStatus ( message=action  + " pending " + packageName, where='Editor' )
		# set the flag - reboot is done in main_loop
		return True
	elif action == 'restartGui':
		# set the flag - reboot is done in main_loop
		global GuiRestart
		GuiRestart = True
		logging.warning ( "received GUI restart request from " + source)
		if source == 'GUI':
			DbusIf.UpdateStatus ( "GUI restart pending " + packageName, where='Editor' )
		return True
	elif action == 'INITIALIZE_PM':
		# set the flag - Initialize will quit the main loop, then work is done in main
		global InitializePackageManager
		InitializePackageManager = True
		logging.warning ( "received PackageManager INITIALIZE request from " + source)
		if source == 'GUI':
			DbusIf.UpdateStatus ( "PackageManager INITIALIZE pending " + packageName, where='Editor' )
		return True
	elif action == 'RESTART_PM':
		# set the flag - Initialize will quit the main loop, then work is done in main
		global RestartPackageManager
		RestartPackageManager = True
		logging.warning ( "received PackageManager RESTART request from " + source)
		if source == 'GUI':
			DbusIf.UpdateStatus ( "PackageManager restart pending " + packageName, where='Editor' )
		return True

	else:
		if source == 'GUI':
			DbusIf.UpdateStatus ( message="unrecognized command '" + command + "'", where='Editor' )
			DbusIf.AcknowledgeGuiEditAction ( 'ERROR', defer=True )
		logging.error ("PushAction received unrecognized command from " + source + ": " + command)
		return False

	if theQueue != None:
		try:
			theQueue.put ( (command, source), block=False )
			return True
		except queue.Full:
			logging.error ("command " + command + " from " + source + " lost - " + queueText + " - queue full")
			return False
		except:
			logging.error ("command " + command + " from " + source + " lost - " + queueText + " - other queue error")
			return False
	else:
		return False
# end PushAction


#	LocatePackagePath
#
# attempt to locate a package directory
#
# all directories at the current level are checked
#	to see if they contain a file named 'version'
#	indicating a package directory has been found
#	if so, that path is returned
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
				return newPath
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
#	Methods:
#		run ( the thread, pulls from  AddRemoveQueue)
#		StopThread ()
#
# some actions called may take seconds or minutes (based on internet speed) !!!!
#
# the queue entries are: ("action":"packageName")
#	this decouples the action from the current package list which could be changing
#	allowing the operation to proceed without locking the list

class AddRemoveClass (threading.Thread):

	def __init__(self):
		threading.Thread.__init__(self)
		self.AddRemoveQueue = queue.Queue (maxsize = 50)
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
	#
	# run () also serves as and idle loop to add packages found in /data (AddStoredPacakges)
	#	this is only called every 3 seconds
	#	and may push add commands onto the AddRemoveQueue
	#
	# StopThread () is called to shut down the thread

	def StopThread (self):
		self.threadRunning = False
		self.AddRemoveQueue.put ( ('STOP', ''), block=False )

	#	AddRemove run ()
	#
	# process package Add/Remove actions
	def run (self):
		global RestartPackageManager

		changes = False
		while self.threadRunning:
			# if package was added or removed, don't wait for queue empty
			# so package lists can be updated immediately
			if changes:
				delay = 0.0
			else:
				delay = 3.0
			try:
				command = self.AddRemoveQueue.get (timeout = delay)
			except queue.Empty:
				# adds/removes since last queue empty
				if changes:
					DbusIf.UpdateDefaultPackages ()
				# no changes so do idle processing:
				#	add packages in /data that aren't included in package list
				else:
					# restart package manager if a duplice name found in PackageList
					#	or if name is not valid
					DbusIf.LOCK ("AddRemove run")
					existingPackages = []
					duplicateFound = False
					for (index, package) in enumerate (PackageClass.PackageList):
						packageName = package.PackageName
						if packageName in existingPackages or not PackageClass.PackageNameValid (packageName):
							duplicateFound = True
							break
						existingPackages.append (packageName)
					del existingPackages
					DbusIf.UNLOCK ("AddRemove run")
					# exit this thread so no more package adds/removes are possible
					#	PackageManager will eventually reset
					if duplicateFound:
						logging.critical ("duplicate " + packageName + " found in package list - restarting PackageManager")
						RestartPackageManager = True
						return

					PackageClass.AddStoredPackages ()

				changes = False
				continue
			except:
				logging.error ("pull from AddRemoveQueue failed")
				continue
			if len (command) == 0:
				logging.error ("pull from AddRemove queue failed - empty comand")
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
					logging.error ("AddRemoveQueue - no action or no package name - discarding", command)
					continue
				source = command[1]
			else:
				logging.error ("AddRemoveQueue - no command and/or source - discarding", command)
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

				if PackageClass.AddPackage (packageName = packageName, source=source,
								gitHubUser=user, gitHubBranch=branch ):
					changes = True

			elif action == 'remove':
				if PackageClass.RemovePackage ( packageName=packageName ):
					changes = True
			else:
				logging.warning ( "received invalid action " + command + " from " + source + " - discarding" )
		# end while True
	# end run ()
# end AddRemoveClass


#	DbusIfClass
#	Instances:
#		DbusIf
#	Methods:
#		RemoveDbusSettings (class method)
#		UpdateStatus
#		various Gets and Sets for dbus parameters
#		handleGuiEditAction (dbus change handler)
#		LocateRawDefaultPackage
#		UpdateDefaultPackages ()
#		ReadDefaultPackagelist ()
#		LOCK ()
#		UNLOCK ()
#		RemoveDbusService ()
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
#	the dbus settings managed here do NOT have a package association
#	however, the per-package parameters from PackageClass are ADDED to
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
#		FALURE TO RELEASE THE LOCK WILL HANG OTHER THREADS !!!!!
#
# default package info is fetched from a file and published to our dbus service
#	for use by the GUI in adding new packages
#	the default info is also stored in defaultPackageList []
#	LocateRawDefaultPackage is used to retrieve the default from local storage
#		rather than pulling from dbus or reading the file again to save time

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
			proc = subprocess.Popen (['dbus', '-y', 'com.victronenergy.settings', '/',
						'RemoveSettings', settingsToRemove  ],
						bufsize=-1, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			_, stderr = proc.communicate ()
			stderr = stderr.decode ().strip ()
			returnCode = proc.returncode
		except:
			logging.error ("dbus RemoveSettings call failed")
		else:
			if returnCode != 0:
				logging.error ("dbus RemoveSettings failed " + str (returnCode))
				logging.error ("stderr: " + stderr)
	
	#	UpdateStatus
	#
	# updates the status when the operation completes
	# the GUI provides three different areas to show status
	# where specifies which of these are updated
	#	'PmStatus'
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
		elif where == 'PmStatus':
			DbusIf.SetPmStatus ( message )
		elif where == 'Media':
			DbusIf.SetMediaStatus (message)

	def UpdatePackageCount (self):
		count = len(PackageClass.PackageList)
		self.DbusSettings['packageCount'] = count
	def GetPackageCount (self):
		return self.DbusSettings['packageCount']
	def SetAutoDownloadMode (self, value):
		self.DbusSettings['autoDownload'] = value
	def GetAutoDownloadMode (self):
		return self.DbusSettings['autoDownload']
	def GetAutoInstall (self):
		return self.DbusSettings['autoInstall'] == 1
	def SetAutoInstall (self, value):
		if value == True:
			dbusValue = 1
		else:
			dbusValue = 0
		self.DbusSettings['autoInstall'] = dbusValue
	def SetPmStatus (self, value):
		self.DbusService['/PmStatus'] = value
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

	def SetBackupSettingsLocalFileExist (self, value):
		if value == True:
			dbusValue = 1
		else:
			dbusValue = 0
		self.DbusService['/BackupSettingsLocalFileExist'] = dbusValue

	def GetBackupSettingsFileExist (self):
		if self.DbusService['/BackupSettingsFileExist'] == 1:
			return True
		else:
			return True

	def SetBackupProgress (self, value):
		self.DbusService['/BackupProgress'] = value
	def GetBackupProgress (self):
		return self.DbusService['/BackupProgress']


	#	AcknowledgeGuiEditAction
	# is part of the PackageManager to GUI communication
	# the GUI set's an action triggering some processing here
	# 	via the dbus change handler
	# PM updates this dbus value when processing completes 
	#	signaling either success or failure
	#
	# acknowledgements can not be sent from within the GuiEditAction handler
	#	so these are deferred and processed in mainLoop
	
	def AcknowledgeGuiEditAction (self, value, defer=False):
		global DeferredGuiEditAcknowledgement

		if defer:
			DeferredGuiEditAcknowledgement = value
		else:
			# delay acknowledgement slightly to prevent lockups in the dbus system
			time.sleep (0.002)
			self.DbusService['/GuiEditAction'] = value

	def SetEditStatus (self, message):
		self.DbusService['/GuiEditStatus'] = message



	#	handleGuiEditAction (internal use only)
	#
	# the GUI uses PackageManager service /GuiEditAction
	# to request the PackageManager perform some action
	#
	# this handler disposes of the request quickly by pushing
	#	the command onto a queue or setting a global variable for later processing

	# errors that occur from the handler thread can not set the GuiEditAction
	#	since the parameter will be set to the value passed to the handler
	# 	overriding the one set within the handler thread

	def handleGuiEditAction (self, path, command):
		global PushAction
		# ignore a blank command - this happens when the command is cleared
		#	and should not trigger further action
		if command == "":
			pass
		else:
			PushAction ( command=command, source='GUI' )
		return True	# True acknowledges the dbus change - otherwise dbus parameter does not change


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

	def UpdateDefaultPackages (self):
		DbusIf.LOCK ("UpdateDefaultPackages")
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

		DbusIf.UNLOCK ("UpdateDefaultPackages")


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
	#
	# locked sections of code should execute quickly to minimize impact on other threads
	#
	# failure to UNLOCK will result in a LOCK request from another thread timing out
	#
	# lock requests that time out result in PackageManager exiting immediately without cleanup
	# supervise will then restart it
	
	def LOCK (self, name):
		requestTime = time.time()
		reportTime = requestTime
		while True:
			if self.lock.acquire (blocking=False):
				# here if lock was acquired
				return
			else:
				time.sleep (0.1)
				currentTime = time.time()
				# waiting for 5 seconds - timeout
				if currentTime - requestTime > 5.0:
					logging.critical ("timeout waiting for lock " + name + " - restarting PackageManager")
					os._exit(1)		
				# report waiting every 1 second
				elif currentTime - reportTime > 0.5:
					logging.warning ("waiting to aquire lock " + name)
					reportTime = currentTime

		
	def UNLOCK (self, name):
		try:
			self.lock.release ()
		except RuntimeError:
			logging.error ("UNLOCK when not locked - continuing " + name)
			

	def __init__(self):
		self.lock = threading.RLock()
		settingsList = {'packageCount': [ '/Settings/PackageManager/Count', 0, 0, 0 ],
						'autoDownload': [ '/Settings/PackageManager/GitHubAutoDownload', 0, 0, 0 ],
						'autoInstall': [ '/Settings/PackageManager/AutoInstall', 0, 0, 0 ],
						}
		self.DbusSettings = SettingsDevice(bus=dbus.SystemBus(), supportedSettings=settingsList,
								timeout = 30, eventCallback=None )

		# check firmware version and delay dbus service registration for v3.40~38 and beyond
		global VenusVersionNumber
		global VersionToNumber
		self.DbusService = VeDbusService ('com.victronenergy.packageManager', bus = dbus.SystemBus(), register=False)
		
		self.DbusService.add_mandatory_paths (
							processname = 'PackageManager', processversion = 1.0, connection = 'none',
							deviceinstance = 0, productid = 1, productname = 'Package Manager',
							firmwareversion = 1, hardwareversion = 0, connected = 1)
		self.DbusService.add_path ( '/MediaUpdateStatus', "", writeable = True )
		self.DbusService.add_path ( '/GuiEditStatus', "", writeable = True )

		self.DbusService.add_path ( '/GuiEditAction', "", writeable = True,
										onchangecallback = self.handleGuiEditAction )

		# initialize default package list to empty - entries will be added later
		self.DbusService.add_path ('/DefaultCount', 0 )

		# a special package used for editing a package prior to adding it to Package list
		self.EditPackage = PackageClass ( section = "Edit", packageName = "" )
		
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

		self.DbusService.add_path ( '/BackupMediaAvailable', 0, writeable = True )
		self.DbusService.add_path ( '/BackupSettingsFileExist', 0, writeable = True )
		self.DbusService.add_path ( '/BackupSettingsLocalFileExist', 0, writeable = True )
		self.DbusService.add_path ( '/BackupProgress', 0, writeable = True )

		# do these last because the GUI uses them to check if PackageManager is running
		self.DbusService.add_path ( '/PmStatus', "", writeable = True )
		global Platform
		self.DbusService.add_path ( '/Platform', Platform )

		self.DbusService.register ()


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
#		GetAutoAddOk (class method)
#		SetAutoAddOk (class method)
#		SetAutoInstallOk ()
#		settingChangedHandler ()
#		various Gets and Sets
#		AddPackagesFromDbus (class method)
#		PackageNameValid (class method)
#		AddStoredPackages (class method)
#		AddPackage (class method)
#		RemovePackage (class method)
#		UpdateVersionsAndFlags ()
#
#	Globals:
#		PackageList [] - list instances of all packages
#		DbusSettings (for per-package settings)
#		DbusService (for per-package parameters)
#		DownloadPending
#		InstallPending
#
# a package consits of Settings and version parameters in the PackageMonitor dbus service
# all Settings and parameters are accessible via set... and get... methods
#	so that the caller does not need to understand dbus Settings and service syntax
# the packageName variable maintains a local copy of the dBus parameter for speed in loops
# section passed to init can be either a int or string ('Edit')
#	an int is converted to a string to form the dbus setting paths
#
# the dbus settings and service parameters managed here are on a per-package basis

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


	def SetAutoInstallOk (self, state):
		packageName = self.PackageName
		if packageName == None:
			logging.error ("SetAutoInstallOk - no packageName")
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

	def SetIncompatible (self, value, details="", resolvable=False):
		self.Incompatible = value
		self.IncompatibleDetails = details
		self.IncompatibleResolvable = resolvable
		if self.incompatiblePath != "":
			DbusIf.DbusService[self.incompatiblePath] = value	
		if self.incompatibleDetailsPath != "":
			DbusIf.DbusService[self.incompatibleDetailsPath] = details
		if self.IncompatibleResolvablePath != "":
			if resolvable:
				DbusIf.DbusService[self.IncompatibleResolvablePath] = 1
			else:
				DbusIf.DbusService[self.IncompatibleResolvablePath] = 0

	def settingChangedHandler (self, name, old, new):
		# when dbus information changes, need to refresh local mirrors
		if name == 'packageName':
			self.PackageName = new
		elif name == 'gitHubBranch':
			self.GitHubBranch = new
			if self.PackageName != None and self.PackageName != "":
				UpdateGitHubVersion.SetPriorityGitHubVersion ( 'package:' + self.PackageName )
		elif name == 'gitHubUser':
			self.GitHubUser = new
			if self.PackageName != None and self.PackageName != "":
				UpdateGitHubVersion.SetPriorityGitHubVersion ( 'package:' + self.PackageName )

	def __init__( self, section, packageName = None ):
		# add package parameters if it's a real package (not Edit)
		if section != 'Edit':
			section = str (section)
			self.gitHubVersionPath = '/Package/' + section + '/GitHubVersion'
			self.packageVersionPath = '/Package/' + section + '/PackageVersion'
			self.installedVersionPath = '/Package/' + section + '/InstalledVersion'
			self.incompatiblePath = '/Package/' + section + '/Incompatible'
			self.incompatibleDetailsPath = '/Package/' + section + '/IncompatibleDetails'
			self.IncompatibleResolvablePath = '/Package/' + section + '/IncompatibleResolvable'

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
				foo = DbusIf.DbusService[self.incompatiblePath]
			except:
				DbusIf.DbusService.add_path (self.incompatiblePath, "" )
			try:
				foo = DbusIf.DbusService[self.incompatibleDetailsPath]
			except:
				DbusIf.DbusService.add_path (self.incompatibleDetailsPath, "" )
			try:
				foo = DbusIf.DbusService[self.IncompatibleResolvablePath]
			except:
				DbusIf.DbusService.add_path (self.IncompatibleResolvablePath, "" )

		self.packageNamePath = '/Settings/PackageManager/' + section + '/PackageName'
		self.gitHubUserPath = '/Settings/PackageManager/' + section + '/GitHubUser'
		self.gitHubBranchPath = '/Settings/PackageManager/' + section + '/GitHubBranch'

		# temporarily set PackageName since settingChangeHandler may be called as soon as SettingsDevice is called
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
		
		# these flags are used to insure multiple actions aren't executed on top of each other
		self.DownloadPending = False
		self.InstallPending = False
		self.InstallAfterDownload = False	# used by ResolveConflicts when doing both download and install

		self.AutoInstallOk = False
		self.DependencyErrors = []
		self.FileConflicts = []
		self.PatchCheckErrors = []
		self.ConflictsResolvable = True

		self.ActionNeeded = ''

		self.lastScriptPrecheck = 0

		self.lastGitHubRefresh = 0

		# init dbus parameters
		# these have local values also to speed access
		# only create service parameters for real packages
		if section != 'Edit':
			self.SetInstalledVersion ("")
			self.SetPackageVersion ("")
			self.SetGitHubVersion ("")
			self.SetIncompatible ("")
			# copy dbus info to local values
			self.GitHubUser = self.DbusSettings['gitHubUser']
			self.GitHubBranch = self.DbusSettings['gitHubBranch']
		# init edit GitHub info
		else:
			self.SetGitHubUser ("?")
			self.SetGitHubBranch ("?")


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
	# invalid names contain strings in the rejectStrings
	#	or complete names in rejectNames
	#	or names beginning with '.'
	#
	# returns true if name is OK, false if in the reject list

	rejectStrings = [ "-current", "-latest", "-main", "-test", "-temp", "-debug", "-beta", "-backup1", "-backup2",
					"-blind", "-0", "-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9", "ccgx", " " ]

	rejectNames = [ "conf", "db", "etc", "home", "keys", "log", "lost+found", "setupOptions", "themes", "tmp", "var", "venus", "vrmfilescache" ]

	@classmethod
	def PackageNameValid (cls, packageName):

		if packageName == None or packageName == "":
			return False

		if packageName[0] == '.':
			return False

		for reject in cls.rejectNames:
			if reject == packageName:
				return False

		for reject in cls.rejectStrings:
			if reject in packageName:
				return False

		return True


	#	AddStoredPackages
	# add packages stored in /data to the package list
	# in order to qualify as a package:
	#	must be a directory
	#	name must not contain strings in the reject lists
	#	name must not include any spaces
	#	directory must contain a file named setup
	#	diretory must contain a file named version
	#	first character of version file must be 'v'
	#	name must be unique - that is not match any existing packages
	# order of validating tests minimizes execution time (determined emperically)
	#
	# AddStoredPackages is called from init
	#	and the AddPackages run () loop for background updates

	@classmethod
	def AddStoredPackages (cls):
		global Platform

		platformIsRaspberryPi = Platform[0:4] == 'Rasp'

		for packageName in os.listdir ("/data"):
			if not PackageClass.PackageNameValid (packageName):
				continue
			# if package is already in the active list - skip it
			DbusIf.LOCK ("AddStoredPackages")
			package = PackageClass.LocatePackage (packageName)
			DbusIf.UNLOCK ("AddStoredPackages")			
			if package != None:
				continue

			packageDir = "/data/" + packageName

			# skip if no setup file - also verifies packageDir is a directory!
			if not os.path.exists (packageDir + "/setup"):
				continue

			# skip if no version file or not a valid version
			versionFile = packageDir + "/version"
			try:
				fd = open (versionFile, 'r')
				version = fd.readline().strip()
				fd.close ()
			except:
				continue
			if version == "" or version[0] != 'v':
				continue
			# skip if package is for Raspberry PI only and platform is not
			if os.path.exists (packageDir + "/raspberryPiOnly") and not platformIsRaspberryPi:
				continue
			# skip if package was manually removed
			if not PackageClass.GetAutoAddOk (packageName):
				continue
			# package is unique and passed all tests - schedule the package addition
			PushAction ( command='add:' + packageName, source='AUTO')


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
				DbusIf.AcknowledgeGuiEditAction ( 'ERROR' )
			return False

		# insure packageName is unique before adding this new package
		success = False
		DbusIf.LOCK ("AddPackage")
		package = PackageClass.LocatePackage (packageName)

		# new packageName is unique, OK to add it
		if package == None:
			DbusIf.UpdateStatus ( message="adding " + packageName, where='Editor', logLevel=WARNING )

			section = len(cls.PackageList)
			cls.PackageList.append( PackageClass ( section, packageName = packageName ) )
			DbusIf.UpdatePackageCount ()
			success = True

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
				DbusIf.AcknowledgeGuiEditAction ( '' )
				DbusIf.UpdateStatus ( message = "", where='Editor')

			# allow auto adds and auto installs
			PackageClass.SetAutoAddOk (packageName, True)
			package.SetAutoInstallOk (True)

		else:
			if source == 'GUI':
				DbusIf.UpdateStatus ( message=packageName + " already exists - choose another name", where=reportStatusTo, logLevel=WARNING )
				DbusIf.AcknowledgeGuiEditAction ( 'ERROR' )
			else:
				DbusIf.UpdateStatus ( message=packageName + " already exists", where=reportStatusTo, logLevel=WARNING )
		
		DbusIf.UNLOCK ("AddPackage")
		return success
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
	def RemovePackage (cls, packageName=None, packageIndex=None, isDuplicate=False ):
		# packageName specified so this is a call from the GUI
		if packageName != None:
			guiRequestedRemove = True
			if packageName == "SetupHelper":
				DbusIf.UpdateStatus ( message="REMOVING SetupHelper" + packageName, where='Editor', logLevel=CRITICAL )
			else:
				DbusIf.UpdateStatus ( message="removing " + packageName, where='Editor', logLevel=WARNING )
		# no package name specified, so this is a call from system initialization - messages to log only
		elif packageIndex != None:
			guiRequestedRemove = False
			name = PackageClass.PackageList [packageIndex].PackageName
			if name == None or name == "":
				logging.error ( "RemovePackage: removing package without a name" )
			else:
				logging.warning ( "RemovePackage: removing " + name )
		# neither package name nor package instance passed - can't do anything
		else:
			logging.error ( "RemovePackage: no package info passed - nothing done" )
			return

		DbusIf.LOCK ("RemovePackage")
		packages = PackageClass.PackageList
		listLength = len (packages)
		if listLength == 0:
			DbusIf.UNLOCK ("RemovePackage")
			return

		# locate index of packageName
		#	LocaatePackage not used because we want the index anyway
		if guiRequestedRemove:
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

		packageIsInstalled = packages[toIndex].InstalledVersion != ""
		
		# if package is installed, don't remove it
		if matchFound and not packageIsInstalled:
			# if not just removing a duplicate
			# block future automatic adds since the package is being removed
			if not isDuplicate:
				PackageClass.SetAutoAddOk (packageName, False)

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
				toPackage.SetIncompatible (fromPackage.Incompatible, fromPackage.IncompatibleDetails,
															fromPackage.IncompatibleResolvable )

				# package variables
				toPackage.DownloadPending = fromPackage.DownloadPending
				toPackage.InstallPending = fromPackage.InstallPending
				toPackage.AutoInstallOk = fromPackage.AutoInstallOk
				toPackage.DependencyErrors = fromPackage.DependencyErrors
				toPackage.FileConflicts = fromPackage.FileConflicts
				toPackage.PatchCheckErrors = fromPackage.PatchCheckErrors
				toPackage.lastScriptPrecheck = fromPackage.lastScriptPrecheck
				toPackage.lastGitHubRefresh = fromPackage.lastGitHubRefresh
				toPackage.ActionNeeded = fromPackage.ActionNeeded

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
			toPackage.SetIncompatible ("")

			# remove the Settings and service paths for the package being removed
			DbusIf.RemoveDbusSettings ( [toPackage.packageNamePath, toPackage.gitHubUserPath, toPackage.gitHubBranchPath] )

			# remove entry from package list
			packages.pop (toIndex)
			DbusIf.UpdatePackageCount ()
		DbusIf.UNLOCK ("RemovePackage")
		# this package was manually removed so block automatic adds
		#	in the package directory
		if guiRequestedRemove:
			if matchFound:
				# block automatic adds
				PackageClass.SetAutoAddOk (packageName, False)

				DbusIf.UpdateStatus ( message="", where='Editor' )
				DbusIf.AcknowledgeGuiEditAction ( '' )
			else:
				DbusIf.UpdateStatus ( message=packageName + " not removed - name not found", where='Editor', logLevel=ERROR )
				DbusIf.AcknowledgeGuiEditAction ( 'ERROR' )
		return matchFound
	# end RemovePackage


	#	UpdateVersionsAndFlags
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

	def UpdateVersionsAndFlags (self, doConflictChecks=False, doScriptPreChecks=False):
		global VersionToNumber
		global VenusVersion
		global VenusVersionNumber
		global Platform

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
			self.SetIncompatible ("no package")
			return

		# fetch package version (the one in /data/packageName)
		try:
			versionFile = open (packageDir + "/version", 'r')
			packageVersion = versionFile.readline().strip()
			versionFile.close()
		except:
			packageVersion = ""
		self.SetPackageVersion (packageVersion)

		compatible = True

		# set the incompatible parameter
		#	to 'PLATFORM' or 'VERSION'
		if os.path.exists (packageDir + "/raspberryPiOnly" ):
			if Platform[0:4] != 'Rasp':
				self.SetIncompatible ("incompatible with " + Platform)
				compatible = False
				doConflictChecks = False

		# update local auto install flag based on DO_NOT_AUTO_INSTALL
		flagFile = "/data/setupOptions/" + packageName + "/DO_NOT_AUTO_INSTALL"
		if os.path.exists (flagFile):
			self.AutoInstallOk = False
		else:
			self.AutoInstallOk = True

		# platform is OK, now check versions
		if compatible:
			try:
				fd = open (packageDir + "/firstCompatibleVersion", 'r')
				firstVersion = fd.readline().strip()
				fd.close ()
			except:
				firstVersion = "v2.71"
			try:
				fd = open (packageDir + "/obsoleteVersion", 'r')
				obsoleteVersion = fd.readline().strip()
				fd.close ()
			except:
				obsoleteVersion = "v9999.9999.9999"
			
			firstVersionNumber = VersionToNumber (firstVersion)
			obsoleteVersionNumber = VersionToNumber (obsoleteVersion)
			if VenusVersionNumber < firstVersionNumber or VenusVersionNumber >= obsoleteVersionNumber:
				self.SetIncompatible ("incompatible with " + VenusVersion)
				compatible = False
				doConflictChecks = False
			elif os.path.exists (packageDir + "/validFirmwareVersions"):
				with open(packageDir + "/validFirmwareVersions") as f:
					lines = f.readlines ()
					versionPresent = False
					for line in lines:
						if line.strip() == VenusVersion:
							versionPresent = True
							break
					if not versionPresent:
						self.SetIncompatible ("incompatible with " + VenusVersion)
						compatible = False
						doConflictChecks = False

		# check to see if command line is needed for install
		# the optionsRequired flag in the package directory indicates options must be set before a blind install
		# the optionsSet flag indicates the options HAVE been set already
		# so if optionsRequired == True and optionsSet == False, can't install from GUI
		if compatible:
			if os.path.exists ("/data/" + packageName + "/optionsRequired" ):
				if not os.path.exists ( "/data/setupOptions/" + packageName + "/optionsSet"):
					self.SetIncompatible ("install from command line" )
					compatible = False
					doConflictChecks = False

		# check to see if file set has errors
		if compatible:
			fileSetsDir = packageDir + "/FileSets"
			fileSet = fileSetsDir + "/" + VenusVersion
			if os.path.exists (fileSet + "/INCOMPLETE"):
				self.SetIncompatible ("incomplete file set for " + str (VenusVersion) )
				compatible = False
				doConflictChecks = False


		# check for package conflicts - but not if an operation is in progress
		if doConflictChecks and not self.InstallPending and not self.DownloadPending:
			# update dependencies
			dependencyFile = "/data/" + packageName + "/packageDependencies"
			dependencyErrors = []
			if os.path.exists (dependencyFile):
				try:
					with open (dependencyFile, 'r') as file:
						for item in file:
							parts = item.split ()
							if len (parts) < 2:
								logging.error ("package dependency " + item + " incomplete")
								continue
							dependencyPackage = parts [0]
							dependencyRequirement = parts [1]

							installedFile = "/etc/venus/installedVersion-" + dependencyPackage
							packageIsInstalled = os.path.exists (installedFile)
							packageMustBeInstalled = dependencyRequirement == "installed"
							if packageIsInstalled != packageMustBeInstalled:
								dependencyErrors.append ( (dependencyPackage, dependencyRequirement) )
					dependencyErrors.sort()
				except:
					pass
			# log dependency changes if they have changed
			if dependencyErrors != self.DependencyErrors:
				self.DependencyErrors = dependencyErrors
				if len (dependencyErrors) > 0:
					for dependency in dependencyErrors:
						(dependencyPackage, dependencyRequirement) = dependency
						logging.warning (packageName + " requires " + dependencyPackage + " to be " + dependencyRequirement)
				else:
					logging.warning ("dependency conflicts for " + packageName + " have been resolved")

			# check for file conflicts with prevously installed packages
			# each line in all file lists are checked to see if the <active file>.package contains a different package name
			# if they differ, a conflict between this and the other package exists
			#	requiring one or the other package to be uninstalled
			#
			# patched files are NOT checked because they patch the active file
			# the setup script with the 'check' option will test the patch file
			#	and report any patch failures

			fileConflicts = []
			fileLists =  [ "fileList", "fileListVersionIndependent" ]
			for fileList in fileLists:
				path = "/data/" + packageName + "/FileSets/" + fileList
				if not os.path.exists (path):
					continue
				try:
					with open (path, 'r') as file:
						# valid entries begin with / and everything after white space is discarded
						# the result should be a full path to one replacment file
						for entry in file:
							entry = entry.strip ()
							if not entry.startswith ("/"):
								continue
							replacementFile = entry.split ()[0].strip ()
							packagesList = replacementFile + ".package"
							if not os.path.exists ( packagesList ) :
								continue
							# if a package list for an active file changes,
							#	run script checks again to uncover new or resolved conflicts
							if os.path.getmtime (packagesList) > self.lastScriptPrecheck:
								doScriptPreChecks = True
							try:
								with open (packagesList, 'r') as plFile:
									for entry2 in plFile:
										packageFromList = entry2.strip()
										# here if previously updated file was from a different package
										if packageFromList != packageName:
											file =  os.path.basename (replacementFile)
											fileConflicts.append ( (packageFromList, "uninstalled", file) )
							except:
								pass
				except:
					logging.critical ("error while reading file lists for " + packageName)
					continue

			conflicts = self.DependencyErrors

			if fileConflicts != self.FileConflicts:
				self.FileConflicts = fileConflicts
				if len (fileConflicts) > 0:
					for (otherPackage, dependency, file) in fileConflicts:
						logging.warning ("to install " + packageName + ", " + otherPackage + " must not be installed (" + file + ")" )
						conflicts.append ( ( otherPackage, dependency ) )
				else:
					logging.warning ("file conflicts for " + packageName + " have been resolved")

			details = ""
			if len (conflicts) > 0:
				# eliminate duplicates
				conflicts = list ( set ( conflicts ) )
				resolveOk = True
				for ( otherPackage, dependency ) in conflicts:
					if dependency == "uninstalled":
						details += otherPackage + " must not be installed\n"
					else:
						conflictPackage = PackageClass.LocatePackage (otherPackage)
						if conflictPackage == None:
							details += otherPackage + " must be installed but not available\n"
							resolveOk = False
						elif conflictPackage.PackageVersion != "":
							details += otherPackage + " must be installed\n"
						elif conflictPackage.GitHubVersion != "":
							details += otherPackage + " must be downloaded and installed\n"
						else:
							details += otherPackage + " unknown\n"
				self.SetIncompatible ("package conflict", details, resolvable=resolveOk)
				compatible = False

			# check for and report patch errors if there are no other errors
			else:
				patchCheckErrors = []
				if os.path.exists (packageDir + "/patchErrors"):
					# rebuild patch errors list
					with open ( packageDir + "/patchErrors" ) as file:
						for line in file:
							patchCheckErrors.append ( line )
							compatible = False
					patchCheckErrors = list ( set ( patchCheckErrors ) )
				if patchCheckErrors != self.PatchCheckErrors:
					self.PatchCheckErrors = patchCheckErrors
					if len (patchCheckErrors) > 0:
						for line in patchCheckErrors:
							patchFailure = line.strip()
							details += patchFailure + "\n"
							logging.warning (packageName + " patch check error: " + patchFailure + " ")
						self.SetIncompatible ("patch error", details,)
					else:
						logging.warning (packageName + " patch check reported no errors")

			# make sure script checks are run once at boot
			#	(eg patched errors, but there are others)
			if self.lastScriptPrecheck == 0:
				doScriptPreChecks = True
			self.lastScriptPrecheck = time.time ()
		# end if doConflictChecks

		# if no incompatibilities found, clear incompatible dbus parameters
		#	so the GUI will allow installs
		if compatible:
			self.SetIncompatible ("")

		# run setup script to check for file conflicts (can't be checked here)
		if doScriptPreChecks and os.path.exists ("/data/" + packageName + "/setup"):
			PushAction ( command='check' + ':' + packageName, source='AUTO' )
	# end UpdateVersionsAndFlags
# end Package


#	UpdateGitHubVersionClass
#
# downloads the GitHub versions
# this work is done in a separate thread so network activity can be spaced out
#	and isolated from other acvities since they may take a while on slow networks
# 
# a message is used to trigger a priority update for a specific package
#		this is used when the operator changes GitHub user/branch so the version
#			updates rapidly
#	or speed up the refresh rate
# a STOP message is used to wake the thread
#	so that the tread can exit wihout waitin for a potentially long timeout
#
# background refreshes are triggered by a queue timeout while waiting for messages
#	refreshes occur rapidly to refresh the GUI and minimize time waiting for the versions
#	or are spaced out over time such that version information is refreshed every 10 seconds
#
#	Instances:
#		UpdateGitHubVersion (a separate thread)
#
#	Methods:
#		updateGitHubVersion 
#		run ()
#		StopThread ()
#
# delay for GitHub version refreshes
# slow refresh also controls GitHub version expiration

FAST_GITHUB_REFRESH = 0.25
NORMAL_GITHUB_REFRESH = 600.0	# 10 minutes
HOURLY_GITHUB_REFRESH = 60.0 * 60.0
DAILY_GITHUB_REFRESH = HOURLY_GITHUB_REFRESH * 24.0

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
						bufsize=-1, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			stdout, _ = proc.communicate ()
			stdout = stdout.decode ().strip ()
			returnCode = proc.returncode
		except:
			logging.error ("wget for version failed " + packageName)
			gitHubVersion = ""
		else:
			if proc.returncode == 0:
				gitHubVersion = stdout
			else:
				gitHubVersion = ""

		# locate the package with this name and update it's GitHubVersion
		# if not in the list discard the information
		DbusIf.LOCK ("updateGitHubVersion")
		package = PackageClass.LocatePackage (packageName)
		if package != None:
			package.SetGitHubVersion (gitHubVersion)
			package.lastGitHubRefresh = time.time ()
		DbusIf.UNLOCK ("updateGitHubVersion")
		return gitHubVersion


	def __init__(self):
		threading.Thread.__init__(self)
		self.GitHubVersionQueue = queue.Queue (maxsize = 50)
		self.threadRunning = True
		# package needing immediate update
		self.priorityPackageName = None


	#	SetPriorityGitHubVersion
	# pushes a priority package version update onto our queue
	#
	# 'local' is a dummy source for the queue pull
	
	def SetPriorityGitHubVersion (self, command):
		self.GitHubVersionQueue.put ( (command, 'local'), block=False )


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
	#		the shorter delay is used again when we pull "REFRESH" off the queue
	#
	#	when the que returns an item, it is checked to see if it is either a
	#		prioirty package to update it's GitHub version 
	#		"STOP" - indicating run should return
	#		"REFRESH" - indicating the loop should update all package GitHub versions
	#			this is used when download refresh mode/rates change
	#		"ALL" - same as REFRESH but from the GUI
	#			(uses the saem message path from GUI as the prioirty package update)
	#			when entering the Active packages menu
	#			need to clear the dbus /GuiEditAction
	#		checks the threadRunning flag and returns if it is False,
	#	when run returns, the main method should catch the tread with join ()

	def StopThread (self):
		self.threadRunning = False
		self.SetPriorityGitHubVersion ( 'STOP' )


	def run (self):
		global WaitForGitHubVersions

		gitHubVersionPackageIndex = 0
		forcedRefresh = True

		packageListLength = 0
		
		while self.threadRunning:
			downloadMode = DbusIf.GetAutoDownloadMode ()

			# do initial refreshes quickly
			if forcedRefresh:
				delay = FAST_GITHUB_REFRESH
			# otherwise set delay to complete scan of all versions in the selected refresh period
			#	this prevents GitHub versions from going undefined if refreshes are happening
			else:
				if downloadMode == NORMAL_DOWNLOAD:
					delay = NORMAL_GITHUB_REFRESH
				elif downloadMode == HOURLY_DOWNLOAD:
					delay = HOURLY_GITHUB_REFRESH
				else:
					delay = DAILY_GITHUB_REFRESH
				#	this prevents divide by zero - value not actually used
				if packageListLength != 0:
					delay /= packageListLength
			# queue gets STOP and REFRESH commands or priority package name
			# empty queue signals it's time for a background update
			# queue timeout is used to pace background updates
			command = ""
			source = ""
			packageName = ""
			try:
				(command, source) = self.GitHubVersionQueue.get (timeout = delay)
				parts = command.split (":")
				length = len (parts)
				if length >= 1:
					command = parts [0]
				if length >= 2:
					packageName = parts [1]
			except queue.Empty:	# means get() timed out as expected - not an error
				# timeout indicates it's time to do a background update
				pass
			except:
				logging.error ("pull from GitHubVersionQueue failed")
			if command == 'STOP' or self.threadRunning == False:
				return

			doUpdate = False
			packageUpdate = False

			# the REFRESH command triggers a refresh of all pachage Git Hub versions
			# background scans in the mainLoop are blocked until the refresh is complete
			if command == 'REFRESH':
				gitHubVersionPackageIndex = 0
				# hold off other processing until refresh is complete
				WaitForGitHubVersions = True
				forcedRefresh = True		# guarantee at least one pass even if auto downloads are off
			# refresh request was received from GUI
			elif source == 'GUI':
				# acknowledge command ASAP to minimize time GUI is held off
				DbusIf.AcknowledgeGuiEditAction ('')
				if command != 'gitHubScan':
					logging.error ("incomplete GitHub refresh request from GUI: " + str(parts))
				# if GUI is requesting a refresh of all package versions, trigger a one-time refresh
				# but does not block background scans in mainLoop
				elif packageName == 'ALL':
					if not forcedRefresh:
						gitHubVersionPackageIndex = 0
						forcedRefresh = True
				# refresh is for a spcific package
				elif packageName != "":
					packageUpdate = True
				else:
					logging.error ("missing name in GitHub refresh request from GUI: " + str(parts))
			# package priority update NOT from the GUI
			elif source == 'local' and packageName != "":
				packageUpdate = True
			if packageUpdate:
				DbusIf.LOCK ("UpdateGitHubVersion run 1")
				package = PackageClass.LocatePackage (packageName)
				if package != None:
					user = package.GitHubUser
					branch = package.GitHubBranch
					# always do the update for 'local' source
					if source != 'GUI':
						doUpdate = True
					# for GUI - refresh if no version or last refresh more than 30 seconds ago
					# prevents unnecessary network traffic when navigating PackageManager menus
					elif package.GitHubVersion == "" or time.time () > package.lastGitHubRefresh + 30:
						doUpdate = True
				else:
					logging.error ("can't fetch GitHub version - " + packageName + " not in package list")
				DbusIf.UNLOCK ("UpdateGitHubVersion run 1")

			doBackground = forcedRefresh or downloadMode != AUTO_DOWNLOADS_OFF
			# no priority update - do background update
			if not doUpdate and doBackground:
				DbusIf.LOCK ("UpdateGitHubVersion run 2")
				packageListLength = len (PackageClass.PackageList)
				# empty package list - no refreshes possible
				if packageListLength == 0:
					gitHubVersionPackageIndex = 0
				# select package to update
				elif gitHubVersionPackageIndex < packageListLength:
					package = PackageClass.PackageList[gitHubVersionPackageIndex]
					packageName = package.PackageName
					user = package.GitHubUser
					branch = package.GitHubBranch
					doUpdate = True
					gitHubVersionPackageIndex += 1
				# reached end of list - all package Git Hub versions have been refreshed
				if gitHubVersionPackageIndex >= packageListLength:
					gitHubVersionPackageIndex = 0
					# notify the main loop that all versions have been refreshed and
					# download modes can now be changed if appropriate
					WaitForGitHubVersions = False
					forcedRefresh = False
				DbusIf.UNLOCK ("UpdateGitHubVersion run 2")

			# do the actual background update outsde the above LOCKED section
			#	since the update requires internet access
			if doUpdate:
				self.updateGitHubVersion (packageName, user, branch)
		# end while self.threadRunning
	# end UpdateGitHubVersion run ()
# end UpdateGitHubVersionClass


#	DownloadGitHubPackagesClass
#
# downloads packages from GitHub, replacing the existing package
#
# downloads can take significant time, so they are handled in a separate thread
#
# the GUI and auto download code (in main loop) push download
#	actions onto this queue
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
#		run
#		StopThread
#
# the run () thread is only responsible for pacing automatic downloads from the internet
#	commands are pushed onto the processing queue (PushAction)

class DownloadGitHubPackagesClass (threading.Thread):

	def __init__(self):
		threading.Thread.__init__(self)
		self.DownloadQueue = queue.Queue (maxsize = 50)
		self.threadRunning = True


	# this method downloads a package from GitHub
	# it is called from run() below
	#
	# download requests are pushed for automatic downloads from mainloop
	# and also for a manual download triggered from the GUI
	#
	# automatic downloads that fail are logged but otherwise not reported

	def GitHubDownload (self, packageName=None, source=None):
		if source == 'GUI':
			where = 'Editor'
		elif source == 'AUTO':
			where = 'PmStatus'
		else:
			where = None

		errorMessage = None
		errorDetails = None
		downloadError = False

		if packageName == None or packageName == "":
			logging.error ("GitHubDownload: no package name specified")
			downloadError = True

		if not downloadError:
			packagePath = "/data/" + packageName
			tempPackagePath = packagePath + "-temp"

			DbusIf.LOCK ("GitHubDownload - get GitHub user/branch")
			package = PackageClass.LocatePackage (packageName)
			gitHubUser = package.GitHubUser
			gitHubBranch = package.GitHubBranch
			DbusIf.UNLOCK ("GitHubDownload - get GitHub user/branch")

			DbusIf.UpdateStatus ( message="downloading " + packageName, where=where, logLevel=WARNING )

			tempDirectory = "/data/PmDownloadTemp"
			if not os.path.exists (tempDirectory):
				os.mkdir (tempDirectory)

			# create temp directory specific to this thread
			tempArchiveFile = tempDirectory + "/temp.tar.gz"
			# download archive
			if os.path.exists (tempArchiveFile):
				os.remove ( tempArchiveFile )

			url = "https://github.com/" + gitHubUser + "/" + packageName  + "/archive/" + gitHubBranch  + ".tar.gz"
			try:
				proc = subprocess.Popen ( ['wget', '--timeout=120', '-qO', tempArchiveFile, url ],
									bufsize=-1, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
				_, stderr = proc.communicate()
				stderr = stderr.decode ().strip ()
				returnCode = proc.returncode
			except:
				errorMessage = "could not access archive on GitHub " + packageName
				downloadError = True
			else:
				if returnCode != 0:
					errorMessage = "could not access " + packageName + ' ' + gitHubUser + ' ' + gitHubBranch + " on GitHub"
					errorDetails = "returnCode:" + str (returnCode)
					if stderr != "":
						errorDetails +=  " stderr:" + stderr
					downloadError = True
		if not downloadError:
			try:
				proc = subprocess.Popen ( ['tar', '-xzf', tempArchiveFile, '-C', tempDirectory ],
								bufsize=-1, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
				_, stderr = proc.communicate ()
				stderr = stderr.decode ().strip ()
				returnCode = proc.returncode
			except:
				errorMessage = "could not unpack " + packageName + ' ' + gitHubUser + ' ' + gitHubBranch
				downloadError = True
			else:
				if returnCode != 0:
					errorMessage = "unpack failed " + packageName + ' ' + gitHubUser + ' ' + gitHubBranch
					errorDetails = "stderr: " + stderr
					downloadError = True

		if not downloadError:
			# attempt to locate a directory that contains a version file
			# the first directory in the tree starting with tempDirectory is returned
			unpackedPath = LocatePackagePath (tempDirectory)
			if unpackedPath == None:
				errorMessage = "no archive path for " + packageName
				downloadError = True

		if not downloadError:
			# move unpacked archive to package location
			# LOCK this section of code to prevent others
			#	from accessing the directory while it's being updated
			try:
				if os.path.exists (tempPackagePath):
					shutil.rmtree (tempPackagePath, ignore_errors=True)	# like rm -rf
			except:
				pass

			DbusIf.LOCK ("GitHubDownload - move package")
			try:
				if os.path.exists (packagePath):
					os.rename (packagePath, tempPackagePath)
				shutil.move (unpackedPath, packagePath)
				
			except:
				errorMessage = "couldn't update " + packageName
				downloadError = True
			DbusIf.UNLOCK ("GitHubDownload - move package")

		DbusIf.LOCK ("GitHubDownload - update status")
		package = PackageClass.LocatePackage (packageName)
		if package != None:
			installAfter = package.InstallAfterDownload	# save install after flag for later, then clear it
			package.InstallAfterDownload = False
			package.DownloadPending = False
			if not downloadError:
				# update basic flags then request install
				if installAfter:
					package.UpdateVersionsAndFlags ()
					logging.warning ("install after download requested for " + packageName)
					PushAction ( command='install' + ':' + packageName, source=source )
				# no install after, do full version/flag update
				else:
					package.UpdateVersionsAndFlags (doConflictChecks=True, doScriptPreChecks=True)
		DbusIf.UNLOCK ("GitHubDownload - update status")

		# report errors / success
		if errorMessage != None:
			logging.error (errorMessage)
		if errorDetails != None:
			logging.error (errorDetails)
		DbusIf.UpdateStatus ( message=errorMessage, where=where )
		if source == 'GUI':
			if errorMessage != None:
				DbusIf.AcknowledgeGuiEditAction ( 'ERROR' )
			# don't ack success if there's more to do
			elif not installAfter:
				DbusIf.AcknowledgeGuiEditAction ( '' )

		# remove any remaining temp directories
		if os.path.exists (tempPackagePath):
			shutil.rmtree (tempPackagePath, ignore_errors=True)	# like rm -rf
		if os.path.exists (tempDirectory):
			shutil.rmtree (tempDirectory, ignore_errors=True)
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
					continue
				source = command[1]
			else:
				logging.error ("DownloadQueue - no command and/or source - discarding", command)
				continue

			# invalid action for this queue
			if action != 'download':
				logging.error ("received invalid command from Install queue: ", command )
				continue

			# do the download here
			self.GitHubDownload (packageName=packageName, source=source )
		# end while True
	# end run
# end DownloadGitHubPackagesClass
					

#	InstallPackagesClass
#	Instances:
#		InstallPackages (a separate thread)
#
#	Methods:
#		InstallPackage
#		ResolveConflicts
#		run (the thread)
#		StopThread
#		run
#
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
		DbusIf.SetPmStatus ("")
		self.threadRunning = True
		self.InstallQueue = queue.Queue (maxsize = 10)

	
	#	InstallPackage
	#
	# this method either installs, uninstalls or checks a package
	#	by calling the package's setup script
	#
	# the 'check' action runs file set checks without installing the package
	#	this creates a missing file set then sets/clears the INCOMPLETE flag
	#	a missing file set is reported as "no file set" but does not block installs
	#	an INCOMPLETE file set blocks installs
	#	therefore, check attempts to resolve a missing file set
	#
	# the operation can take many seconds
	# 	i.e., the time it takes to run the package's setup script
	#
	# uninstalling SetupHelper is a special case since that action will end PackageManager
	#	so it is deferred until mainLoop detects the request and exits to main
	#	where the actual uninstall occurs

	def InstallPackage ( self, packageName=None, source=None , action='install' ):

		global SetupHelperUninstall

		# refresh versions, then check to see if an install is possible
		DbusIf.LOCK ("InstallPackage")
		package = PackageClass.LocatePackage (packageName)

		if package == None:
			logging.error ("InstallPackage: " + packageName + " not in package list")
			if source == 'GUI':
				DbusIf.UpdateStatus ( message=packageName + " not in package list", where='Editor' )
				DbusIf.AcknowledgeGuiEditAction ( 'ERROR' )
			DbusIf.UNLOCK ("InstallPackage error 1")
			return

		if source == 'GUI':
			sendStatusTo = 'Editor'
			# uninstall sets the uninstall flag file to prevent auto install
			if action == 'uninstall':
				package.SetAutoInstallOk (False)
				logging.warning (packageName + " was manually uninstalled - auto install for that package will be skipped")
			# manual install removes the flag file
			elif action == 'install':
				package.SetAutoInstallOk (True)
				logging.warning (packageName + " was manually installed - allowing auto install for that package")
		elif source == 'AUTO':
			sendStatusTo = 'PmStatus'

		packageDir = "/data/" + packageName
		if not os.path.isdir (packageDir):
			errorMessage = "no package directory " + packageName
			logging.error ("InstallPackage - " + errorMessage)
			package.InstallPending = False
			package.UpdateVersionsAndFlags ()
			if source == 'GUI':
				DbusIf.AcknowledgeGuiEditAction ( 'ERROR' )
			DbusIf.UNLOCK ("InstallPackage error 2")
			return
			
		setupFile = packageDir + "/setup"
		if not os.path.isfile(setupFile):
			errorMessage = "setup file for " + packageName + " doesn't exist"
			DbusIf.UpdateStatus ( message=errorMessage,	where=sendStatusTo, logLevel=ERROR )
			package.InstallPending = False
			package.UpdateVersionsAndFlags ()
			if source == 'GUI':
				DbusIf.AcknowledgeGuiEditAction ( 'ERROR' )
			DbusIf.UNLOCK ("InstallPackage error 3")
			return
		elif os.access(setupFile, os.X_OK) == False:
			errorMessage = "setup file for " + packageName + " not executable"
			DbusIf.UpdateStatus ( message=errorMessage,	where=sendStatusTo, logLevel=ERROR )
			package.InstallPending = False
			if source == 'GUI':
				DbusIf.AcknowledgeGuiEditAction ( 'ERROR' )
			DbusIf.UNLOCK ("InstallPackage error 4")
			return

		DbusIf.UNLOCK ("InstallPackage normal")

		DbusIf.UpdateStatus ( message=action + "ing " + packageName, where=sendStatusTo, logLevel=WARNING )
		try:
			proc = subprocess.Popen ( [ setupFile, action, 'runFromPm' ],
										bufsize=-1, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
			_, stderr = proc.communicate ()
			stderr = stderr.decode ().strip ()
			returnCode = proc.returncode
			setupRunFail = False
		except:
			setupRunFail = True

		# manage the result of the setup run while locked just in case
		DbusIf.LOCK ("InstallPackage - update status")

		package = PackageClass.LocatePackage (packageName)
		package.InstallPending = False

		errorMessage = ""
		if setupRunFail:
			errorMessage = "could not run setup"
		elif returnCode == EXIT_SUCCESS:
			DbusIf.UpdateStatus ( message="", where=sendStatusTo )
			if source == 'GUI':
				DbusIf.AcknowledgeGuiEditAction ( '' )
		elif returnCode == EXIT_REBOOT:
			package.ActionNeeded = REBOOT_NEEDED
			if source == 'GUI':
				logging.warning ( packageName + " " + action + " REBOOT needed but handled by GUI")
				DbusIf.UpdateStatus ( message="", where=sendStatusTo )
				DbusIf.AcknowledgeGuiEditAction ( "" )
			# auto install triggers a reboot by setting the global flag - reboot handled in main_loop
			else:
				logging.warning ( packageName + " " + action + " REBOOT pending")
				global SystemReboot
				SystemReboot = True
		elif returnCode == EXIT_RESTART_GUI:
			package.ActionNeeded = GUI_RESTART_NEEDED
			if source == 'GUI':
				logging.warning ( packageName + " " + action + " GUI restart needed but handled by GUI")
				DbusIf.UpdateStatus ( message="", where=sendStatusTo )
				DbusIf.AcknowledgeGuiEditAction ( "" )
			# auto install triggers a GUI restart by setting the global flag - restart handled in main_loop
			else:
				logging.warning ( packageName + " " + action + " GUI restart pending")
				global GuiRestart
				GuiRestart = True
		elif returnCode == EXIT_RUN_AGAIN:
			if source == 'GUI':
				DbusIf.UpdateStatus ( message=packageName + " run install again to complete install",
											where=sendStatusTo, logLevel=WARNING )
				DbusIf.AcknowledgeGuiEditAction ( 'ERROR' )
			else:
				DbusIf.UpdateStatus ( message=packageName + " setup must be run again",
											where=sendStatusTo, logLevel=WARNING )
		elif returnCode == EXIT_INCOMPATIBLE_VERSION:
			global VenusVersion
			errorMessage = "incompatible with " + VenusVersion
		elif returnCode == EXIT_INCOMPATIBLE_PLATFORM:
			global Platform
			errorMessage = "incompatible with " + Platform
		elif returnCode == EXIT_OPTIONS_NOT_SET:
			errorMessage = "setup must be run from the command line"
		elif returnCode == EXIT_FILE_SET_ERROR:
			errorMessage = "incomplete file set for " + VenusVersion
		elif returnCode == EXIT_ROOT_FULL:
			errorMessage = "no room on root partition "
		elif returnCode == EXIT_DATA_FULL:
			errorMessage = "no room on data partition "
		elif returnCode == EXIT_NO_GUI_V1:
			errorMessage = "failed - " + "GUI v1 not installed"
		elif returnCode == EXIT_PACKAGE_CONFLICT:
			errorMessage = "package conflict " + stderr
		elif returnCode == EXIT_PATCH_ERROR:
			errorMessage = "could not patch some files"
		# unknown error
		elif returnCode != 0:
			errorMessage = "unknown error " + str (returnCode) + " " + stderr

		if errorMessage != "":
			if setupRunFail:
				logLevel = ERROR
			else:
				logLevel = WARNING
			DbusIf.UpdateStatus ( message=packageName + " " + action + " failed - " + errorMessage,
					where=sendStatusTo, logLevel=logLevel )
			if source == 'GUI':
				DbusIf.AcknowledgeGuiEditAction ( 'ERROR' )

		# installs do script conflict checks
		#	update last check time here so checks aren't run right away
		package.lastScriptPrecheck = time.time ()

		package.UpdateVersionsAndFlags ()

		DbusIf.UNLOCK ("InstallPackage - update status")
	# end InstallPackage ()


	# 	ResolveConflicts
	#
	# this method checks the conflicts for the indicated package
	# if conflicts exist, the conflicting package(s) are installed or uninstalled
	# by pushing them on the install queue
	
	def ResolveConflicts ( self, packageName=None, source=None ):

		if packageName == None:
			logging.error ("ResolveConflicts - no package name specified")
			return

		DbusIf.LOCK ("ResolveConflicts")
	
		package = PackageClass.LocatePackage (packageName)
		if package == None:
			logging.error ("ResolveConflicts: " + packageName + "not found")

		for conflict in (package.DependencyErrors + package.FileConflicts):
			if len (conflict) < 2:
				logging.error ("ResolveConflicts: " + packageName + " missing parameters: " + str (conflict) )
				continue
			dependencyPackage = conflict[0]
			dependencyRequirement = conflict[1]
			if dependencyRequirement == "installed":
				packageMustBeInstalled = True
			elif dependencyRequirement == "uninstalled":
				packageMustBeInstalled = False
			else:
				logging.error ("ResolveConflicts: " + packageName + " unrecognized requirement: " + str (conflict) )
				continue

			requiredPackage = PackageClass.LocatePackage (dependencyPackage)

			if requiredPackage.InstalledVersion != "":
				packageIsInstalled = True
			else:
				packageIsInstalled = False
			if requiredPackage.PackageVersion != "":
				packageIsStored = True
			else:
				packageIsStored = False
			if requiredPackage.GitHubVersion != "":
				packageIsOnGitHub = True
			else:
				packageIsOnGitHub = False
			if packageIsStored or packageIsOnGitHub:
				packageIsAvailable = True
			else:
				packageIsAvailable = True

			if packageMustBeInstalled and not packageIsInstalled:
				if not packageIsAvailable:
					DbusIf.UpdateStatus ( message=dependencyPackage + " not available - can't install",
								where='Editor', logLevel=WARNING )
				elif not packageIsStored and packageIsOnGitHub:
					logging.warning ("ResolveConflicts: downloading and installing" + dependencyPackage + " so that " + packageName + " can be installed" )
					PushAction ( command='download' + ':' + dependencyPackage, source=source )
					# download will trigger install when it finished
					requiredPackage.InstallAfterDownload = True
				else:
					logging.warning ("ResolveConflicts: installing " + dependencyPackage + " so that " + packageName + " can be installed" )
					PushAction ( command='install' + ':' + dependencyPackage, source=source )

			elif not packageMustBeInstalled and packageIsInstalled:
				logging.warning ("ResolveConflicts: uninstalling " + dependencyPackage + " so that " + packageName + " can be installed" )
				PushAction ( command='uninstall' + ':' + dependencyPackage, source=source )

		DbusIf.UNLOCK ("ResolveConflicts")


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
					continue
				source = command[1]
			else:
				logging.error ("InstallQueue - no command and/or source - discarding", command)
				continue

			# resolve conflicts may cause OTHER packages to install or uninstall
			if action == 'resolveConflicts':
				self.ResolveConflicts (packageName=packageName, source=source)
			# otherwise use InstallPackage to install, uninstall, or check the package
			elif action == 'install' or action == 'uninstall' or action == 'check':
				self.InstallPackage (packageName=packageName, source=source , action=action )

			# invalid action for this queue
			else:
				logging.error ("received invalid command from Install queue: ", command )
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
#
# removable media is checked for several "flag files" that trigger actions elsewhere
#	these are described in detail at the beginning of this file
#	scans for flag files is done in run ()

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
							bufsize=-1, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			_, stderr = proc.communicate ()
			stderr = stderr.decode ().strip ()
			returnCode = proc.returncode
		except:
			DbusIf.UpdateStatus ( message="tar failed for " + packageName,
									where='Media', logLevel=ERROR)
			time.sleep (5.0)
			DbusIf.UpdateStatus ( message="", where='Media')
			return False
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
		DbusIf.LOCK ("transferPackage") 
		if os.path.exists (tempPackagePath):
			shutil.rmtree (tempPackagePath, ignore_errors=True)	# like rm -rf
		if os.path.exists (packagePath):
			os.rename (packagePath, tempPackagePath)
		try:
			shutil.move (unpackedPath, packagePath)
		except:
			logging.error ( "transferPackages: couldn't relocate " + packageName )
		if os.path.exists (tempPackagePath):
			shutil.rmtree (tempPackagePath, ignore_errors=True)	# like rm -rf
		# set package one-time install flag so this package is installed regardless of other flags
		#	this flag is removed when the install is preformed
		if autoInstallOverride:
			logging.warning ("Auto Install - setting ONE_TIME_INSTALL for " + packageName )
			open ( packagePath + "/ONE_TIME_INSTALL", 'a').close()

		DbusIf.UNLOCK ("transferPackage")
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
	# copies ALL log files (backup only obvously)
	#	the files are zipped to save space
	#
	# backup and restore options are either to/from removable media or /data
	#
	# settingsList contains the list of dbus /Settings parameters to save and restore
	#

	def settingsBackup (self, backupPath, settingsOnly = False):
		settingsCount = 0
		overlayCount = 0
		logsWritten = "no logs"

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
		
		if not settingsOnly:
			# backup logo overlays
			overlaySourceDir = "/data/themes/overlay"
			overlayDestDir = backupPath + "/logoBackup"

			
			# remove any previous logo backups
			if os.path.isdir (overlayDestDir):
				shutil.rmtree (overlayDestDir)

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
			try:
				# remove any previous log backups
				logDestDir = backupPath + "/logs"
				if os.path.isdir (logDestDir):
					shutil.rmtree (logDestDir)

				proc = subprocess.Popen ( [ 'zip', '-rq', backupPath + "/logs.zip", "/data/log" ],
										bufsize=-1, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
				proc.commiunicate()	#output ignored
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


	def settingsRestore (self, backupPath, settingsOnly = False):
		backupFile = backupPath + "/settingsBackup"
		if not os.path.exists (backupFile):
			logging.error (backupFile + " does not exist - can't restore settings")
		bus = dbus.SystemBus()
		settingsCount = 0
		overlayCount = 0


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
											bufsize=-1, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
							proc.commiunicate ()	# output ignored
							parameterExists = True
							logging.warning ("settingsRestore: creating " + path)
						except:
							logging.error ("settingsRestore: settings create failed for " + path)

				# update parameter's value if it exists (or was just created)
				if parameterExists:
					bus.get_object("com.victronenergy.settings", path).SetValue (value)
					settingsCount += 1

		if not settingsOnly:
			# restore logo overlays
			overlaySourceDir = backupPath + "/logoBackup"
			overlayDestDir = "/data/themes/overlay"
			if os.path.isdir (overlaySourceDir):
				overlayFiles = os.listdir (overlaySourceDir)
				if len (overlayFiles) > 0:
					# create overlay direcory in /data, then copy files
					if not os.path.isdir (overlayDestDir):
						os.mkdir (overlayDestDir)
					for overlay in overlayFiles:
						if overlay[0] == ".":
							continue
						try:
							shutil.copy ( overlaySourceDir + "/" + overlay, overlayDestDir )
						except:
							logging.error ("settingsRestore: overlay create failed for " + overlay)
						overlayCount += 1

			# restore setup script options
			optionsSourceDir = backupPath + "/setupOptions"
			optionsDestDir = "/data/setupOptions"

			# remove any previous options backups
			if os.path.isdir (optionsDestDir):
				shutil.rmtree (optionsDestDir)

			if os.path.isdir (optionsSourceDir):
				try:
					shutil.copytree ( optionsSourceDir, optionsDestDir )
				except:
					logging.error ("settingsRestore: options restore failed")
		
		logging.warning ("settings restore completed - " + str(settingsCount) + " settings and " + str (overlayCount) + " overlays")


	#	Media Scan run (the thread)
	#
	# run () checks the threadRunning flag and returns if it is False,
	#	essentially taking the thread off-line
	#	the main method should catch the tread with join ()
	# StopThread () is called to shut down the thread
	#
	# a queue with set timeout is used to pace operations
	#	 this gives other threads time away from slower media scanning operations

	def StopThread (self):
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
		localSettingsBackupExists = True

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

			# do local settings backup/restore
			if os.path.exists ("/data/settingsBackup"):
				localSettingsBackupExists = True
				DbusIf.SetBackupSettingsLocalFileExist (True)
			else:
				localSettingsBackupExists = False
				DbusIf.SetBackupSettingsLocalFileExist (False)

			backupProgress = DbusIf.GetBackupProgress ()
			if backupProgress == 21:
				DbusIf.SetBackupProgress (23)
				self.settingsBackup ("/data", settingsOnly = True)
				DbusIf.SetBackupProgress (0)
			elif backupProgress == 22:
				if localSettingsBackupExists:
					DbusIf.SetBackupProgress (24)
					self.settingsRestore ("/data", settingsOnly = True)
				DbusIf.SetBackupProgress (0)


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

		# end while
	# end run ()
# end MediaScanClass



# main and mainLoop
#
#	Methods:
#		mainLoop
#		main ( the entry point)
#		directUninstall
#
#	mainLoop is called each second to make background checks
#	update global and package flags, versions, etc
#	and schedule automatic installs, uninstalls, downloads, etc
#
#	operations that can not be done in line may be deferred here:
#		GUI restarts and system reboots
#		PackageManager restarts and INITIALIZE
#		GUI command acknowledgement from within the thread of the command handler
#
#	handshakes between threads often use a global variable rather than pushing something on a queue:
#		install/download check holdoff while waiting for GitHub version refresh
#
#	some operations performed in mainLoop take a while but do not need to be done every second
#	to spread things out, and minimize impact on other tasks within Venus Os,
#	only one package is checked each second
# 	(it would take 10 seconds to scan 10 packages)
#
#	PackageManager is responsible for reinstalling packages following a firmware update
#	reinstallMods is a script called from /data/rcS.local that installs the PackageManager service
#		then sets the /etc/venus/REINSTALL_PACKAGES flag file instructing PackageManager
#		to do a boot-time check all packages for possible reinstall
#		PackageManager clears that flag when all packages have been reinstalled
#	boot-time reinstall is done using the normal automatic install mechanism but bypasses
#		the test for the user selectable auto install on/off
#
#	mainLoop is resonsible for triggering GUI restarts and system reboots
#	installs, uninstalls and downloads are handled by the package's setup script
#		but the script does not initalte these options.
#	the results of the setup script set reboot/reset flags for the package
#	the actual restart/reboot actions are held off as long as any package operations are pending
#		so repeaded GUI restarts or system reboots are avoided
#	this gives all packages a chance to download and/or install automatically
#		before the restart/reboot
#
#	mainLoop also handles PackageManager restart and INITIALIZE actions
#	INITIALZE wipes out the package information in dbus /Settings then quits
#	The package information is then rebuilt the next time PackageManager starts
#
#	mainLoop also provides status information to the GUI
#
#	GUI restarts are handled without exiting PackageManager, however
#	system reboots and Package manager restarts and INITIALIZE actions require
#	PackageManager to exit
#	The actual operations are performed in main () after mainLoop quits
#
#	mainLoop is "scheduled" to run from GLib which is all set up in main()
#		however, mainLoop is not a simple loop
#		it is called once per second by GLib then exits True
#		mainLoop exits by calling mainloop.quit() then returning False
#
#	main is tasks:
#		instializing global variables that do not change over time
#		instantiating objects
#		retriving nonvolatile information from dbus /Settings
#		starting all threads
#		start mainLoop
#
#		the code after mainloop.run() does not execute until mainLoop exits
#		at which time the activities necessarey for a clean exit are performed:
#
#		an uninstall all function triggered by a flag on removable media
#			this allows a blind uninstall of all packages (including SetupHelper)
#			in the event the GUI becomes unresponsive and the user has no access to the console
#		stopping all threads
#		PackageManager actual initialziation
#			is done by setting the package count in dbus /Settings to 0
#		remove dbus com.victronenergy.packageManager
#		uninstalling SetupHelper if requested above
#			done by trigging a nohup backround task that sleeps for 30 seconds then installs the package
#		reboot the system
#		exit

# persistent storage for mainLoop
packageIndex = 0
noActionCount = 0
lastDownloadMode = AUTO_DOWNLOADS_OFF
bootInstall = False
ignoreBootInstall = False
DeferredGuiEditAcknowledgement = None
lastTimeSync = 0

WaitForGitHubVersions = False
			
# states for package.ActionNeeded
REBOOT_NEEDED = 2
GUI_RESTART_NEEDED = 1
NONE = 0

def mainLoop ():
	global mainloop
	global PushAction
	global MediaScan
	global SystemReboot	# initialized/used in main, set in mainloop, PushAction, InstallPackage
	global GuiRestart	# initialized in main, set in PushAction, InstallPackage, used in mainloop
	global WaitForGitHubVersions  # initialized above, set in UpdateGitHubVersion used in mainLoop 
	global InitializePackageManager # initialized/used in main, set in PushAction, MediaScan run, used in mainloop
	global RestartPackageManager # initialized/used in main, set in PushAction, MediaScan run, used in mainloop
	global DeferredGuiEditAcknowledgement # set in the handleGuiEditAction thread becasue the dbus paramter can't be set there

	global noActionCount
	global packageIndex
	global noActionCount
	global lastDownloadMode
	global bootInstall
	global ignoreBootInstall
	global lastTimeSync
	startTime = time.time()

	# an unclean shutdown will not save the last known time of day
	#	which is used during the next boot until ntp can sync time
	#	so do it here every 30 seconds
	# an old RTC
	timeSyncCommand = '/etc/init.d/save-rtc.sh'
	if startTime > lastTimeSync + 30 and os.path.exists (timeSyncCommand):
		try:
			subprocess.Popen ( [ timeSyncCommand ],
					bufsize=-1, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			proc.commiunicate ()	# output ignored
		except:
			pass
		lastTimeSync = startTime

	packageName = "none"

	if DeferredGuiEditAcknowledgement != None:
		DbusIf.AcknowledgeGuiEditAction (DeferredGuiEditAcknowledgement)
		DeferredGuiEditAcknowledgement = None


	# auto uninstall triggered by AUTO_UNINSTALL_PACKAGES flag file on removable media
	#	or SetupHelper uninstall was deferred
	# exit mainLoop and do uninstall in main, then reboot
	# skip all processing below !
	actionMessage = ""
	bootReinstallFile="/etc/venus/REINSTALL_PACKAGES"

	currentDownloadMode = DbusIf.GetAutoDownloadMode ()
	emptyPackageList = False
	checkPackages = True
	autoInstall = False
	autoDownload = False

	# hold off all package processing if package list is empty
	if len (PackageClass.PackageList) == 0:
		emptyPackageList = True
		checkPackages = False
		packageIndex = 0

	# if boot-time reinstall has been requiested by reinstallMods
	#	override modes and initiate auto install of all packages
	# ignore the boot reinstall flag if it's been done once and the flag removal failed
	elif os.path.exists (bootReinstallFile) and not ignoreBootInstall:
		# beginning of boot install - reset package index to insure a complete scan
		if not bootInstall:
			bootInstall = True
			packageIndex = 0
			logging.warning ("starting boot-time reinstall")
	elif WaitForGitHubVersions:
		checkPackages = False

	# don't look for new actions if uninstalling all packages or uninstalling SetupHelper
	elif MediaScan.AutoUninstall or SetupHelperUninstall:
		pass
	# not doing something special - use dbus values
	else:
		autoDownload = currentDownloadMode != AUTO_DOWNLOADS_OFF
		autoInstall = DbusIf.GetAutoInstall ()

		# download mode changed
		# restart at beginning of list and refresh all GitHub versions
		if currentDownloadMode != lastDownloadMode and currentDownloadMode != AUTO_DOWNLOADS_OFF:
			packageIndex = 0
			checkPackages = False
			UpdateGitHubVersion.SetPriorityGitHubVersion ('REFRESH')
		# save mode so changes can be detected on next pass
		lastDownloadMode = currentDownloadMode

	# make sure a new scan starts at beginning of list
	if not checkPackages:
		packageIndex = 0
	# process one package per pass of mainloop
	else:
		DbusIf.LOCK ("mainLoop 1")	
		packageListLength = len (PackageClass.PackageList)
		# reached end of list - start over
		if packageIndex >= packageListLength:
			packageIndex = 0
			# end of ONCE download - switch auto downloads off
			if currentDownloadMode == ONE_DOWNLOAD:
				DbusIf.SetAutoDownloadMode (AUTO_DOWNLOADS_OFF)
				currentDownloadMode = AUTO_DOWNLOADS_OFF
			# end of boot install
			if bootInstall:
				logging.warning ("boot-time reinstall complete")
				bootInstall = False
				if os.path.exists (bootReinstallFile):
					try:
						os.remove (bootReinstallFile)
					except FileNotFoundError:
						pass
					except:
						# log the error and continue
						# set flag so we don't repeat the reinstall if the flag removal fails (until next boot)
						ignoreBootInstall = True
						logging.critical ("could not remove the boot time reinstall flag: /etc/venus/REINSTALL_PACKAGES")

		package = PackageClass.PackageList [packageIndex]
		packageName = package.PackageName
		packageIndex += 1

		# skip conflict checks if boot-time checks are bening made
		package.UpdateVersionsAndFlags (doConflictChecks = not bootInstall)

		# disallow operations on this package if anything is pending
		packageOperationOk = not package.DownloadPending and not package.InstallPending
		if packageOperationOk and autoDownload and DownloadGitHub.DownloadVersionCheck (package):
			# don't allow install if download is needed - even if it has not started yet
			packageOperationOk = False
			actionMessage = "downloading " + packageName + " ..."
			PushAction ( command='download' + ':' + packageName, source='AUTO' )

		# validate package for install
		if packageOperationOk and package.Incompatible == "" :
			installOk = False
			# one-time install flag file is set in package directory - install without further checks
			oneTimeInstallFile = "/data/" + packageName + "/ONE_TIME_INSTALL"
			if os.path.exists (oneTimeInstallFile):
				os.remove (oneTimeInstallFile)
				installOk = True
			# auto install OK (not manually uninstalled) and versions are different
			elif package.AutoInstallOk and package.PackageVersionNumber != package.InstalledVersionNumber:
				if autoInstall:
					installOk = True
				# do boot-time install only if the package is not installed
				elif bootInstall and package.InstalledVersion == "":
					installOk = True
				elif os.path.exists ("/data/" + packageName + "/AUTO_INSTALL"):
					installOk = True

			if installOk:
				packageOperationOk = False
				actionMessage = "installing " + packageName + " ..."
				PushAction ( command='install' + ':' + packageName, source='AUTO' )
		DbusIf.UNLOCK ("mainLoop 1")
	# end if checkPackages

	DbusIf.LOCK ("mainLoop 2")
	actionsPending = False
	actionsNeeded = ""
	systemAction = NONE
	# hold off reboot or GUI restart if any package has an action pending
	# collect actions needed to activage changes - only sent to GUI - no action taken
	for package in PackageClass.PackageList:
		if package.DownloadPending or package.InstallPending:
			actionsPending = True
		# clear GitHub version if not refreshed in 10 minutes
		elif package.GitHubVersion != "" and package.lastGitHubRefresh > 0 and time.time () > package.lastGitHubRefresh + NORMAL_GITHUB_REFRESH + 10:
			package.SetGitHubVersion ("")

		if package.ActionNeeded == REBOOT_NEEDED:
			actionsNeeded += (package.PackageName + " requires REBOOT\n")
			systemAction = REBOOT_NEEDED
		elif package.ActionNeeded == GUI_RESTART_NEEDED:
			actionsNeeded += (package.PackageName + " requires GUI restart\n")
			if systemAction != REBOOT_NEEDED:
				systemAction = GUI_RESTART_NEEDED

	if systemAction == REBOOT_NEEDED:
		actionsNeeded += "REBOOT system ?"
	elif systemAction == GUI_RESTART_NEEDED:
		actionsNeeded += "restart GUI ?"

	# don't show an action needed if reboot, etc is pending
	if SystemReboot or GuiRestart or RestartPackageManager or InitializePackageManager:
		DbusIf.DbusService['/ActionNeeded'] = ""
	else:
		DbusIf.DbusService['/ActionNeeded'] = actionsNeeded

	DbusIf.UNLOCK ("mainLoop 2")

	if actionsPending:
		noActionCount = 0
	else:
		noActionCount += 1

	# wait for two complete passes with nothing happening
	# 	before triggering reboot, GUI restart or initializing PackageManager Settings
	#	or ininstalling packages
	# these actions are all handled in main () after mainLoop () exits
	if noActionCount >= 2:
		if SystemReboot or InitializePackageManager or GuiRestart\
				 or RestartPackageManager or MediaScan.AutoUninstall or SetupHelperUninstall:
			# already exiting - include pending operations
			if systemAction == REBOOT_NEEDED:
				SystemReboot = True
			elif systemAction == GUI_RESTART_NEEDED:
				GuiRestart = True
			mainloop.quit()
			return False

	if actionMessage != "":
		DbusIf.UpdateStatus ( actionMessage, where='PmStatus' )
	else:
		if emptyPackageList:
			idleMessage = "no active packages"
		elif bootInstall:
			idleMessage = "reinstalling packages after firmware update"
		elif WaitForGitHubVersions:
			idleMessage = "refreshing GitHub version information"
		elif currentDownloadMode != AUTO_DOWNLOADS_OFF and autoInstall:
			idleMessage = "checking for downloads and installs"
		elif currentDownloadMode == AUTO_DOWNLOADS_OFF and autoInstall:
			idleMessage = "checking for installs"
		elif currentDownloadMode != AUTO_DOWNLOADS_OFF and not autoInstall:
			idleMessage = "checking for downloads"
		else:
			idleMessage = ""
		DbusIf.UpdateStatus ( idleMessage, where='PmStatus' )

	# enable the following lines to report execution time of main loop
	####endTime = time.time()
	####print ("main loop time %3.1f mS" % ( (endTime - startTime) * 1000 ), packageName)

	# to continue the main loop, must return True
	return True
# end mainLoop

# uninstall a package with a direct call to it's setup script
# used to bypass package list, and other processing
#
# do not use once package list has been set up
#
# SetupHelper uninstall is deferred and handled
#	during PackageManager exit

def	directUninstall (packageName):
	global SetupHelperUninstall
	global SystemReboot
	global GuiRestart

	if packageName == "SetupHelper":
		SetupHelperUninstall = True
		return

	packageDir = "/data/" + packageName
	setupFile = packageDir + "/setup"
	try:
		if os.path.isdir (packageDir) and os.path.isfile (setupFile) \
				and os.access(setupFile, os.X_OK):
			proc = subprocess.Popen ( [ setupFile, 'uninstall', 'runFromPm' ],
						bufsize=-1, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			proc.commiunicate ()	# output ignored
			returnCode = proc.returncode
	except:
		logging.critical ("could not uninstall " + packageName)
	else:
		if returnCode == EXIT_REBOOT:
			SystemReboot = True
		elif returnCode == EXIT_RESTART_GUI:
			GuiRestart = True


# signal handler for TERM and CONT
# this is needed to allow pending operations to finish before PackageManager exits
# TERM sets RestartPackageManager which causes mainLoop to exit and therefor main to complete
# TERM, then CONT is issued by supervise when shutting down the service
# CONT handler differentiates a restart vs service down for logging purposes

def setPmRestart (signal, frame):
	global RestartPackageManager
	RestartPackageManager = True

def shutdownPmRestart (signal, frame):
	global RestartPackageManager
	global ShutdownPackageManager
	if RestartPackageManager:
		ShutdownPackageManager = True

signal.signal (signal.SIGTERM, setPmRestart)
signal.signal (signal.SIGCONT, shutdownPmRestart)


#	main
#
# ######## code begins here
# responsible for initialization and starting main loop and threads
# also deals with clean shutdown when main loop exits
#

def main():
	global mainloop
	global SystemReboot	# initialized/used in main, set in mainloop, PushAction, InstallPackage
	global GuiRestart	# initialized in main, set in PushAction, InstallPackage, used in mainloop
	global InitializePackageManager # initialized in main, set in PushAction, used in mainloop
	global RestartPackageManager # initialized in main, set in PushAction, used in mainloop
	global ShutdownPackageManager
	global SetupHelperUninstall
	global WaitForGitHubVersions  # initialized in main, set in UpdateGitHubVersion used in mainLoop
	SystemReboot = False
	GuiRestart = False
	InitializePackageManager = False
	RestartPackageManager = False
	ShutdownPackageManager = False
	SetupHelperUninstall = False

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

	logging.warning ("420 PackageManager " + installedVersion + " starting")

	from dbus.mainloop.glib import DBusGMainLoop

	# Have a mainloop, so we can send/receive asynchronous calls to and from dbus
	DBusGMainLoop(set_as_default=True)

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
		elif machine == "ekrano":
			Platform = "Ekrano GX"
		else:
			Platform = machine
		file.close()

	# initialze dbus Settings and com.victronenergy.packageManager
	global DbusIf
	DbusIf = DbusIfClass ()
	
	# populate local package information from dbus settings
	#	this creates package class instances
	PackageClass.AddPackagesFromDbus ()

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
	
	# make a pass through the package list to:
	#	update local versions and flags
	#		( this is needed anyway before mainLoop so do it here while we have the package )
	#	remove any packages if its name is not valid
	#		(invalid package names may be left over from a previous version)
	# 	remove any packages with their forced removal flag is set
	#		package conflicts are sometimes resolved by uninstalling a package
	#			(done in their setup script eg GuiMods force removes GeneratorConnector)
	#	remove duplicate packages
	# could be time-consuming (uninstall, removal and checking all packages)
	# lock is really unecessary since threads aren't running yet
	#
	# if a package is removed, start at the beginning of the list again

	while True:
		DbusIf.LOCK ("main")
		runAgain = False
		existingPackages = []
		for (index, package) in enumerate (PackageClass.PackageList):
			packageName = package.PackageName
			# valid package name
			if PackageClass.PackageNameValid (packageName):

				flagFile = "/data/setupOptions/" + packageName + "/FORCE_REMOVE" 
				# forced removal flag
				if os.path.exists (flagFile):
					os.remove (flagFile)
					if os.path.exists ("/etc/venus/installedVersion-" + packageName):
						logging.warning ( "uninstalling " + packageName + " prior to forced remove" )
						directUninstall (packageName)
					# now remove the package from list
					logging.warning ( "forced remove of " + packageName )
					PackageClass.RemovePackage (packageIndex=index)
					runAgain = True
					break
				elif packageName in existingPackages:
					logging.warning ( "removing duplicate " + packageName )
					PackageClass.RemovePackage (packageIndex=index, isDuplicate=True)
					runAgain = True
					break

			# invalid package name (including a null string) so remove the package from the list
			else:
				logging.warning ( "removing package with invalid name " + packageName )
				PackageClass.RemovePackage (packageIndex=index)
				runAgain = True
				break

			# package not removed above - add its name to list that will be checked for duplicates
			existingPackages.append (packageName)

		DbusIf.UNLOCK ("main")
		if not runAgain:
			break
	del existingPackages

	DbusIf.UpdateDefaultPackages ()

	#### start threads - must use LOCK / UNLOCK to protect access to DbusIf from here on
	UpdateGitHubVersion.start()
	DownloadGitHub.start()
	InstallPackages.start()
	AddRemove.start()
	MediaScan.start ()

	# call the main loop - every 1 second
	# this section of code loops until mainloop quits
	GLib.timeout_add(1000, mainLoop)
	mainloop = GLib.MainLoop()
	mainloop.run()


	#### this section of code runs only after the mainloop quits (LOCK / UNLOCK no longer necessary)

	# output final prompts to GUI and log
	DbusIf.DbusService['/ActionNeeded'] = ""
	DbusIf.SetEditStatus ("")
	DbusIf.AcknowledgeGuiEditAction ('')
	message = ""
	if MediaScan.AutoUninstall:
		message = "UNINSTALLING ALL PACKAGES & REBOOTING ..."
		logging.warning (">>>> UNINSTALLING ALL PACKAGES & REBOOTING...")
	elif SetupHelperUninstall:
		message = "UNINSTALLING SetupHelper ..."
		logging.critical (">>>> UNINSTALLING SetupHelper ...")
	elif InitializePackageManager:
		if SystemReboot:
			message = "initializing and REBOOTING ..."
			logging.warning (">>>> initializing PackageManager and REBOOTING SYSTEM")
		else:
			logging.warning (">>>> initializing PackageManager ...")
			message = "initializing and restarting PackageManager ..."
	elif SystemReboot:
		message = "REBOOTING SYSTEM ..."
		logging.warning (">>>> REBOOTING SYSTEM")
	elif GuiRestart:
		message = "restarting GUI and Package Manager..."
	elif ShutdownPackageManager:
		message = "shutting down PackageManager ..."
	elif RestartPackageManager:
		message = "restarting PackageManager ..."
	DbusIf.UpdateStatus ( message=message, where='PmStatus' )
	DbusIf.UpdateStatus ( message=message, where='Editor' )

	# stop threads, remove service from dbus
	logging.warning ("stopping threads")
	UpdateGitHubVersion.StopThread ()
	DownloadGitHub.StopThread ()
	InstallPackages.StopThread ()
	AddRemove.StopThread ()
	MediaScan.StopThread ()

	try:
		UpdateGitHubVersion.join (timeout=1.0)
		DownloadGitHub.join (timeout=1.0)
		InstallPackages.join (timeout=1.0)
		AddRemove.join (timeout=1.0)
		MediaScan.join (timeout=1.0)
	except:
		logging.critical ("one or more threads failed to exit")
		pass

	# if initializing PackageManager persistent storage, set PackageCount to 0
	#	which will cause the package list to be rebuilt from packages found in /data
	#	user-specified Git Hub user and branch are lost
	if InitializePackageManager:
		DbusIf.DbusSettings['packageCount'] = 0

	# com.victronenergy.packageManager no longer available after this call
	DbusIf.RemoveDbusService ()

	# auto uninstall triggered by AUTO_UNINSTALL_PACKAGES flag file on removable media
	if MediaScan.AutoUninstall:
		# uninstall all packages EXCEPT SetupHelper which is done later
		for path in os.listdir ("/data"):
			directUninstall (path)
		SystemReboot = True

	# tell supervise not to restart PackageManager when this program exits
	if SystemReboot or SetupHelperUninstall:
		logging.warning ("setting PackageManager to not restart")
		try:
			proc = subprocess.Popen ( [ 'svc', '-o', '/service/PackageManager' ] )
		except:
			logging.critical ("svc command failed")

	# remaining tasks are handled in packageManagerEnd.sh because
	#	SetupHelper uninstall needs to be done after PackageManager.py exists
	#	and the reboot/GUI restart (if any) needs to be done after that.
	if SystemReboot or SetupHelperUninstall or GuiRestart:
		command = [ '/data/SetupHelper/packageManagerEnd.sh' ]
		if SetupHelperUninstall:
			command.append ("shUninstall")
		if SystemReboot:
			command.append ("reboot")
		elif GuiRestart:
			command.append ("guiRestart")

		# this runs in the background and will CONTINUE after PackageManager.py exits below
		try:
			logging.warning ("finishing up in packageManagerEnd.sh")
			proc = subprocess.Popen ( command )
		except:
			logging.critical ("packageManagerEnd.sh failed")

	logging.warning (">>>> PackageManager exiting")

# Always run our main loop so we can process updates
main()





