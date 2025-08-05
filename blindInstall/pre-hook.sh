#!/bin/bash

# this script is part of a "blind install" archive which installs SetupHelper
# refer to blindInstall.sh for more an explaination
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
		logMessage "ERROR: no blind version"
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
	logMessage "completed - will do install"
	exit 0
# returning non-zero will prevent unpacking
# there won't be an archive to unpack andpost-hook.sh will NOT run 
else
	logMessage "completed - unstall not needed - skipping unpack and install"
	exit -1
fi
