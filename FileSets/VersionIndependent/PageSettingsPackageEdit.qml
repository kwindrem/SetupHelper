/////// new menu for package version edit

import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: platform.valid ? qsTr("Package editor") : qsTr ("Package manager not running")

	property bool isCurrentItem: root.ListView.isCurrentItem
	property MbStyle style: MbStyle { isCurrentItem: root.ListView.isCurrentItem }

	property string settingsPrefix: "com.victronenergy.settings/Settings/PackageManager"
	property string servicePrefix: "com.victronenergy.packageManager"
	property int packageIndex: 0
	property int defaultIndex:0
	property VBusItem packageCount: VBusItem { bind: Utils.path(settingsPrefix, "/Count") }
	property VBusItem editAction: VBusItem { bind: Utils.path(servicePrefix, "/GuiEditAction") }
	property VBusItem editStatus: VBusItem { bind: Utils.path(servicePrefix, "/GuiEditStatus") }

	property string packageName: packageNameBox.item.valid ? packageNameBox.item.value : ""
	property bool isSetupHelper: packageName == "SetupHelper"

	property VBusItem incompatibleReasonItem: VBusItem { bind: getServiceBind ( "Incompatible") }
	property string incompatibleReason: incompatibleReasonItem.valid ? incompatibleReasonItem.value : ""
	property VBusItem packageConflictsItem: VBusItem { bind: getServiceBind ( "PackageConflicts") }
	property string packageConflicts: packageConflictsItem.valid ? packageConflictsItem.value : ""
	property bool incompatible: incompatibleReason != ""
	property VBusItem platform: VBusItem { bind: Utils.path(servicePrefix, "/Platform") }

	property bool gitHubValid: gitHubVersion.item.valid && gitHubVersion.item.value.substring (0,1) === "v"
	property bool packageValid: packageVersion.item.valid && packageVersion.item.value.substring (0,1) === "v"
	property bool installedValid: installedVersion.item.valid && installedVersion.item.value.substring (0,1) === "v"
	property bool downloadOk: gitHubValid && gitHubVersion.item.value != ""
	property bool installOk: packageValid && packageVersion.item.value  != "" && ! incompatible
	property string requestedAction: ''
	property bool actionPending: requestedAction != ''
	property bool navigate: ! actionPending && ! waitForAction
	property bool waitForAction: editAction.value != ''
	property bool editError: editAction.value == 'ERROR'
	property bool conflictsExist: packageConflicts != ""

	property VBusItem defaultPackageName: VBusItem { bind: Utils.path ( servicePrefix, "/Default/", defaultIndex, "/", "PackageName" ) }
	property VBusItem defaultGitHubUser: VBusItem { bind: Utils.path ( servicePrefix, "/Default/", defaultIndex, "/", "GitHubUser" ) }
	property VBusItem defaultGitHubBranch: VBusItem { bind: Utils.path ( servicePrefix, "/Default/", defaultIndex, "/", "GitHubBranch" ) }
	// version info may be in platform service or in vePlatform.version
	VBusItem { id: osVersionItem; bind: Utils.path("com.victronenergy.platform", "/Firmware/Installed/Version" ) }
	property string osVersion: osVersionItem.valid ? osVersionItem.value : vePlatform.version

	// ActionNeeded is a global parameter provided inform the GUI that a GUI restart or system reboot is needed
	// when dismissed, a timer started which hides the information
	// when the timer expires, the information is shown again
	// changes to ActionNeeded will stop the timer so the new value will be shown immediately
	property VBusItem actionNeededItem: VBusItem { bind: Utils.path(servicePrefix, "/ActionNeeded") }
	property string actionNeeded: actionNeededItem.valid ? actionNeededItem.value : ""
	property bool showActionNeeded: ! hideActionNeededTimer.running && actionNeeded != ''

	onActionNeededChanged: hideActionNeededTimer.stop ()
	
	// hide action for 10 minutes
	Timer {
		id: hideActionNeededTimer
		running: false
		repeat: false
		interval: 1000 * 5 ////////// 60 * 10
		triggeredOnStart: true
	}

	Component.onCompleted:
	{
		hideActionNeededTimer.stop ()
		resetPackageIndex ()
		// request PackageManager to refresh GitHub version info for this package
		sendCommand ('gitHubScan' + ':' + packageName)
	}

	function resetPackageIndex ()
	{
		if (packageIndex < 0)
			packageIndex = 0
		else if (packageIndex >= packageCount.value)
			packageIndex = packageCount.value - 1
	}

	function getSettingsBind(param)
	{
		return Utils.path(settingsPrefix, "/", packageIndex, "/", param)
	}
	function getServiceBind(param)
	{
		return Utils.path(servicePrefix, "/Package/", packageIndex, "/", param)
	}

	function sendCommand (command)
	{
		if (packageIndex >= 0 && packageIndex < packageCount.value)
			editAction.setValue (command)
	}
	function setEditStatus (status)
	{
		if (packageIndex >= 0 && packageIndex < packageCount.value)
			editStatus.setValue (status)
	}

	function nextIndex ()
	{
		var newIndex = packageIndex + 1
		if (newIndex >= packageCount.value)
			newIndex = packageCount.value - 1
		// if new package, request PackageManager to refresh GitHub version info for this package
		if (packageIndex != newIndex)
		{
			cancelEdit ()
			packageIndex = newIndex
			sendCommand ('gitHubScan' + ':' + packageName)
		}
	}
	function previousIndex ()
	{
		var newIndex = packageIndex - 1
		if (newIndex < 0)
		newIndex = 0
		// if new package, notify PackageManager to refresh GitHub version info for this package
		if (packageIndex != newIndex)
		{
			cancelEdit ()
			packageIndex = newIndex
			sendCommand ('gitHubScan' + ':' + packageName)
		}
	}

	// only the cancel edit button sets hideActionNeeded
	function cancelEdit (hideActionNeeded)
	{
		if (hideActionNeeded)
			hideActionNeededTimer.start ()
		requestedAction = ''
		sendCommand ( '' )
		setEditStatus ( '' )
	}
	function confirm ()
	{
		// provide local confirmation of action in case PackageManager doesn't act on it
		if (showActionNeeded)
		{
			if (actionNeeded == 'reboot')
			{
				setEditStatus ( "sending reboot request" )
				sendCommand ( 'reboot' )
			}
			else if (actionNeeded == 'guiRestart')
			{
				setEditStatus ( "sending GUI restart request" )
				sendCommand ( 'restartGui' )
			}
		}
		else if (actionPending)
		{
			setEditStatus ( "sending " + requestedAction + packageName + " request")
			sendCommand (requestedAction + ':' + packageName)
		}
		requestedAction = ''
	}
	function install ()
	{
		if (navigate && installOk)
			requestedAction = 'install'
	}
	function uninstall ()
	{
		if (navigate && installedValid)
			requestedAction = 'uninstall'
	}
	function gitHubDownload ()
	{
		if (navigate && downloadOk)
			requestedAction = 'download'
	}
	function remove ()
	{
		requestedAction = 'remove'
	}

	model: VisibleItemModel
	{
		MbEditBox
		{
			id: packageNameBox
			description: qsTr ("Package name and versions")
			maximumLength: 30
			item.bind: getSettingsBind ("PackageName")
			overwriteMode: false
			writeAccessLevel: User.AccessInstaller
			readonly: true
		}
		MbRowSmall
		{
			description: " "
			height: 25
			Text
			{
				text: "GitHub:"
				color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
				font.pixelSize: 10
			}
			MbTextBlock
			{
				id: gitHubVersion
				item { bind: getServiceBind("GitHubVersion") }
				height: 25; width: 105
			}
			Text
			{
				text: qsTr ("stored:")
				color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
				font.pixelSize: 10
			}
			MbTextBlock
			{
				id: packageVersion
				item { bind: getServiceBind("PackageVersion") }
				height: 25; width: 105
			}
			Text
			{
				text: qsTr ("installed:")
				color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
				horizontalAlignment: Text.AlignRight
				font.pixelSize: 10
			}
			MbTextBlock
			{
				id: installedVersion
				item { bind: getServiceBind("InstalledVersion") }
				height: 25
				width: 105
			}
		}
		MbEditBox
		{
			id: gitHubUser
			description: qsTr ("GitHub user")
			maximumLength: 20
			item.bind: getSettingsBind ("GitHubUser")
			overwriteMode: false
			writeAccessLevel: User.AccessInstaller
		}
		MbEditBox
		{
			id: gitHubBranch
			description: qsTr ("GitHub branch or tag")
			maximumLength: 20
			item.bind: getSettingsBind ("GitHubBranch")
			overwriteMode: false
			writeAccessLevel: User.AccessInstaller
		}
		MbOK
		{
			id: cancelButton
			width: 85
			anchors { right: parent.right; bottom: statusMessage.bottom }
			description: ""
			value: showActionNeeded ? qsTr("Later") : (editError ? qsTr("OK") : qsTr("Cancel"))
			onClicked: cancelEdit (showActionNeeded)
			show: actionPending || waitForAction || editError || showActionNeeded
		}
		MbOK
		{
			id: confirmButton
			width: 92
			anchors { right: cancelButton.left; bottom: statusMessage.bottom }
			description: ""
			value: showActionNeeded ? qsTr("Now") : qsTr ("Proceed")
			onClicked: confirm ()
			show: ( actionPending || waitForAction || showActionNeeded) && ! editError
			writeAccessLevel: User.AccessInstaller
		}

		// bottom row of buttons
		MbOK
		{
			id: previousButton
			width: 100
			anchors { left: parent.left; top: statusMessage.bottom; topMargin: 5  }
			description: ""
			value: qsTr("Previous")
			onClicked: previousIndex ()
			opacity: packageIndex > 0 ? 1.0 : 0.2
		}
		MbOK
		{
			id: nextButton
			width: 75
			anchors { left: previousButton.right; top: statusMessage.bottom; topMargin: 5 }
			description: ""
			value: qsTr("Next")
			onClicked: nextIndex ()
			opacity: (packageIndex < packageCount.value - 1) ? 1.0 : 0.2
		}
		MbOK
		{
			id: downloadButton
			width: 110
			anchors { left: nextButton.right; top: statusMessage.bottom; topMargin: 5 }
			description: ""
			value: qsTr ("Download")
			onClicked: gitHubDownload ()
			opacity: navigate && downloadOk > 0 ? 1.0 : 0.2
			writeAccessLevel: User.AccessInstaller
		}
		MbOK
		{
			id: installButton
			width: 90
			anchors { right: uninstallButton.left; top: statusMessage.bottom; topMargin: 5 }
			description: ""
			value: qsTr ("Install")
			onClicked: install ()
			opacity: navigate && installOk > 0 ? 1.0 : 0.2
			writeAccessLevel: User.AccessInstaller
		}
		MbOK
		{
			id: uninstallButton
			width: 100
			anchors { right: parent.right; top: statusMessage.bottom; topMargin: 5 }
			description: ""
			value: installedValid ? qsTr("Uninstall") : qsTr("Remove")
			onClicked: installedValid ? uninstall () : remove ()
			opacity: navigate ? 1.0 : 0.2
			writeAccessLevel: User.AccessInstaller
		}
		MbOK
		{
			id: showConflictsButton
			width: 150
			anchors { right: parent.right; bottom: statusMessage.bottom}
			description: ""
			value: qsTr("Show Conflicts")
			onClicked: requestedAction = 'resolveConflicts'
			writeAccessLevel: User.AccessInstaller
			show: navigate && conflictsExist && ! editError
		}
		// at bottom so it's not in the middle of hard button cycle
		Text
		{
			id: statusMessage
			width:
			{
				var smWidth = root.width
				if (cancelButton.show)
					smWidth -= cancelButton.width
				if (confirmButton.show)
					smWidth -= confirmButton.width
				if (showConflictsButton.show)
					smWidth -= showConflictsButton.width
				return smWidth
			}
			height: Math.max (paintedHeight, 35)
			wrapMode: Text.WordWrap
			horizontalAlignment: Text.AlignLeft
			anchors { left: parent.left; leftMargin: 5; top: gitHubBranch.bottom }
			font.pixelSize: 12
			color: actionPending && isSetupHelper ? "red" : root.style.textColor
			text:
			{
				if (actionPending)
				{
					if (requestedAction == 'resolveConflicts')
						return ( packageConflicts + qsTr ("\nResolve conflicts?") )
					else if (isSetupHelper && requestedAction == 'uninstall')
						return qsTr ("WARNING: SetupHelper is required for these menus - uninstall anyway ?")
					else
						return (requestedAction + " " + packageName + " ?")
				}
				else if (editStatus.valid && editStatus.value != "")
					return ( editStatus.value )
				else if (incompatible)
					return ( incompatibleReason )
				else if (showActionNeeded)
				{
					if (actionNeeded == 'reboot')
						return qsTr ("Reboot now?")
					else if (actionNeeded == 'guiRestart')
						return qsTr ("restart GUI now ?")
					else
						return ( "unknown ActionNeeded " + actionNeeded ) 
				}
				else
					return ""
			}
		}
		// dummy item to allow scrolling to show last button line when status message has many lines
		MbItemText
		{
			text: ""
			opacity: 0
			show: statusMessage.height > 35
		}
	}
}
