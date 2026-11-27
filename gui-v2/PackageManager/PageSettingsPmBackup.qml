//////// PackageManager gui-v2 plugin
// settings backup and restore
// gui-v2 version of PageSettingsPmBackup.qml
//
// /BackupProgress: the GUI writes 1 (backup to media), 2 (restore from media),
//	21 (backup to /data) or 22 (restore from /data)
//	PackageManager shows 3, 4, 23 or 24 while it works and sets 0 when done

import QtQuick
import Victron.GuiPlugins

PluginPage {
	id: root

	title: "Settings backup & restore"

	PmService {
		id: pm
	}

	PluginDataItem {
		id: mediaAvailable
		serviceType: "packageManager"
		path: "/BackupMediaAvailable"
	}
	PluginDataItem {
		id: settingsFileExists
		serviceType: "packageManager"
		path: "/BackupSettingsFileExist"
	}
	PluginDataItem {
		id: settingsLocalFileExists
		serviceType: "packageManager"
		path: "/BackupSettingsLocalFileExist"
	}
	PluginDataItem {
		id: backupProgressItem
		serviceType: "packageManager"
		path: "/BackupProgress"
	}

	readonly property int backupProgress: backupProgressItem.valid ? backupProgressItem.value : 0
	readonly property bool idle: pm.running && backupProgressItem.valid && backupProgress === 0
	readonly property bool mediaFound: mediaAvailable.valid && mediaAvailable.value == 1

	// the restore waiting for confirmation in restoreDialog
	property int pendingRestore: 0

	PluginConfirmationDialog {
		id: restoreDialog

		title: root.pendingRestore === 22 ? "Restore settings from local storage?" : "Restore settings and logos?"
		description: "Current settings are replaced by the ones in the backup."
		acceptText: "Restore"
		onAccepted: backupProgressItem.setValue (root.pendingRestore)
	}

	PluginItemListView {
		PluginPrimaryListLabel {
			text: "Backup and restore SOME system settings, logs and logos.\nThis is NOT the Victron mechanism.\nCurrently under development."
		}

		PluginPrimaryListLabel {
			text:
			{
				if (root.backupProgress === 21 || root.backupProgress === 23)
					return "backing up settings to local storage ... (may take a while)"
				else if (root.backupProgress === 22 || root.backupProgress === 24)
					return "restoring settings from local storage ... (may take a while)"
				else if (root.backupProgress === 1 || root.backupProgress === 3)
					return "backing up settings ... (may take a while)"
				else if (root.backupProgress === 2 || root.backupProgress === 4)
					return "restoring settings ... (may take a while)"
				else if (! root.mediaFound)
					return "No USB or SD media found - insert one to continue"
				else if (settingsFileExists.valid && settingsFileExists.value == 1)
					return "Settings backup file found"
				else
					return ""
			}
			preferredVisible: text !== ""
		}

		PluginListButton {
			text: "Backup settings, logos, logs"
			secondaryText: "Backup"
			preferredVisible: root.idle && root.mediaFound
			onClicked: backupProgressItem.setValue (1)
		}

		PluginListButton {
			text: "Restore settings, logos"
			secondaryText: "Restore"
			preferredVisible: root.idle && settingsFileExists.valid && settingsFileExists.value == 1
			onClicked:
			{
				root.pendingRestore = 2
				restoreDialog.open ()
			}
		}

		PluginListButton {
			text: "Backup settings to local storage"
			secondaryText: "Backup"
			preferredVisible: root.idle
			onClicked: backupProgressItem.setValue (21)
		}

		PluginListButton {
			text: "Restore settings from local storage"
			secondaryText: "Restore"
			preferredVisible: root.idle && settingsLocalFileExists.valid && settingsLocalFileExists.value == 1
			onClicked:
			{
				root.pendingRestore = 22
				restoreDialog.open ()
			}
		}
	}
}
