/////// new menu for package version display

import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: showControls ? qsTr("Package manager") : qsTr("Package manager not running")
    property string settingsPrefix: "com.victronenergy.settings/Settings/PackageManager"
    property string servicePrefix: "com.victronenergy.packageManager"
	property string bindVrmloggerPrefix: "com.victronenergy.logger"
    VBusItem { id: pmStatusItem; bind: Utils.path(servicePrefix, "/PmStatus") }
	property string pmStatus: pmStatusItem.valid ? pmStatusItem.value : ""
    VBusItem { id: mediaStatus; bind: Utils.path(servicePrefix, "/MediaUpdateStatus") }
    VBusItem { id: actionNeeded; bind: Utils.path(servicePrefix, "/ActionNeeded") }
    VBusItem { id: editAction; bind: Utils.path(servicePrefix, "/GuiEditAction") }
    property bool showMediaStatus: mediaStatus.valid && mediaStatus.value != ""
    property bool showControls: pmStatusItem.valid

	// the last status message received from PackageManager is saved in lastStatus
	//	so there is some status to display when PackageManager quits
	property string lastStatus: ""

	onPmStatusChanged:
	{
		if (pmStatusItem.valid)
			lastStatus = pmStatus
	}

	model: VisibleItemModel
    {
        MbItemText
        {
			id: status
            text:
            {
				if (mediaStatus.valid && mediaStatus.value != "")
					return mediaStatus.value
				else if (showControls)
					return pmStatus
				else
					return lastStatus
			}
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
        MbItemOptions
        {
            id: autoDownload
            description: qsTr ("GitHub check frequency")
            bind: Utils.path (settingsPrefix, "/GitHubAutoDownload")
            possibleValues:
            [
				MbOption { description: "Once"; value: 99 },
				MbOption { description: "Every 10 minutes"; value: 1 },
				MbOption { description: "Hourly"; value: 2 },
				MbOption { description: "Daily"; value: 3 },
                MbOption { description: "Never"; value: 0 }
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
				else if (actionNeeded.value.indexOf ( "REBOOT" ) != -1 )
					return qsTr ("Reboot")
				else if (actionNeeded.value.indexOf ( "restart" ) != -1 )
					return qsTr ("Restart GUI")
				else
					return ""
			}
			onClicked:
            {
				if (finishButton.value == 'REBOOT')
				{
					// needs immediate update because GUI will be going down ASAP
					finishButton.description = qsTr ("REBOOTING ...")
					editAction.setValue ( 'reboot' )
				}
				else if (finishButton.value == 'guiRestart')
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
		MbOK {
			property int notMounted: 0
			property int mounted: 1
			property int unmountRequested: 2
			property int unmountBusy: 3

			function mountStateToText(s)
			{
				switch (s) {
				case mounted:
					return qsTr("Press to eject");
				case unmountRequested:
				case unmountBusy:
					return qsTr("Ejecting, please wait");
				default:
					return qsTr("No storage found");
				}
			}

			VBusItem {
				id: vMountState
				bind: Utils.path(bindVrmloggerPrefix, "/Storage/MountState")
			}
			description: qsTr("microSD / USB")
			value: mountStateToText(vMountState.value)
			writeAccessLevel: User.AccessUser
			onClicked: vMountState.setValue(unmountRequested);
			editable: vMountState.value === mounted
			cornerMark: false
		}
		MbSubMenu
        {
            description: qsTr("Restart or initialize ...")
            subpage: Component { PageSettingsPmInitialize {} }
            show: showControls
        }
    }
}
