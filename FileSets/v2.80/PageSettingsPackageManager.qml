/////// new menu for package version display

import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: qsTr("Package manager")
    property string settingsPrefix: "com.victronenergy.settings/Settings/PackageManager"
    property string servicePrefix: "com.victronenergy.packageManager"
    VBusItem { id: downloadStatus; bind: Utils.path(servicePrefix, "/GitHubUpdateStatus") }
    VBusItem { id: installStatus; bind: Utils.path(servicePrefix, "/InstallStatus") }
    VBusItem { id: mediaStatus; bind: Utils.path(servicePrefix, "/MediaUpdateStatus") }
    VBusItem { id: actionNeeded; bind: Utils.path(servicePrefix, "/ActionNeeded") }
    VBusItem { id: editAction; bind: Utils.path(servicePrefix, "/GuiEditAction") }
    property bool showInstallStatus: installStatus.valid && installStatus.value != ""
    property bool showMediaStatus: mediaStatus.valid && mediaStatus.value != ""
    property bool showControls: installStatus.valid

	model: VisualItemModel
    {
        MbItemText
        {
			id: status
            text:
            {
				if (! showControls)
					return"Package manager not running"
				else if (installStatus.valid && installStatus.value != "")
					return installStatus.value
				else if (mediaStatus.valid && mediaStatus.value != "")
					return mediaStatus.value
				else if (downloadStatus.valid && downloadStatus.value != "")
					return downloadStatus.value
				else
					return "idle"
			}
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
        MbItemOptions
        {
            id: autoDownload
            description: qsTr ("Automatic GitHub downloads")
            bind: Utils.path (settingsPrefix, "/GitHubAutoDownload")
            possibleValues:
            [
                MbOption { description: "Normal"; value: 1 },
                MbOption { description: "Fast, then Normal"; value: 2 },
                MbOption { description: "Once (Fast)"; value: 3 },
                MbOption { description: "Off"; value: 0 }
            ]
            writeAccessLevel: User.AccessInstaller
        }
        MbSwitch
        {
            id: autoInstall
            bind: Utils.path (settingsPrefix, "/AutoInstall")
            name: qsTr ("Auto install packages")
            writeAccessLevel: User.AccessInstaller
        }
        MbSubMenu
        {
            description: qsTr("Active packages")
            subpage: Component { PageSettingsPackageVersions {} }
            show: showControls
        }
		MbSubMenu
        {
            description: qsTr("Inactive packages")
            subpage: Component { PageSettingsAddPackageList {} }
            show: showControls
        }
        MbOK
        {
            id: finishButton
            description:
            {
				if (editAction.value == 'reboot')
					return qsTr ("REBOOTING ...")
				else if (editAction.value == 'guiRestart')
					return qsTr ("restarting GUI ...")
				else
					return qsTr ("action to finish install/uninstall")
			}
            value:
             {
				if (! actionNeeded.valid)
					return ""
				else if (actionNeeded.value == 'reboot')
					return qsTr ("Reboot")
				else if (actionNeeded.value == 'guiRestart')
					return qsTr ("Restart GUI")
				else
					return ""
			}
			onClicked:
            {
				if (actionNeeded.value == 'reboot')
				{
					// needs immediate update because GUI will be going down ASAP
					finishButton.description = qsTr ("REBOOTING ...")
					editAction.setValue ( 'reboot' )
				}
				else if (actionNeeded.value == 'guiRestart')
				{
					// needs immediate update because GUI will be going down ASAP
					finishButton.description = qsTr ("restarting GUI ...")
					editAction.setValue ( 'restartGui' )
				}
			}
            show: actionNeeded.valid && actionNeeded.value != ''
            writeAccessLevel: User.AccessInstaller
        }
		MbSubMenu
        {
            description: qsTr("Backup & restore settings")
            subpage: Component { PageSettingsPmBackup {} }
            show: showControls
        }
		MbMountState {
			description: qsTr("microSD / USB")
		}
		MbSubMenu
        {
            description: qsTr("Initialize PackageManager ...")
            subpage: Component { PageSettingsPmInitialize {} }
            show: showControls
        }
    }
}
