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
	property int newPackageIndex:0
	property VBusItem packageCount: VBusItem { bind: Utils.path(settingsPrefix, "/Count") }
	property VBusItem editAction: VBusItem { bind: Utils.path(servicePrefix, "/GuiEditAction") }
	property VBusItem editStatus: VBusItem { bind: Utils.path(servicePrefix, "/GuiEditStatus") }
	property VBusItem gitHubVersionAgeItem: VBusItem { bind: getServiceBind ( "GitHubVersionAge" ) }
	property int gitHubVersionAge: gitHubVersionAgeItem.valid ? gitHubVersionAgeItem.value : 0
	property VBusItem packageNameItem: VBusItem { bind: getSettingsBind ("PackageName") }
	property string packageName: packageNameItem.valid ? packageNameItem.value : ""
	property bool isSetupHelper: packageName == "SetupHelper"

	property VBusItem incompatibleReasonItem: VBusItem { bind: getServiceBind ( "Incompatible" ) }
	property string incompatibleReason: incompatibleReasonItem.valid ? incompatibleReasonItem.value : ""
	property VBusItem packageConflictsItem: VBusItem { bind: getServiceBind ( "PackageConflicts") }
	property string packageConflicts: packageConflictsItem.valid ? packageConflictsItem.value : ""
	property bool incompatible: incompatibleReason != ""
	property VBusItem platform: VBusItem { bind: Utils.path(servicePrefix, "/Platform") }
	property VBusItem fileSetOkItem: VBusItem { bind: getServiceBind ( "FileSetOk" ) }

	
	property bool gitHubValid: gitHubVersion.item.valid && gitHubVersion.item.value.substring (0,1) === "v"
	property bool packageValid: packageVersion.item.valid && packageVersion.item.value.substring (0,1) === "v"
	property bool installedValid: installedVersion.item.valid && installedVersion.item.value.substring (0,1) === "v"
	property bool downloadOk: gitHubValid && gitHubVersion.item.value != ""
	property bool installOk: fileSetOkItem.valid && fileSetOkItem.value == 1 ? true : false
	property string requestedAction: ''
	property bool actionPending: requestedAction != ''
	property bool waitForAction: editAction.value != ''
	property bool navigate: ! actionPending && ! waitForAction
	property bool editError: editAction.value == 'ERROR'
	property bool conflictsExist: packageConflicts != ""
	property string localError: ""

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

	
	onEditActionChanged:
	{
		hideActionNeededTimer.stop ()
	}
	
	onActiveChanged:
	{
		if (active)
		{
			hideActionNeededTimer.stop ()
			resetPackageIndex ()
			refreshGitHubVersions ()
		}
	}

	onNavigateChanged: resetPackageIndex ()
	
	// hide action for 10 minutes
	Timer
	{
		id: hideActionNeededTimer
		running: false
		repeat: false
		interval: 1000 * 60 * 10
	}

	// refresh the GitHub version GitHub version age is greater than 30 seconds
	property bool waitForIndexChange: false
	property bool waitForNameChange: false
	onGitHubVersionAgeChanged:
	{
		refreshGitHubVersions ()
	}
	onPackageIndexChanged:
	{
		waitForIndexChange = false
	}
	onPackageNameChanged:
	{
		waitForNameChange = false
		refreshGitHubVersions ()
	}

	function refreshGitHubVersions ()
	{
		if ( waitForIndexChange || waitForNameChange )
			return
		else if (! active || gitHubVersionAge < 30 ||  editAction.value != "" )
		{
			return
		}

		sendCommand ( 'gitHubScan' + ':' + packageName )
	}

	function resetPackageIndex ()
	{
		if (newPackageIndex < 0)
			newPackageIndex = 0
		else if (newPackageIndex >= packageCount.value)
			newPackageIndex = packageCount.value - 1

		if (navigate && newPackageIndex != packageIndex)
		{
			waitForIndexChange = true
			waitForNameChange = true
			packageIndex = newPackageIndex
		}
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
		if (editAction.value != "")
			localError = "command could not be sent - reboot needed ("  + command + ")"
		else if (packageIndex >= 0 && packageIndex < packageCount.value)
			editAction.setValue (command)
	}
	function setEditStatus (status)
	{
		if (packageIndex >= 0 && packageIndex < packageCount.value)
			editStatus.setValue (status)
	}

	// don't change packages if pending operation or waiting for completion
	function nextIndex ()
	{
		newPackageIndex += 1
		resetPackageIndex ()
	}
	function previousIndex ()
	{
		newPackageIndex -= 1
		resetPackageIndex ()
	}

	function cancelEdit (hideActionNeeded)
	{
		// only the cancel edit button sets hideActionNeeded
		if (hideActionNeeded)
			hideActionNeededTimer.start ()
		requestedAction = ''
	}
	function confirm ()
	{
		// provide local confirmation of action in case PackageManager doesn't act on it
		if (actionPending)
		{
			setEditStatus ( "sending " + requestedAction + packageName + " request")
			sendCommand (requestedAction + ':' + packageName)
			// insure restart/reboot status shows up immediately after operaiton finishes
			hideActionNeededTimer.stop ()
		}
		else if (showActionNeeded)
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
		MbItemText
		{
			id: packageNameBox
			text: packageName + " versions"
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
			value: actionPending ? qsTr("Cancel") : (editError ? qsTr("OK") : qsTr("Later"))
			onClicked: cancelEdit (showActionNeeded)
			show: ( actionPending || editError || showActionNeeded ) && ! waitForAction
		}
		MbOK
		{
			id: confirmButton
			width: 92
			anchors { right: cancelButton.left; bottom: statusMessage.bottom }
			description: ""
			value: actionPending ? qsTr("Proceed") : qsTr ("Now")
			onClicked: confirm ()
			show: ( actionPending || showActionNeeded ) && ! waitForAction
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
			show: navigate && conflictsExist && ! ( editError || actionPending || waitForAction || showActionNeeded)
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
			opacity: newPackageIndex > 0 ? 1.0 : 0.2
		}
		MbOK
		{
			id: nextButton
			width: 70
			anchors { left: previousButton.right; top: statusMessage.bottom; topMargin: 5 }
			description: ""
			value: qsTr("Next")
			onClicked: nextIndex ()
			opacity: (newPackageIndex < packageCount.value - 1) ? 1.0 : 0.2
		}
		MbOK
		{
			id: downloadButton
			width: 110
			anchors { right: installButton.left; top: statusMessage.bottom; topMargin: 5 }
			description: ""
			value: qsTr ("Download")
			onClicked: gitHubDownload ()
			opacity: navigate && downloadOk > 0 ? 1.0 : 0.2
			writeAccessLevel: User.AccessInstaller
		}
		MbOK
		{
			id: installButton
			width: 80
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
			width: 105
			anchors { right: parent.right; top: statusMessage.bottom; topMargin: 5 }
			description: ""
			value: installedValid ? qsTr("Uninstall") : qsTr("Remove")
			onClicked: installedValid ? uninstall () : remove ()
			opacity: navigate ? 1.0 : 0.2
			writeAccessLevel: User.AccessInstaller
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
				else if (showActionNeeded)
				{
					if (actionNeeded == 'reboot')
						return qsTr ("Reboot now?")
					else if (actionNeeded == 'guiRestart')
						return qsTr ("restart GUI now ?")
					else
						return ( "unknown ActionNeeded " + actionNeeded ) 
				}
				else if (incompatible)
					return ( incompatibleReason )
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
