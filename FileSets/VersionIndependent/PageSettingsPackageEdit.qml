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
    property VBusItem defaultCount: VBusItem { bind: Utils.path(servicePrefix, "/DefaultCount") }
    property VBusItem packageCount: VBusItem { bind: Utils.path(settingsPrefix, "/Count") }
    property VBusItem editAction: VBusItem { bind: Utils.path(servicePrefix, "/GuiEditAction") }
    property VBusItem editStatus: VBusItem { bind: Utils.path(servicePrefix, "/GuiEditStatus") }
    property string packageName: packageNameBox.item.valid ? packageNameBox.item.value : ""
    property bool isSetupHelper: packageName == "SetupHelper"

    property VBusItem rebootNeeded: VBusItem { bind: getServiceBind ( "RebootNeeded") }
    property VBusItem guiRestartNeeded: VBusItem { bind: getServiceBind ( "GuiRestartNeeded") }
	property VBusItem incompatibleReasonItem: VBusItem { bind: getServiceBind ( "Incompatible") }
	property string incompatibleReason: incompatibleReasonItem.valid ? incompatibleReasonItem.value : ""
	property VBusItem incompatibleDetailsItem: VBusItem { bind: getServiceBind ( "IncompatibleDetails") }
	property string incompatibleDetails: incompatibleDetailsItem.valid ? incompatibleDetailsItem.value : ""
    property bool incompatible: incompatibleReason != ""
    property VBusItem platform: VBusItem { bind: Utils.path(servicePrefix, "/Platform") }
	property bool showIncompableDetails: false

    property bool gitHubValid: gitHubVersion.item.valid && gitHubVersion.item.value.substring (0,1) === "v"
    property bool packageValid: packageVersion.item.valid && packageVersion.item.value.substring (0,1) === "v"
    property bool installedValid: installedVersion.item.valid && installedVersion.item.value.substring (0,1) === "v"
    property bool downloadOk: gitHubValid && gitHubVersion.item.value != ""
    property bool installOk: packageValid && packageVersion.item.value  != "" && ! incompatible
    property string requestedAction: ''
    property bool actionPending: requestedAction != ''
    property bool navigate: ! actionPending && ! waitForAction
    property bool waitForAction: editAction.value != ''
    property bool moreActions: editAction.value == 'RebootNeeded' || editAction.value == 'GuiRestartNeeded'

    property VBusItem defaultPackageName: VBusItem { bind: Utils.path ( servicePrefix, "/Default/", defaultIndex, "/", "PackageName" ) }
    property VBusItem defaultGitHubUser: VBusItem { bind: Utils.path ( servicePrefix, "/Default/", defaultIndex, "/", "GitHubUser" ) }
    property VBusItem defaultGitHubBranch: VBusItem { bind: Utils.path ( servicePrefix, "/Default/", defaultIndex, "/", "GitHubBranch" ) }
    property VBusItem editPackageName: VBusItem { bind: Utils.path ( settingsPrefix, "/Edit/", "PackageName" ) }
    property VBusItem editGitHubUser: VBusItem { bind: Utils.path ( settingsPrefix, "/Edit/", "GitHubUser" ) }
    property VBusItem editGitHubBranch: VBusItem { bind: Utils.path ( settingsPrefix, "/Edit/", "GitHubBranch" ) }

	// version info may be in platform service or in vePlatform.version
    VBusItem { id: osVersionItem; bind: Utils.path("com.victronenergy.platform", "/Firmware/Installed/Version" ) }
    property string osVersion: osVersionItem.valid ? osVersionItem.value : vePlatform.version

	Component.onCompleted:
	{
		resetPackageIndex ()
		// request PackageManager to refresh GitHub version info for this package
		editAction.setValue ('gitHubScan' + ':' + packageName)
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
		resetPackageIndex ()
		return Utils.path(settingsPrefix, "/", packageIndex, "/", param)
	}
	function getServiceBind(param)
	{
		resetPackageIndex ()
		return Utils.path(servicePrefix, "/Package/", packageIndex, "/", param)
	}

    function nextIndex ()
    {
		var lastIndex = packageIndex
		cancelEdit ()
		packageIndex += 1
		if (packageIndex >= packageCount.value)
			packageIndex = packageCount.value - 1
		// if new package, request PackageManager to refresh GitHub version info for this package
		if (packageIndex != lastIndex)

		editAction.setValue ('gitHubScan' + ':' + packageName)
	}
	function previousIndex ()
    {
		var lastIndex = packageIndex
		cancelEdit ()
		packageIndex -= 1
		if (packageIndex < 0)
			packageIndex = 0
		// if new package, notify PackageManager to refresh GitHub version info for this package
		if (packageIndex != lastIndex)
			editAction.setValue ('gitHubScan' + ':' + packageName)
    }

    function cancelEdit ()
    {
		requestedAction = ''
		editAction.setValue ( '' )
		editStatus.setValue ( '' )
    }
    function confirm ()
    {
		if (showIncompableDetails)
		{
			showIncompableDetails = false
			editAction.setValue ("resolveConflicts" + ':' + packageName)
		}
        else if (actionPending)
        {
			// provide local confirmation of action - takes PackageManager too long
			editStatus.setValue ( (requestedAction == 'remove' ? "removing " : requestedAction + "ing ") + packageName)
            editAction.setValue (requestedAction + ':' + packageName)
			requestedAction = ''
        }
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
    function signalAdditionalAction ()
    {
		if (editAction.value == 'RebootNeeded')
		{
			// provide local confirmation of action - takes PackageManager too long
			editStatus.setValue ( "rebooting")
			editAction.setValue ( 'reboot' )
		}
		else if (editAction.value == 'GuiRestartNeeded')
		{
			// provide local confirmation of action - takes PackageManager too long
			editStatus.setValue ( "restarting GUI")
			editAction.setValue ( 'restartGui' )
		}
		requestedAction = ''
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
            width: 90
            anchors { right: parent.right; bottom: statusMessage.bottom }
            description: ""
            value: qsTr("Cancel")
            onClicked: showIncompableDetails ? showIncompableDetails = false : cancelEdit ()
            show: ! navigate && ! waitForAction || showIncompableDetails
        }
        MbOK
        {
            id: dismissErrorButton
            width: 90
            anchors { right: parent.right; bottom: statusMessage.bottom }
            description: ""
            value: qsTr("OK")
            onClicked: cancelEdit ()
            show: editAction.value == 'ERROR' || editStatus.value == "command failed"
        }
        MbOK
        {
            id: laterButton
            width: 90
            anchors { right: parent.right; bottom: statusMessage.bottom }
            description: ""
            value: qsTr("Later")
            onClicked: cancelEdit ()
            show: moreActions
        }
        MbOK
        {
            id: nowButton
            width: 90
            anchors { right: laterButton.left; bottom: statusMessage.bottom }
            description: ""
            value: qsTr("Now")
            onClicked: signalAdditionalAction ()
            show: moreActions
        }
        MbOK
        {
            id: confirmButton
            width: 90
            anchors { right: cancelButton.left; bottom: statusMessage.bottom }
            description: ""
            value: qsTr ("Proceed")
            onClicked: confirm ()
            show: ! navigate && actionPending || showIncompableDetails
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
            onClicked: uninstall ()
            opacity: navigate ? 1.0 : 0.2
            writeAccessLevel: User.AccessInstaller
        }
		MbOK
		{
			id: showDetailsButton
			width: 170
			anchors { right: parent.right; bottom: statusMessage.bottom}
			description: ""
			value: qsTr("Show Details")
			onClicked: showIncompableDetails = true
			writeAccessLevel: User.AccessInstaller
			show: navigate && incompatibleDetails != "" && ! showIncompableDetails && ! dismissErrorButton.show
		}
		// at bottom so it's not in the middle of hard button cycle
        Text
        {
            id: statusMessage
            width: dismissErrorButton.show ? root.width - dismissErrorButton.width : 250
			height: 35
            wrapMode: Text.WordWrap
            anchors { left: parent.left; leftMargin: 10; top: gitHubBranch.bottom; topMargin: 5 }
            font.pixelSize: 12
            color: actionPending && isSetupHelper ? "red" : root.style.textColor
            text:
            {
				if (showIncompableDetails)
					return incompatibleDetails
				else if (actionPending)
				{
					if (isSetupHelper && requestedAction == 'uninstall')
						return qsTr ("WARNING: SetupHelper is required for these menus - uninstall anyway ?")
					else
						return (requestedAction + " " + packageName + " ?")
				}
				else if (editStatus.valid && editStatus.value != "")
					return editStatus.value
				else if (incompatible)
					return incompatibleReason
				else
					return " "
			}
        }
    }
}
