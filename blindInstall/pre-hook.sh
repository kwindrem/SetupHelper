#!/bin/bash
#
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
	echo "blind install pre-hook.sh: $*" | tai64n >> "$logFile"
}


logMessage "starting"

scriptDir="$( cd "$(dirname $0)" >/dev/null 2>&1 ; /bin/pwd -P )"
blindVersionFile="$scriptDir/SetupHelperVersion"
installedVersionFile='/etc/venus/installedVersion-SetupHelper'
setupHelperStored='/data/SetupHelper'

# remove GitHub project data just in case it ends up on the target
#	(it's large (about 20 MB) and could get in the way of package replacement
rm -rf $setupHelperStored/.git

doInstall=false
# SetupHelper is currently stored in /data
# check to see if it needs to be updated
if [ -d "$setupHelperStored" ]; then
	if [ -f "$blindVersionFile" ]; then
		blindVersion=$(cat "$blindVersionFile")
	else
		logMessage "Error: no blind version"
		blindVersion=""
	fi
	if [ -f "$installedVersionFile" ]; then
		installedVersion=$(cat "$installedVersionFile")
	else
		installedVersion=""
	fi

	if [ "$installedVersion" != "$blindVersion" ]; then
		doInstall=true
	fi
# no SetupHelper found, skip version checks and install
else
	doInstall=true
fi
# returning with 0 will trigger unpacking and run post-hook.sh
if $doInstall ; then
	# back up /data/rcS.local for restoration in post.sh
	rm -rf /data/rcS.local.orig
	if [ -r /data/rcS.local ] ; then
		logMessage "backing up rcS.local"
		cp /data/rcS.local /data/rcS.local.orig
	fi
	logMessage "completed - will do install"
	exit 0
# returning non-zero will prevent unpacking
# there won't be an archive to unpack andpost-hook.sh will NOT run 
else
	logMessage "completed - skipping unpack and install"
	exit -1
fi
