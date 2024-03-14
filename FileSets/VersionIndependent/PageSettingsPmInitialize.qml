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
	property string initializeMessage: ""

	onPmRunningChanged: { showInProgress = false }

    function sendCommand (command, message)
    {
		initializeMessage = message
		showInProgress = true
		editAction.setValue (command)
    }

	model: VisibleItemModel
    {
		MbOK
		{
			description: qsTr("Restart")
			value: qsTr("Press to restart Package Manager")
			onClicked:sendCommand ("RESTART_PM", qsTr ("restarting Package Manager ..."))
			writeAccessLevel: User.AccessInstaller
			show: ! showInProgress
		}
		MbOK
		{
			description: qsTr("Restart GUI")
			value: qsTr("Press to restart GUI")
			onClicked:sendCommand ("restartGui", qsTr ("restarting GUI ..."))
			writeAccessLevel: User.AccessInstaller
			show: ! showInProgress
		}
        MbItemText
        {
			id: info
            text: qsTr ("Initializing PackageManager will\nreset persistent storage to an empty state\nGit Hub user and branch are reset to defaults\nPackages added manually must be added again")
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
			show: ! showInProgress
        }
		MbOK
		{
			description: qsTr("Initialize")
			value: qsTr("Press to INITIALIZE Package Manager")
			onClicked: sendCommand ("INITIALIZE_PM", qsTr ("INITIALIZING Package Manager ..."))
            writeAccessLevel: User.AccessInstaller
            show: ! showInProgress
		}
        MbItemText
        {
			id: initializingMessage
            text: initializeMessage
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            show: showInProgress
        }
    }
}
