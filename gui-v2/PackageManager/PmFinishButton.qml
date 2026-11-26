//////// PackageManager gui-v2 plugin
// list item that finishes an install or uninstall with a reboot or GUI restart
// shown when PackageManager reports /ActionNeeded, and while the reboot or restart is pending

import QtQuick
import Victron.GuiPlugins

PluginListButton {
	id: root

	property PmService service

	readonly property bool restarting: service.editAction === "reboot" || service.editAction === "restartGui"

	text:
	{
		if (service.editAction === "reboot")
			return "REBOOTING ..."
		else if (service.editAction === "restartGui")
			return "Restarting GUI ..."
		else
			return "Action to finish install/uninstall"
	}
	caption: restarting ? "" : service.actionNeeded
	secondaryText: service.rebootNeeded ? "Reboot" : "Restart GUI"
	preferredVisible: restarting || service.rebootNeeded || service.guiRestartNeeded
	interactive: service.idle
	onClicked: confirmDialog.open ()

	PluginConfirmationDialog {
		id: confirmDialog

		title: root.service.rebootNeeded ? "Reboot now?" : "Restart the GUI now?"
		description: root.service.actionNeeded
		acceptText: root.service.rebootNeeded ? "Reboot" : "Restart GUI"
		onAccepted:
		{
			if (root.service.rebootNeeded)
				root.service.send ("reboot")
			else if (root.service.guiRestartNeeded)
				root.service.send ("restartGui")
		}
	}
}
