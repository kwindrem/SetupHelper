//////// PackageManager gui-v2 plugin
// main menu: Settings > Integrations > UI Plugins > PackageManager
// gui-v2 version of FileSets/VersionIndependent/PageSettingsPackageManager.qml

import QtQuick
import Victron.GuiPlugins

PluginPage {
	id: root

	title: pm.running ? "Package manager" : "Package manager not running"

	// the last status message received from PackageManager is saved in lastStatus
	//	so there is some status to display when PackageManager quits
	property string lastStatus: ""

	PmService {
		id: pm

		onPmStatusChanged:
		{
			if (pm.running)
				root.lastStatus = pm.pmStatus
		}
	}

	PluginDataItem {
		id: mediaStatus
		serviceType: "packageManager"
		path: "/MediaUpdateStatus"
	}

	PluginDataItem {
		id: mountState
		serviceType: "logger"
		path: "/Storage/MountState"
	}

	function mountStateToText (state)
	{
		switch (state)
		{
		case 1:
			return "Press to eject"
		case 2:
		case 3:
			return "Ejecting, please wait"
		default:
			return "No storage found"
		}
	}

	PluginItemListView {
		PluginPrimaryListLabel {
			text:
			{
				var media = pm.stringValue (mediaStatus)
				if (media !== "")
					return media
				else if (pm.running)
					return pm.pmStatus
				else
					return root.lastStatus
			}
			preferredVisible: text !== ""
		}

		PluginListRadioButtonGroup {
			text: "GitHub check frequency"
			dataItem.serviceType: "settings"
			dataItem.path: pm.settingsPath + "/GitHubAutoDownload"
			optionModel: [
				{ display: "Once", value: 99 },
				{ display: "Every 10 minutes", value: 1 },
				{ display: "Hourly", value: 2 },
				{ display: "Daily", value: 3 },
				{ display: "Never", value: 0 }
			]
			writeAccessLevel: PluginAccessLevel.Installer
		}

		PluginListSwitch {
			text: "Auto install packages"
			dataItem.serviceType: "settings"
			dataItem.path: pm.settingsPath + "/AutoInstall"
			writeAccessLevel: PluginAccessLevel.Installer
		}

		PluginListNavigation {
			text: "Active packages"
			pageUrl: Qt.resolvedUrl ("PageSettingsPackageVersions.qml")
			preferredVisible: pm.running
		}

		PluginListNavigation {
			text: "Inactive packages"
			pageUrl: Qt.resolvedUrl ("PageSettingsAddPackageList.qml")
			preferredVisible: pm.running
		}

		PmFinishButton {
			service: pm
		}

		PluginListNavigation {
			text: "Backup & restore settings"
			pageUrl: Qt.resolvedUrl ("PageSettingsPmBackup.qml")
			preferredVisible: pm.running
		}

		PluginListButton {
			text: "microSD / USB"
			secondaryText: root.mountStateToText (mountState.value)
			writeAccessLevel: PluginAccessLevel.User
			interactive: mountState.value === 1
			onClicked: mountState.setValue (2)
		}

		PluginListNavigation {
			text: "Restart or initialize ..."
			pageUrl: Qt.resolvedUrl ("PageSettingsPmInitialize.qml")
			preferredVisible: pm.running
		}
	}
}
