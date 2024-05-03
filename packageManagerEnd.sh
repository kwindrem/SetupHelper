#!/bin/bash

#
# this script handles the actions AFTER PackageManager.py exits
#	that can not be easily performed while it is running:
#
#	uninstalling SetupHelper and therefore the PackageManager service
#
#	system reboots are also handled here since that needs to happen
#	AFTER SetupHelper is uninstalled
#
#	GUI restart if needed
# 
# this script is called from PackageManager.py just prior to it exiting
#
# PackageManager will pass the following options as appropriate:
#
#	'shUninstall'	to uninstall SetupHelper
#	'reboot'		to trigger a system reboot
#	'guiRestart'	to trigger a GUI restart
#
#	all are optional but at least one should be passed or
#	this script will exit without doing anything
#
#	reboot overrides a guiRestart since the reboot will restart the GUI

logFile=/data/log/PackageManager/current
logMessage ()
{
     # to setup helper log
    if [ ! -z $logFile ]; then
        if [ -f "$logFile" ]; then
			echo "pmEnd: $*" | tai64n >> $logFile
        fi
    fi
}

# copied from Essential Resources
EXIT_SUCCESS=0
EXIT_REBOOT=123
EXIT_RESTART_GUI=124

logMessage "starting packageManagerEnd.sh"

shUninstall=false
guiRestart=false
reboot=false

while [ $# -gt 0 ]; do
	case $1 in
		"shUninstall")
			shUninstall=true
			;;
		"guiRestart")
			guiRestart=true
			;;
		"reboot")
			reboot=true
			;;
		*)
	esac
    shift
done

# allow PackageManager exit before doing anything
if $shUninstall || $reboot ; then
	service="/service/PackageManager"
	# insure the PackageManager service doesn't restart when it exits
	#	it will start up again after the reboot if it is still installed
	#	only issue svc -o if PM is running or it will be started !!!
	if [ $(svstat "$service" | awk '{print $2}') == "up" ]; then
		svc -o "$service"
	fi
	while true; do
		if [ -z "$( pgrep -f PackageManager.py )" ]; then
			break
		else
			logMessage "waiting for PackageManager.py to exit"
			sleep 5
		fi
	done
fi

if $shUninstall ; then
	logMessage ">>>> uninstalling SetupHelper !!"
	setupFile="/data/SetupHelper/setup"
	if [ -f "$setupFile" ]; then
		$setupFile uninstall runFromPm
		returnCode=$( echo $? )
	else
		returnCode=$EXIT_SUCCESS
	fi
	if (( returnCode == $EXIT_REBOOT )); then
		reboot=true
	elif (( returnCode == $EXIT_RESTART_GUI )); then
		guiRestart=true
	fi
fi

if $reboot ; then
	logMessage ">>>> REBOOTING ..."
	# TODO: add -k for debugging - outputs message but doesn't reboot
	shutdown -r now "PackageManager is REBOOTING SYSTEM ..."
elif $guiRestart ; then
	if $shUninstall ; then
		logMessage ">>>> restarting GUI"
	else
		logMessage ">>>> restarting GUI and Package Manager"
	fi
	if [ -e "/service/start-gui" ]; then
		svc -t "/service/start-gui"
	elif [ -e "/service/gui" ]; then
		svc -t "/service/gui"
	fi
fi

logMessage "end packageManagerEnd.sh"
