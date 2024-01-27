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
        if (actionPending)
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
                text:
                {
					if (incompatible)
					{
						if (incompatibleReason == 'PLATFORM')
							return ( qsTr ("not compatible with\n") + platformItem.value )
						else if (incompatibleReason == 'VERSION')
							return ( qsTr ("not compatible with\n") + osVersion )
						else if (incompatibleReason == 'CMDLINE')
							return qsTr ("must install\nfrom command line" )
						else if (incompatibleReason == 'NO_FILE_SET')
							return qsTr ( "no file set for\n" + osVersion )
							else if (incompatibleReason == 'ROOT_FULL')
								return qsTr ( "no room on root partition" )
						else if (incompatibleReason == 'DATA_FULL')
							return qsTr ( "no room on data partition" )
							else if (incompatibleReason == 'GUI_V1_MISSING')
								return qsTr ( "GUI v1\nnot installed" )
						else
							return qsTr ("incompatible ???" ) // compatible for unknown reason
					}
					else if (rebootNeeded.value == 1)
						return qsTr ("REBOOT:")
					else if (guiRestartNeeded.value == 1)
						return qsTr ("GUI\nRestart:")
					else
						return qsTr ("installed:")
				}
                color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
				horizontalAlignment: Text.AlignRight
				width: incompatible ? 50 + 80 + 3 : 50
                font.pixelSize: 10
            }
            MbTextBlock
            {
                id: installedVersion
                item { bind: getServiceBind("InstalledVersion") }
                height: 25
                width: incompatible ? 0 : 105
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
            id: removeButton
            width: 170
            anchors { right: parent.right; bottom: statusMessage.bottom}
            description: ""
            value: qsTr("Remove package")
            onClicked: remove ()
            writeAccessLevel: User.AccessInstaller
            show: navigate && ! installedValid
        }
        MbOK
        {
            id: cancelButton
            width: 90
            anchors { right: parent.right; bottom: statusMessage.bottom }
            description: ""
            value: qsTr("Cancel")
            onClicked: cancelEdit ()
            show: ! navigate && ! waitForAction
        }
        MbOK
        {
            id: dismissErrorButton
            width: 90
            anchors { right: parent.right; bottom: statusMessage.bottom }
            description: ""
            value: qsTr("OK")
            onClicked: cancelEdit ()
            show: editAction.value == 'ERROR'
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
            width: 375
            anchors { left: parent.left; bottom: statusMessage.bottom }
            description: ""
            value: qsTr ("Proceed")
            onClicked: confirm ()
            show: ! navigate && actionPending
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
            value: qsTr("Uninstall")
            onClicked: uninstall ()
            opacity: navigate && installedValid > 0 ? 1.0 : 0.2
            writeAccessLevel: User.AccessInstaller
        }
		// at bottom so it's not in the middle of hard button cycle
        Text
        {
            id: statusMessage
            width: 250
            wrapMode: Text.WordWrap
            anchors { left: parent.left; leftMargin: 10; top: gitHubBranch.bottom; topMargin: 22 }
            font.pixelSize: 12
            color: actionPending && isSetupHelper ? "red" : root.style.textColor
            text:
            {
				if (actionPending)
				{
					if (isSetupHelper && requestedAction == 'uninstall')
						return qsTr ("WARNING: SetupHelper is required for these menus - uninstall anyway ?")
					else
						return (requestedAction + " " + packageName + " ?")
				}
				else if (editStatus.valid && editStatus.value != "")
					return editStatus.value
				else
					return " "
			}
        }
    }
}
