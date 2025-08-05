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
	property VBusItem packageNameItem: VBusItem { bind: getSettingsBind ("PackageName") }
	property string packageName: packageNameItem.valid ? packageNameItem.value : ""
	property bool isSetupHelper: packageName == "SetupHelper"

	property VBusItem incompatibleReasonItem: VBusItem { bind: getServiceBind ( "Incompatible" ) }
	property string incompatibleReason: incompatibleReasonItem.valid ? incompatibleReasonItem.value : ""
	property VBusItem incompatibleDetailsItem: VBusItem { bind: getServiceBind ( "IncompatibleDetails") }
	property string incompatibleDetails: incompatibleDetailsItem.valid ? incompatibleDetailsItem.value : ""
	property bool incompatible: incompatibleReason != ""
	property VBusItem platform: VBusItem { bind: Utils.path(servicePrefix, "/Platform") }
	property VBusItem incompatibleResolvableItem: VBusItem { bind: getServiceBind ( "IncompatibleResolvable") }
	
	property bool gitHubValid: gitHubVersion.item.valid && gitHubVersion.item.value.substring (0,1) === "v"
	property bool packageValid: packageVersion.item.valid && packageVersion.item.value.substring (0,1) === "v"
	property bool installedValid: installedVersion.item.valid && installedVersion.item.value.substring (0,1) === "v"
	property bool downloadOk: gitHubValid && gitHubVersion.item.value != ""
	property bool installOk: ! incompatible
	property string requestedAction: ''
	property bool actionPending: requestedAction != ''
	property bool waitForAction: editAction.value != '' && ! editError
	property bool editError: editAction.value == 'ERROR'
	property bool navigate: ! actionPending && ! waitForAction
	property bool detailsExist: incompatibleDetails != ""
	property bool detailsResolvable: incompatibleResolvableItem.valid ? incompatibleResolvableItem.value : ""

	property bool showDetails: false
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

	
	onActionNeededChanged:
	{
		hideActionNeededTimer.stop ()
	}
	
	onWaitForActionChanged:
	{
		if ( ! waitForAction )
		{
			hideActionNeededTimer.stop ()
			requestedAction = ''
		}
	}

	onIncompatibleChanged:
	{
		if (! incompatible )
			showDetails = false
	}

	onActiveChanged:
	{
		if (active)
		{
			hideActionNeededTimer.stop ()
			resetPackageIndex ()
			refreshGitHubVersions ()
			acknowledgeError ()
			requestedAction = ''
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
		else if (! active || editAction.value != "" || actionPending)
			return
		sendCommand ( 'gitHubScan' + ':' + packageName, false )
	}

	// acknowledge error reported from PackageManager
	//	and erase status message
	function acknowledgeError ()
	{
		if (editError)
		{
			editAction.setValue ("")
			editStatus.setValue ("")
		}
	}

	function resetPackageIndex ()
	{
		if (waitForAction)
			return

		if (newPackageIndex < 0)
			newPackageIndex = 0
		else if (newPackageIndex >= packageCount.value)
			newPackageIndex = packageCount.value - 1

		if (newPackageIndex != packageIndex)
		{
			waitForIndexChange = true
			waitForNameChange = true
			packageIndex = newPackageIndex
			requestedAction = ''
			showDetails = false
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

	function sendCommand (command, updateEditStatus )
	{
		if (editAction.value != "")
			localError = "command could not be sent ("  + command + ")"
		else
		{
			if (updateEditStatus)
				editStatus.setValue ("sending " + command)
			editAction.setValue (command)
		}
	}

	// don't change packages if pending operation or waiting for completion
	function nextIndex ()
	{
		if (editError)
			return
		newPackageIndex += 1
		resetPackageIndex ()
	}
	function previousIndex ()
	{
		if (editError)
			return
		newPackageIndex -= 1
		resetPackageIndex ()
	}

	function cancelEdit ()
	{
		// cancel any pending operation
		requestedAction = ''
		showDetails = false

		acknowledgeError ()

		// if was showing action needed, hide that messge for now
		if (showActionNeeded)
			hideActionNeededTimer.start ()
	}
	function confirm ()
	{
		if (showDetails)
		{
			if (detailsResolvable)
			{
				sendCommand ( 'resolveConflicts:' + packageName, true )
				showDetails = false
			}
			// trigger setup script prechecks
			else
			{
				sendCommand ( 'check:' + packageName, true )
				showDetails = false
			}
		}
		else if (actionPending)
			sendCommand ( requestedAction + ':' + packageName, true )
		else if (showActionNeeded)
		{
			if (actionNeeded.indexOf ( "REBOOT" ) != -1 )
				sendCommand ( 'reboot', true )
			else if (actionNeeded.indexOf ( "restart" ) != -1 )
				sendCommand ( 'restartGui', true )
				hideActionNeededTimer.start ()
		}
		requestedAction = ''
	}
	function install ()
	{
		if (navigate && installOk && ! editError)
		{
			requestedAction = 'install'
			showDetails = false
		}
	}
	function uninstall ()
	{
		if (navigate && installedValid && ! editError)
		{
			requestedAction = 'uninstall'
			showDetails = false
		}
	}
	function gitHubDownload ()
	{
		if (navigate && downloadOk && ! editError)
		{
			requestedAction = 'download'
			showDetails = false
		}
	}
	function remove ()
	{
		if ( ! editError)
		{
			requestedAction = 'remove'
			showDetails = false
		}
	}

	model: VisibleItemModel
	{
		MbItemText
		{
			id: packageNameBox
			text: packageName + " versions"
		}
		Row
		{
			height: 25
			leftPadding: 7; rightPadding: 5; spacing: 1
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
				height: 25; width: 112
			}
			Text
			{
				text: qsTr (" stored:")
				color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
				font.pixelSize: 10
			}
			MbTextBlock
			{
				id: packageVersion
				item { bind: getServiceBind("PackageVersion") }
				height: 25; width: 112
			}
			Text
			{
				text: qsTr (" installed:")
				color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
				horizontalAlignment: Text.AlignRight
				font.pixelSize: 10
			}
			MbTextBlock
			{
				id: installedVersion
				item { bind: getServiceBind("InstalledVersion") }
				height: 25
				width: 112
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
			anchors { right: gitHubBranch.right; bottom: statusMessage.bottom }
			description: ""
			value: ( actionPending || showDetails ) ? qsTr("Cancel") : (editError ? qsTr("OK") : qsTr("Later"))
			onClicked: cancelEdit ()
			show: ( actionPending || showDetails || editError || showActionNeeded ) && ! waitForAction
		}
		MbOK
		{
			id: confirmButton
			width: 92
			anchors { right: cancelButton.left; bottom: statusMessage.bottom }
			description: ""
			value: ( actionPending || detailsResolvable ) ? qsTr("Proceed") : showDetails ? qsTr ("Recheck") : qsTr ("Now")
			onClicked: confirm ()
			show: ( actionPending || showDetails || showActionNeeded ) && ! waitForAction
			writeAccessLevel: User.AccessInstaller
		}
		MbOK
		{
			id: showDetailsButton
			width: 150
			anchors { right: gitHubBranch.right; bottom: statusMessage.bottom}
			description: ""
			value: qsTr("Show Details")
			onClicked: showDetails = true
			writeAccessLevel: User.AccessInstaller
			show: navigate && detailsExist && ! ( editError || actionPending || waitForAction || showActionNeeded || showDetails)
		}
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
				if (showDetailsButton.show)
					smWidth -= showDetailsButton.width
				return smWidth
			}
			height: Math.max (paintedHeight, 35)
			wrapMode: Text.WordWrap
			horizontalAlignment: Text.AlignLeft
			anchors { left: gitHubBranch.left; leftMargin: 5; top: gitHubBranch.bottom }
			font.pixelSize: 12
			color: isSetupHelper && requestedAction == 'uninstall' ? "red" : root.style.textColor
			text:
			{
				if (showDetails)
				{
					if (detailsResolvable)
						return ( incompatibleDetails + qsTr ("\nResolve conflicts?") )
					else
						return ( incompatibleDetails )
				}
				else if (actionPending)
				{
					if (isSetupHelper && requestedAction == 'uninstall')
						return qsTr ("WARNING: SetupHelper is required for these menus - uninstall anyway ?")
					else
						return (requestedAction + " " + packageName + " ?")
				}
				else if (editStatus.valid && editStatus.value != "")
					return ( editStatus.value )
				else if (showActionNeeded)
					return ( actionNeeded ) 
				else if (incompatible)
					return ( incompatibleReason )
				else
					return localError
			}
		}
		// bottom row of buttons
		MbOK
		{
			id: previousButton
			width: 100
			anchors { left: gitHubBranch.left; top: statusMessage.bottom; topMargin: 5  }
			description: ""
			value: qsTr("Previous")
			onClicked: previousIndex ()
			opacity: ! editError && newPackageIndex > 0 ? 1.0 : 0.2
		}
		MbOK
		{
			id: nextButton
			width: 70
			anchors { left: previousButton.right; top: statusMessage.bottom; topMargin: 5 }
			description: ""
			value: qsTr("Next")
			onClicked: nextIndex ()
			opacity: ! editError && (newPackageIndex < packageCount.value - 1) ? 1.0 : 0.2
		}
		MbOK
		{
			id: downloadButton
			width: 110
			anchors { right: installButton.left; top: statusMessage.bottom; topMargin: 5 }
			description: ""
			value: qsTr ("Download")
			onClicked: gitHubDownload ()
			opacity: ! editError && navigate && downloadOk > 0 ? 1.0 : 0.2
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
			opacity: ! editError && navigate && installOk > 0 ? 1.0 : 0.2
			writeAccessLevel: User.AccessInstaller
		}
		MbOK
		{
			id: uninstallButton
			width: 105
			anchors { right: gitHubBranch.right; top: statusMessage.bottom; topMargin: 5 }
			description: ""
			value: installedValid ? qsTr("Uninstall") : qsTr("Remove")
			onClicked: installedValid ? uninstall () : remove ()
			opacity: ! editError && navigate ? 1.0 : 0.2
			writeAccessLevel: User.AccessInstaller
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
