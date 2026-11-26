//////// PackageManager gui-v2 plugin
// package editor: versions, GitHub source, download / install / uninstall / remove
// gui-v2 version of PageSettingsPackageEdit.qml
//
// differences from the GUI v1 editor:
//	each action asks for confirmation in a dialog (instead of the Proceed / Cancel buttons)
//	there are no Previous / Next buttons: go back to the package list to select another package

import QtQuick
import Victron.GuiPlugins

PluginPage {
	id: root

	// set by the package list when it opens this page
	property int packageIndex: 0

	title: pm.running ? (packageName !== "" ? packageName : "Package editor") : "Package manager not running"

	readonly property string settingsPrefix: pm.settingsPath + "/" + packageIndex + "/"
	readonly property string servicePrefix: "/Package/" + packageIndex + "/"

	PmService {
		id: pm

		// commands are sent later, not while /GuiEditAction is still reporting its change
		onIdleChanged: Qt.callLater (root.refreshGitHubVersion)
		onEditActionValidChanged: Qt.callLater (root.acknowledgeOldError)
	}

	PluginDataItem {
		id: packageNameItem
		serviceType: "settings"
		path: root.settingsPrefix + "PackageName"
	}
	PluginDataItem {
		id: installedVersionItem
		serviceType: "packageManager"
		path: root.servicePrefix + "InstalledVersion"
	}
	PluginDataItem {
		id: gitHubVersionItem
		serviceType: "packageManager"
		path: root.servicePrefix + "GitHubVersion"
	}
	PluginDataItem {
		id: packageVersionItem
		serviceType: "packageManager"
		path: root.servicePrefix + "PackageVersion"
	}
	PluginDataItem {
		id: incompatibleItem
		serviceType: "packageManager"
		path: root.servicePrefix + "Incompatible"
	}
	PluginDataItem {
		id: incompatibleDetailsItem
		serviceType: "packageManager"
		path: root.servicePrefix + "IncompatibleDetails"
	}
	PluginDataItem {
		id: incompatibleResolvableItem
		serviceType: "packageManager"
		path: root.servicePrefix + "IncompatibleResolvable"
	}

	readonly property string packageName: pm.stringValue (packageNameItem)
	readonly property bool isSetupHelper: packageName === "SetupHelper"

	readonly property string installedVersion: pm.stringValue (installedVersionItem)
	readonly property bool installedValid: installedVersion !== "" && installedVersion !== "--"
	readonly property string gitHubVersion: pm.stringValue (gitHubVersionItem)
	readonly property bool gitHubValid: gitHubVersion !== "" && gitHubVersion !== "--"
	readonly property string packageVersion: pm.stringValue (packageVersionItem)
	readonly property bool packageValid: packageVersion !== "" && packageVersion !== "--"

	readonly property string incompatibleReason: pm.stringValue (incompatibleItem)
	readonly property bool incompatible: incompatibleReason !== ""
	readonly property string incompatibleDetails: pm.stringValue (incompatibleDetailsItem)
	readonly property bool detailsExist: incompatibleDetails !== ""
	readonly property bool detailsResolvable: incompatibleResolvableItem.valid && incompatibleResolvableItem.value == 1

	// an action button can be used: PackageManager is idle and the package is known
	readonly property bool canAct: pm.idle && packageName !== ""

	// the action waiting for confirmation in actionDialog
	property string pendingAction: ""
	// set if a command could not be sent
	property string localError: ""

	readonly property string statusMessage:
	{
		if (pm.editStatus !== "")
			return pm.editStatus
		else if (incompatible)
			return incompatibleReason
		else
			return localError
	}

	// refresh the GitHub version of this package, once, when the editor is opened
	property bool gitHubScanSent: false

	function refreshGitHubVersion ()
	{
		if (! gitHubScanSent && pm.idle && packageName !== "")
		{
			gitHubScanSent = true
			pm.send ("gitHubScan:" + packageName)
		}
	}
	onPackageNameChanged: Qt.callLater (refreshGitHubVersion)

	// an error left from an earlier action is acknowledged when the editor is opened
	property bool oldErrorChecked: false

	function acknowledgeOldError ()
	{
		if (! oldErrorChecked && pm.editActionValid)
		{
			oldErrorChecked = true
			pm.acknowledgeError ()
		}
	}

	Component.onCompleted:
	{
		acknowledgeOldError ()
		refreshGitHubVersion ()
	}

	function requestAction (action)
	{
		if (! canAct)
			return
		localError = ""
		pendingAction = action
		actionDialog.open ()
	}

	function runAction ()
	{
		var command = pendingAction + ":" + packageName
		if (! pm.send (command, "sending " + command))
			localError = "command could not be sent (" + command + ")"
		pendingAction = ""
	}

	PluginConfirmationDialog {
		id: actionDialog

		title:
		{
			switch (root.pendingAction)
			{
			case "download":
				return "Download " + root.packageName + "?"
			case "install":
				return "Install " + root.packageName + "?"
			case "uninstall":
				return "Uninstall " + root.packageName + "?"
			case "remove":
				return "Remove " + root.packageName + " from the package list?"
			case "resolveConflicts":
				return "Resolve conflicts?"
			case "check":
				return "Recheck " + root.packageName + "?"
			default:
				return ""
			}
		}
		description:
		{
			switch (root.pendingAction)
			{
			case "download":
				return "From GitHub: " + root.gitHubVersion
			case "install":
				return "Stored version: " + (root.packageValid ? root.packageVersion : "--")
			case "uninstall":
				if (root.isSetupHelper)
					return "WARNING: SetupHelper is required for these menus - uninstall anyway ?"
				return "Installed version: " + root.installedVersion
			case "resolveConflicts":
			case "check":
				return root.incompatibleDetails
			default:
				return ""
			}
		}
		acceptText:
		{
			switch (root.pendingAction)
			{
			case "download":
				return "Download"
			case "install":
				return "Install"
			case "uninstall":
				return "Uninstall"
			case "remove":
				return "Remove"
			case "resolveConflicts":
				return "Resolve"
			case "check":
				return "Recheck"
			default:
				return "OK"
			}
		}
		onAccepted: root.runAction ()
		onRejected: root.pendingAction = ""
	}

	PluginItemListView {
		PluginListText {
			text: root.installedValid ? "Installed version" : "Not installed"
			secondaryText: root.installedValid ? root.installedVersion : ""
		}

		PluginListText {
			text: "GitHub version"
			secondaryText: root.gitHubValid ? root.gitHubVersion : "--"
		}

		PluginListText {
			text: "Stored version"
			secondaryText: root.packageValid ? root.packageVersion : "--"
		}

		PluginListTextField {
			text: "GitHub user"
			dataItem.serviceType: "settings"
			dataItem.path: root.settingsPrefix + "GitHubUser"
			maximumLength: 20
			writeAccessLevel: PluginAccessLevel.Installer
		}

		PluginListTextField {
			text: "GitHub branch or tag"
			dataItem.serviceType: "settings"
			dataItem.path: root.settingsPrefix + "GitHubBranch"
			maximumLength: 20
			writeAccessLevel: PluginAccessLevel.Installer
		}

		PluginPrimaryListLabel {
			text: root.statusMessage
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
			text: "Download from GitHub"
			secondaryText: "Download"
			interactive: root.canAct && root.gitHubValid
			onClicked: root.requestAction ("download")
		}

		PluginListButton {
			text: "Install stored version"
			secondaryText: "Install"
			interactive: root.canAct && ! root.incompatible
			onClicked: root.requestAction ("install")
		}

		PluginListButton {
			text: root.installedValid ? "Uninstall package" : "Remove from package list"
			secondaryText: root.installedValid ? "Uninstall" : "Remove"
			interactive: root.canAct
			onClicked: root.requestAction (root.installedValid ? "uninstall" : "remove")
		}

		PluginListButton {
			text: "Incompatibility details"
			caption: root.incompatibleDetails
			secondaryText: root.detailsResolvable ? "Resolve" : "Recheck"
			preferredVisible: root.detailsExist
			interactive: root.canAct
			onClicked: root.requestAction (root.detailsResolvable ? "resolveConflicts" : "check")
		}

		PmFinishButton {
			service: pm
		}
	}
}
