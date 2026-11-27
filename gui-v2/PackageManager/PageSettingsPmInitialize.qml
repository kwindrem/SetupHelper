//////// PackageManager gui-v2 plugin
// restart PackageManager or the GUI, or initialize PackageManager
// gui-v2 version of PageSettingsPmInitialize.qml

import QtQuick
import Victron.GuiPlugins

PluginPage {
	id: root

	title: pm.running ? "PackageManager restart/initialize" : "Package manager not running"

	property bool showInProgress: false
	property string inProgressMessage: ""

	PmService {
		id: pm

		// PackageManager stops and starts again: hide the message
		onRunningChanged: root.showInProgress = false
	}

	// these commands are sent even if PackageManager is busy, as in the GUI v1 menu
	function sendCommand (command, message)
	{
		inProgressMessage = message
		showInProgress = true
		pm.editActionItem.setValue (command)
	}

	PluginConfirmationDialog {
		id: initializeDialog

		title: "Initialize PackageManager?"
		description: "Persistent storage is reset to an empty state. GitHub user and branch are reset to defaults. Packages added manually must be added again."
		acceptText: "Initialize"
		onAccepted: root.sendCommand ("INITIALIZE_PM", "INITIALIZING Package Manager ...")
	}

	PluginItemListView {
		PluginListButton {
			text: "Restart Package Manager"
			secondaryText: "Restart"
			preferredVisible: ! root.showInProgress
			onClicked: root.sendCommand ("RESTART_PM", "restarting Package Manager ...")
		}

		PluginListButton {
			text: "Restart GUI"
			secondaryText: "Restart"
			preferredVisible: ! root.showInProgress
			onClicked: root.sendCommand ("restartGui", "restarting GUI ...")
		}

		PluginPrimaryListLabel {
			text: "Initializing PackageManager will reset persistent storage to an empty state. GitHub user and branch are reset to defaults. Packages added manually must be added again."
			preferredVisible: ! root.showInProgress
		}

		PluginListButton {
			text: "Initialize Package Manager"
			secondaryText: "Initialize"
			preferredVisible: ! root.showInProgress
			onClicked: initializeDialog.open ()
		}

		PluginPrimaryListLabel {
			text: root.inProgressMessage
			preferredVisible: root.showInProgress
		}
	}
}
