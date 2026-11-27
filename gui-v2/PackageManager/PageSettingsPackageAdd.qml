//////// PackageManager gui-v2 plugin
// add a package to the active package list
// gui-v2 version of PageSettingsPackageAdd.qml
//
// the values are edited in /Settings/PackageManager/Edit/...
//	and 'add:packageName' asks PackageManager to add the package
// unlike the GUI v1 page, this page stays open when the package has been added

import QtQuick
import Victron.GuiPlugins

PluginPage {
	id: root

	// set by the inactive package list when it opens this page
	property int defaultIndex: 0

	title: pm.running ? "Add package" : "Package manager not running"

	readonly property string editPrefix: pm.settingsPath + "/Edit/"
	readonly property string defaultPrefix: "/Default/" + defaultIndex + "/"

	PmService {
		id: pm

		onEditActionChanged:
		{
			// PackageManager sets /GuiEditAction back to "" when the add is done
			if (root.addPending && pm.editAction === "")
			{
				root.addPending = false
				root.added = true
			}
			else if (pm.editError)
				root.addPending = false
		}
		// values are written later, not while a value is still reporting its change
		onEditActionValidChanged: Qt.callLater (root.copyDefaults)
	}

	PluginDataItem {
		id: defaultNameItem
		serviceType: "packageManager"
		path: root.defaultPrefix + "PackageName"
		onValidChanged: Qt.callLater (root.copyDefaults)
	}
	PluginDataItem {
		id: defaultGitHubUserItem
		serviceType: "packageManager"
		path: root.defaultPrefix + "GitHubUser"
		onValidChanged: Qt.callLater (root.copyDefaults)
	}
	PluginDataItem {
		id: defaultGitHubBranchItem
		serviceType: "packageManager"
		path: root.defaultPrefix + "GitHubBranch"
		onValidChanged: Qt.callLater (root.copyDefaults)
	}

	readonly property string packageName: pm.stringValue (nameField.dataItem)
	readonly property bool entryValid: packageName !== ""
			&& pm.stringValue (gitHubUserField.dataItem) !== ""
			&& pm.stringValue (gitHubBranchField.dataItem) !== ""

	property bool addPending: false
	property bool added: false
	property bool defaultsCopied: false

	// copy the selected default package to the Edit area, once, when its values are known
	function copyDefaults ()
	{
		if (defaultsCopied || ! pm.editActionValid || ! defaultNameItem.valid
				|| ! defaultGitHubUserItem.valid || ! defaultGitHubBranchItem.valid)
			return
		defaultsCopied = true

		var defaultName = pm.stringValue (defaultNameItem)
		if (defaultName === "new")
			defaultName = ""
		nameField.dataItem.setValue (defaultName)
		gitHubUserField.dataItem.setValue (pm.stringValue (defaultGitHubUserItem))
		gitHubBranchField.dataItem.setValue (pm.stringValue (defaultGitHubBranchItem))
		pm.acknowledgeError ()
		if (pm.idle)
			pm.editStatusItem.setValue ("")
	}

	Component.onCompleted: copyDefaults ()

	function add ()
	{
		if (! entryValid || ! pm.idle)
			return
		added = false
		addPending = true
		// provide local confirmation of action - takes PackageManager too long
		pm.send ("add:" + packageName, "adding " + packageName)
	}

	PluginItemListView {
		PluginListTextField {
			id: nameField
			text: "Package name"
			dataItem.serviceType: "settings"
			dataItem.path: root.editPrefix + "PackageName"
			maximumLength: 30
			writeAccessLevel: PluginAccessLevel.Installer
		}

		PluginListTextField {
			id: gitHubUserField
			text: "GitHub user"
			dataItem.serviceType: "settings"
			dataItem.path: root.editPrefix + "GitHubUser"
			maximumLength: 20
			writeAccessLevel: PluginAccessLevel.Installer
		}

		PluginListTextField {
			id: gitHubBranchField
			text: "GitHub branch or tag"
			dataItem.serviceType: "settings"
			dataItem.path: root.editPrefix + "GitHubBranch"
			maximumLength: 20
			writeAccessLevel: PluginAccessLevel.Installer
		}

		PluginPrimaryListLabel {
			text:
			{
				if (pm.editStatus !== "")
					return pm.editStatus
				else if (root.added)
					return root.packageName + " added - see Active packages"
				else if (root.packageName === "")
					return "enter a unique package name"
				else if (pm.stringValue (gitHubUserField.dataItem) === "")
					return "enter GitHub user"
				else if (pm.stringValue (gitHubBranchField.dataItem) === "")
					return "enter GitHub branch"
				else
					return ""
			}
			preferredVisible: text !== ""
		}

		PluginListButton {
			text: "PackageManager reported an error"
			secondaryText: "OK"
			writeAccessLevel: PluginAccessLevel.User
			preferredVisible: pm.editError
			onClicked: pm.acknowledgeError ()
		}

		PluginListButton {
			text: root.entryValid ? "Add " + root.packageName : "Add package"
			secondaryText: "Proceed"
			interactive: root.entryValid && pm.idle && ! root.addPending
			onClicked: root.add ()
		}
	}
}
