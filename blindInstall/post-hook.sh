#!/bin/bash

# this script is part of a "blind install" archive which installs SetupHelper
#
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
	echo "blind install post-hook.sh: $*" | tai64n >> "$logFile"
}


logMessage "starting"

# run the blind install script from the SetupHelper-blind
script="/data/SetupHelper-blind/blindInstall/blindInstall.sh"
if [ -f "$script" ]; then
	logMessage "running blindInstall.sh as background process"
    nohup "$script" > /dev/null &
fi

logMessage "completed"
