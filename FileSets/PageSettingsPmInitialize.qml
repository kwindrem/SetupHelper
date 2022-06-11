/////// new menu for PackageManager initialize

import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: pmRunning ? qsTr("Intialize Package Manager") : qsTr ("Package manager not running")
    property string settingsPrefix: "com.victronenergy.settings/Settings/PackageManager"
	property bool pmRunning: installStatus.valid

    property VBusItem editAction: VBusItem { bind: Utils.path(servicePrefix, "/GuiEditAction") }
    VBusItem { id: installStatus; bind: Utils.path(servicePrefix, "/InstallStatus") }
	property bool showInProgress: false

	onPmRunningChanged: { showInProgress = false }

    function sendInitialize ()
    {
			// provide local confirmation of action - takes PackageManager too long
            editAction.setValue ("INITIALIZE")
			showInProgress = true
    }

	model: VisualItemModel
    {
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
			onClicked: sendInitialize ()
            writeAccessLevel: User.AccessInstaller
            visible: ! showInProgress
		}
        MbItemText
        {
			id: initializingMessage
            text: qsTr ("... initializing and restarting")
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            visible: showInProgress
        }
    }
}
