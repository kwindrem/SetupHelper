/////// new menu for package version display

import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: qsTr("Package Manager")
    property string settingsPrefix: "com.victronenergy.settings/Settings/PackageMonitor"
    property string servicePrefix: "com.victronenergy.packageMonitor"
    VBusItem { id: downloadStatus; bind: Utils.path(servicePrefix, "/GitHubUpdateStatus") }
    VBusItem { id: installStatus; bind: Utils.path(servicePrefix, "/InstallStatus") }
    property bool showInstallStatus: installStatus.valid && installStatus.value != ""
    VBusItem { id: mediaStatus; bind: Utils.path(servicePrefix, "/MediaUpdateStatus") }
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
					return"Package Manager not running"
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
            description: qsTr("Package Editor")
            subpage: Component { PageSettingsPackageEdit {} }
            show: showControls
        }
        MbSubMenu
        {
            description: qsTr("Package Version List")
            subpage: Component { PageSettingsPackageVersions {} }
            show: showControls
        }
    }
}
