pragma ComponentBehavior: Bound

//////// PackageManager gui-v2 plugin
// list of active packages (tap to edit)
// gui-v2 version of PageSettingsPackageVersions.qml and MbDisplayPackageVersion.qml

import QtQuick
import Victron.GuiPlugins

PluginPage {
	id: root

	title: pm.running ? "Active packages" : "Package manager not running"

	PmService {
		id: pm

		// the GitHub version request needs PackageManager to be idle
		// (sent later, not while /GuiEditAction is still reporting its change)
		onIdleChanged: Qt.callLater (root.refreshGitHubVersions)
	}

	PluginDataItem {
		id: packageCount
		serviceType: "settings"
		path: pm.settingsPath + "/Count"
	}

	PluginDataItem {
		id: platform
		serviceType: "packageManager"
		path: "/Platform"
	}

	// notify PackageManager to refresh GitHub versions for all packages
	// once, when this menu is opened
	property bool gitHubScanSent: false

	function refreshGitHubVersions ()
	{
		if (! gitHubScanSent && pm.idle)
		{
			gitHubScanSent = true
			pm.send ("gitHubScan:ALL")
		}
	}

	Component.onCompleted: refreshGitHubVersions ()

	PluginModelListView {
		model: pm.running && packageCount.valid ? packageCount.value : 0

		delegate: PluginListNavigation {
			id: packageItem

			required property int index

			readonly property string servicePrefix: "/Package/" + index + "/"

			readonly property PluginDataItem nameItem: PluginDataItem {
				serviceType: "settings"
				path: pm.settingsPath + "/" + packageItem.index + "/PackageName"
			}
			readonly property PluginDataItem installedVersionItem: PluginDataItem {
				serviceType: "packageManager"
				path: packageItem.servicePrefix + "InstalledVersion"
			}
			readonly property PluginDataItem gitHubVersionItem: PluginDataItem {
				serviceType: "packageManager"
				path: packageItem.servicePrefix + "GitHubVersion"
			}
			readonly property PluginDataItem packageVersionItem: PluginDataItem {
				serviceType: "packageManager"
				path: packageItem.servicePrefix + "PackageVersion"
			}
			readonly property PluginDataItem incompatibleItem: PluginDataItem {
				serviceType: "packageManager"
				path: packageItem.servicePrefix + "Incompatible"
			}
			readonly property PluginDataItem rebootNeededItem: PluginDataItem {
				serviceType: "packageManager"
				path: packageItem.servicePrefix + "RebootNeeded"
			}
			readonly property PluginDataItem guiRestartNeededItem: PluginDataItem {
				serviceType: "packageManager"
				path: packageItem.servicePrefix + "GuiRestartNeeded"
			}

			readonly property string installedVersion: pm.stringValue (installedVersionItem)
			readonly property bool installedValid: installedVersion !== "" && installedVersion !== "--"
			readonly property string incompatibleReason: pm.stringValue (incompatibleItem)

			function versionText (item)
			{
				var version = pm.stringValue (item)
				return version !== "" ? version : "--"
			}

			function statusText ()
			{
				if (rebootNeededItem.valid && rebootNeededItem.value == 1)
					return "REBOOT needed"
				else if (guiRestartNeededItem.valid && guiRestartNeededItem.value == 1)
					return "GUI restart needed"
				else if (incompatibleReason === "PLATFORM")
					return "incompatible with " + pm.stringValue (platform)
				// don't show warning incompatibilities here - they are shown in the editor menu
				else if (incompatibleReason !== ""
						&& incompatibleReason.toLowerCase ().indexOf ("warning") === -1)
					return incompatibleReason
				else if (installedValid)
					return installedVersion + " installed"
				else
					return ""
			}

			text: pm.stringValue (nameItem)
			secondaryText: statusText ()
			caption: "GitHub: " + versionText (gitHubVersionItem) + "    Stored: " + versionText (packageVersionItem)
			pageUrl: Qt.resolvedUrl ("PageSettingsPackageEdit.qml")
			pageProperties: ({ packageIndex: packageItem.index })
		}
	}
}
