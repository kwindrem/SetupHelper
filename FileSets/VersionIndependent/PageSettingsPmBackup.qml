/////// new menu for settings backup and restore

import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: qsTr("Settings backup & restore")
    property string settingsPrefix: "com.victronenergy.settings/Settings/PackageManager"
    property string servicePrefix: "com.victronenergy.packageManager"
	VBusItem { id: mediaAvailable; bind: Utils.path(servicePrefix, "/BackupMediaAvailable") }
	VBusItem { id: settingsFileExists; bind: Utils.path(servicePrefix, "/BackupSettingsFileExist") }
	VBusItem { id: settingsLocalFileExists; bind: Utils.path(servicePrefix, "/BackupSettingsLocalFileExist") }
	VBusItem { id: backupProgressItem; bind: Utils.path(servicePrefix, "/BackupProgress") }
	property int backupProgress: backupProgressItem.valid ? backupProgressItem.value : 0

	model: VisibleItemModel
    {
        MbItemText
        {
			id: info
            text: qsTr ("Backup and restore\nSOME system settings, logs and logos\nthis is NOT the Victron mechanism\ncurrently under development")
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
        MbItemText
        {
			id: status
            text:
			{
				if (backupProgress == 21 || backupProgress == 23)
					return qsTr ("backing up settings to local storage ... (may take a while)")
				else if (backupProgress == 22 || backupProgress == 24)
					return qsTr ("restoring settings from local storage ... (may take a while)")
				else if (backupProgress == 1 || backupProgress == 3)
					return qsTr ("backing up settings ... (may take a while)")
				else if (backupProgress == 2 || backupProgress == 4)
					return qsTr ("restoring settings ... (may take a while)")
				else if ( ! mediaAvailable.valid || mediaAvailable.value == 0)
					return qsTr ("No USB or SD media found - insert one to continue")
				else if (settingsFileExists.valid && settingsFileExists.value == 1)
					return qsTr ("Settings backup file found")
				else
					return ""
			}
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
		MbOK
		{
			description: qsTr("Backup settings, logos, logs")
			value: qsTr("Press to backup")
			onClicked: backupProgressItem.setValue (1)
			show: mediaAvailable.valid && mediaAvailable.value == 1 && backupProgressItem.value == 0
            writeAccessLevel: User.AccessInstaller
		}
		MbOK
		{
			description: qsTr("Restore settings, logos")
			value: qsTr("Press to restore")
			onClicked: backupProgressItem.setValue (2)
			show: settingsFileExists.valid && settingsFileExists.value == 1 && backupProgressItem.value == 0
            writeAccessLevel: User.AccessInstaller
		}
		MbOK
		{
			description: qsTr("Backup settings to local storage")
			value: qsTr("Press to backup")
			onClicked: backupProgressItem.setValue (21)
			show: backupProgressItem.value == 0
            writeAccessLevel: User.AccessInstaller
		}
		MbOK
		{
			description: qsTr("Restore settings to from storage")
			value: qsTr("Press to restore")
			onClicked: backupProgressItem.setValue (22)
			show: settingsLocalFileExists.valid && settingsLocalFileExists.value == 1 && backupProgressItem.value == 0
            writeAccessLevel: User.AccessInstaller
		}
    }
}
