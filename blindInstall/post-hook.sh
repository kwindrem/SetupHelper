#!/bin/bash

# this script is part of a "blind install" archive which installs SetupHelper
#	without user interaction. Simply inserting media into the GX device
#	and rebooting once or twice (see below) will install SetupHelper
#
# the process makes use of the Venus OS update-data.sh script run during system boot
# archives named "venus-data.tgz" are unpacked during boot
# overriting matching content in /data
#
# this archive unpacks to:
#	/data/SetupHelper-blind to avoid overwriting an existing copy of SetupHelper
#	/data/rc for the pre/post scripts (not used prior to v2.90)
#	/data/rcS.local (used prior to v2.90)
#		(overwrites any current file - restored as of v2.90 but not before!)
# if versions of /data/SetupHelper-blind and the installed version of SetupHelper
#	DIFFER, OR if SetupHelper is NOT INSTALLED,
#	SetupHelper-blind replaces SetupHelper and the setup script is run
#
# prior to v2.90:
# 	the first reboot, unpacks the archive replacing the itmes listed above
#	Venus must be rebooted a second time
#	The second reboot:
#		runs /data/rcS.local included in the archive
#		rcS.local compares versions then runs blindInstall.sh if appropriate
#
# starting with v2.90:
#	pre-hook.sh and post-hook.sh scripts are run before and after the archive is unpacked
# 	/data/rcS.local is saved in pre-hook.sh and restored in post-hook.sh.
# 	The /data/rcS.local file included in the archive is never executed
# 	In stead, post-hook.sh performs the version checks and calls blindInstall.sh
#		if appropriate. This eliminates the second reboot !
#	In order to check versions prior to unpacking the archive,
#		the SetupHelper version is duplicated in the rc folder which unpacks to /data
#		BEFORE the SetupHelper-blind is unpacked.
#
# a call to /data/SetupHelper/reinstallMods is appended to rcS.local by all setup scripts
#	using SetupHelper CommonResources.
# That call is included in the blind install rcS.local so that if the media is left inserted
#	subsequent reboots will still check for reinstalls (applies only to firmwire before v2.90)
#
# the rcS.local from the blindInstall is removed/restored at the end of blindInstall.sh
#	SetupHelper/setup creates a new one or appends to the original rcS.local
#
# blindInstall.sh is run in the background so it can wait for dbus Settings resources
# to become available before running the package install script.
#

logDir="/var/log/PackageManager"
logFile="$logDir/current"
if ! [ "$logDir" ]; then
	mkdir -P "$logDir"
fi
logMessage ()
{
	echo "$*"
	echo "blind install post-hook.sh: $*" | tai64n >> "$logFile"
}


logMessage "starting"

# run the blind install script from the SetupHelper-blind
script="/data/SetupHelper-blind/blindInstall/blindInstall.sh"
if [ -f "$script" ]; then
	logMessage "running blindInstall.sh"
    nohup "$script" > /dev/null &
fi

logMessage "completed"
