pragma ComponentBehavior: Bound

//////// PackageManager gui-v2 plugin
// list of inactive (default) packages (tap to activate)
// gui-v2 version of PageSettingsAddPackageList.qml and MbDisplayDefaultPackage.qml

import QtQuick
import Victron.GuiPlugins

PluginPage {
	id: root

	title: pm.running ? "Inactive packages" : "Package manager not running"

	PmService {
		id: pm
	}

	// DefaultCount also indicates that PackageManager is running
	PluginDataItem {
		id: defaultCount
		serviceType: "packageManager"
		path: "/DefaultCount"
	}

	PluginModelListView {
		model: defaultCount.valid ? defaultCount.value : 0

		delegate: PluginListNavigation {
			id: defaultItem

			required property int index

			readonly property string servicePrefix: "/Default/" + index + "/"

			readonly property PluginDataItem nameItem: PluginDataItem {
				serviceType: "packageManager"
				path: defaultItem.servicePrefix + "PackageName"
			}
			readonly property PluginDataItem gitHubUserItem: PluginDataItem {
				serviceType: "packageManager"
				path: defaultItem.servicePrefix + "GitHubUser"
			}
			readonly property PluginDataItem gitHubBranchItem: PluginDataItem {
				serviceType: "packageManager"
				path: defaultItem.servicePrefix + "GitHubBranch"
			}

			readonly property string packageName: pm.stringValue (nameItem)

			// the first entry ("new") is for a package that is not in the default list
			text: packageName === "new" ? "New package" : packageName
			caption:
			{
				if (packageName === "new")
					return "enter the package name and its GitHub source"
				return "GitHub user: " + pm.stringValue (gitHubUserItem)
						+ "    GitHub tag: " + pm.stringValue (gitHubBranchItem)
			}
			pageUrl: Qt.resolvedUrl ("PageSettingsPackageAdd.qml")
			pageProperties: ({ defaultIndex: defaultItem.index })
		}
	}
}
