/////// new menu for PackageManager initialize

import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: pmRunning ? qsTr("PackageManager restart/initialize") : qsTr ("Package manager not running")
    property string settingsPrefix: "com.victronenergy.settings/Settings/PackageManager"
	VBusItem { id: pmStatus; bind: Utils.path(servicePrefix, "/PmStatus") }
	property bool pmRunning: pmStatus.valid

	property bool showInProgress: false
	property bool initialize: false

	onPmRunningChanged: { showInProgress = false }

    function sendCommand (command)
    {
			// provide local confirmation of action - takes PackageManager too long
            editAction.setValue (command)
			showInProgress = true
			if (command == "INITIALIZE")
				initialize = true
			else
				initialize = false
    }

	model: VisibleItemModel
    {
		MbOK
		{
			description: qsTr("Restart")
			value: qsTr("Press to Restart")
			onClicked: sendCommand ("RESTART_PM")
			writeAccessLevel: User.AccessInstaller
			show: ! showInProgress
		}
        MbItemText
        {
			id: info
            text: qsTr ("Initializing PackageManager will reset persistent storage\nto an empty state\nGit Hub user and branch info is lost")
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
		MbOK
		{
			description: qsTr("Initialize")
			value: qsTr("Press to Initialize")
			onClicked: sendCommand ("INITIALIZE_PM")
            writeAccessLevel: User.AccessInstaller
            show: ! showInProgress
		}
        MbItemText
        {
			id: initializingMessage
            text: initialize ? qsTr ("... initializing and restarting") : qsTr  ("... restarting")
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            show: showInProgress
        }
    }
}
