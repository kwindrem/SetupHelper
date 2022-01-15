/////// new menu for package version edit

import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: platform.valid ? qsTr("Package editor") : qsTr ("Package manager not running")
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
    property VBusItem incompatibleReason: VBusItem { bind: getServiceBind ( "Incompatible") }
    property VBusItem platform: VBusItem { bind: Utils.path(servicePrefix, "/Platform") }

    property bool showControls: editAction.valid
    property bool gitHubValid: gitHubVersion.item.valid && gitHubVersion.item.value.substring (0,1) === "v"
    property bool packageValid: packageVersion.item.valid && packageVersion.item.value.substring (0,1) === "v"
    property bool installedValid: installedVersion.item.valid && installedVersion.item.value.substring (0,1) === "v"
    property bool downloadOk: gitHubValid && gitHubVersion.item.value != ""
    property bool installOk: packageValid && packageVersion.item.value  != "" && incompatibleReason.value == ""
    property string requestedAction: ''
    property bool actionPending: requestedAction != ''
    property bool navigate: ! actionPending && ! waitForAction && showControls
    property bool waitForAction: showControls && editAction.value != ''
    property bool moreActions: showControls && (editAction.value == 'RebootNeeded' || editAction.value == 'GuiRestartNeeded')

    property VBusItem defaultPackageName: VBusItem { bind: Utils.path ( servicePrefix, "/Default/", defaultIndex, "/", "PackageName" ) }
    property VBusItem defaultGitHubUser: VBusItem { bind: Utils.path ( servicePrefix, "/Default/", defaultIndex, "/", "GitHubUser" ) }
    property VBusItem defaultGitHubBranch: VBusItem { bind: Utils.path ( servicePrefix, "/Default/", defaultIndex, "/", "GitHubBranch" ) }
    property VBusItem editPackageName: VBusItem { bind: Utils.path ( settingsPrefix, "/Edit/", "PackageName" ) }
    property VBusItem editGitHubUser: VBusItem { bind: Utils.path ( settingsPrefix, "/Edit/", "GitHubUser" ) }
    property VBusItem editGitHubBranch: VBusItem { bind: Utils.path ( settingsPrefix, "/Edit/", "GitHubBranch" ) }


	Component.onCompleted:
	{
		resetPackageIndex ()
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
		packageIndex += 1
		if (packageIndex >= packageCount.value)
						packageIndex = packageCount.value - 1
   }
    function previousIndex ()
    {
		packageIndex -= 1
		if (packageIndex < 0)
			packageIndex = 0
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
		requestedAction = 'install'
    }
    function uninstall ()
    {
		requestedAction = 'uninstall'
    }
    function gitHubDownload ()
    {
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

	model: VisualItemModel
    {
        MbEditBox
        {
            id: packageNameBox
            description: qsTr ("Package name")
            maximumLength: 30
            item.bind: getSettingsBind ("PackageName")
            overwriteMode: false
            writeAccessLevel: User.AccessInstaller
            readonly: true
            show: showControls
        }
        MbRowSmall
        {
            description: qsTr ("Versions")
            height: 25
            Text
            {
                text: "GitHub:"
                font.pixelSize: 10
				show: showControls
            }
			show: showControls
            MbTextBlock
            {
                id: gitHubVersion
                item { bind: getServiceBind("GitHubVersion") }
                height: 25; width: 80
				show: showControls
            }
            Text
            {
                text: qsTr ("stored:")
                font.pixelSize: 10
				show: showControls
            }
            MbTextBlock
            {
                id: packageVersion
                item { bind: getServiceBind("PackageVersion") }
                height: 25; width: 80
				show: showControls
            }
            Text
            {
                text:
                {
					if (rebootNeeded.value == 1)
						return qsTr ("REBOOT:")
					else if (guiRestartNeeded.value == 1)
						return qsTr ("GUI\nRestart:")
					else
						return qsTr ("installed:")
				}
				horizontalAlignment: Text.AlignRight
				width: 50
                font.pixelSize: 10
				show: showControls && incompatibleReason.value == ""
            }
            MbTextBlock
            {
                id: installedVersion
                item { bind: getServiceBind("InstalledVersion") }
                height: 25; width: 80
				show: showControls && incompatibleReason.value == ""
            }
            Text
            {
				id: incompatibleText
				text:
				{
					if (incompatibleReason.value == 'PLATFORM')
						return ( qsTr ("not compatible with\n") + platformItem.value )
					else if (incompatibleReason.value == 'VERSION')
						return ( qsTr ("not compatible with\n") + vePlatform.version )
					else if (incompatibleReason.value == 'CMDLINE')
						return qsTr ("must install\nfrom command line" )
					else
						return qsTr ("compatible ???" ) // compatible for unknown reason
				}
				horizontalAlignment: Text.AlignHCenter
				width: 50 + 80 + 3
                font.pixelSize: 10
				show: showControls && ! incompatibleReason.value == ""
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
			show: showControls
        }
        MbEditBox
        {
            id: gitHubBranch
            description: qsTr ("GitHub branch or tag")
            maximumLength: 20
            item.bind: getSettingsBind ("GitHubBranch")
            overwriteMode: false
            writeAccessLevel: User.AccessInstaller
			show: showControls
        }
        MbOK
        {
            id: removeButton
            width: 170
            anchors { right: parent.right}
            description: ""
            value: qsTr("Remove package")
            onClicked: remove ()
            writeAccessLevel: User.AccessInstaller
            opacity:  installedValid ? 0.0001 : 1.0
            show: navigate
        }
        MbOK
        {
            id: cancelButton
            width: 90
            anchors { right: parent.right; bottom: removeButton.bottom }
            description: ""
            value: qsTr("Cancel")
            onClicked: cancelEdit ()
            show: showControls && ! navigate && ! waitForAction
        }
        MbOK
        {
            id: dismissErrorButton
            width: 90
            anchors { right: parent.right; bottom: removeButton.bottom }
            description: ""
            value: qsTr("OK")
            onClicked: cancelEdit ()
            show: showControls && editAction.value == 'ERROR'
        }
        MbOK
        {
            id: laterButton
            width: 90
            anchors { right: parent.right; bottom: removeButton.bottom }
            description: ""
            value: qsTr("Later")
            onClicked: cancelEdit ()
            show: moreActions
        }
        MbOK
        {
            id: nowButton
            width: 90
            anchors { right: laterButton.left; bottom: removeButton.bottom }
            description: ""
            value: qsTr("Now")
            onClicked: signalAdditionalAction ()
            show: moreActions
        }
        MbOK
        {
            id: confirmButton
            width: 375
            anchors { left: parent.left; bottom: removeButton.bottom }
            description: ""
            value: qsTr ("Proceed")
            onClicked: confirm ()
            show: showControls && ! navigate && actionPending
            writeAccessLevel: User.AccessInstaller
        }
        Text
        {
            id: statusMessage
            width: 250
            wrapMode: Text.WordWrap
            anchors { left: parent.left; leftMargin: 10; bottom: removeButton.bottom; bottomMargin: 5 }
            font.pixelSize: 12
            color: actionPending && isSetupHelper ? "red" : "black"
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
					return ""
			}
            show: waitForAction || actionPending
        }

        // bottom row of buttons
        MbOK
        {
            id: previousButton
            width: 100
            anchors { left: parent.left ; top:removeButton.bottom }
            description: ""
            value: qsTr("Previous")
            onClicked: previousIndex ()
            show:
            {
				if (! showControls)
					return false
				else if (packageIndex > 0)
					return true
				else
					return false
			}
        }
        MbOK
        {
            id: nextButton
            width: 75
            anchors { left: previousButton.right; bottom: previousButton.bottom }
            description: ""
            value: qsTr("Next")
            onClicked: nextIndex ()
            show:
            {
				if (! showControls)
					return false
				else if (packageIndex < packageCount.value - 1)
					return true
				else
					return false
			}
        }
        MbOK
        {
            id: downloadButton
            width: 110
            anchors { right: installButton.left; bottom: previousButton.bottom }
            description: ""
            value: qsTr ("Download")
			onClicked: gitHubDownload ()
			show: navigate && downloadOk
            writeAccessLevel: User.AccessInstaller
        }
        MbOK
        {
            id: installButton
            width: 90
            anchors { right: uninstallButton.left; bottom: previousButton.bottom }
            description: ""
            value: qsTr ("Install")
            onClicked: install ()
            show: navigate && installOk 
            writeAccessLevel: User.AccessInstaller
        }
        MbOK
        {
            id: uninstallButton
            width: 100
            anchors { right: parent.right; bottom: installButton.bottom }
            description: ""
            value: qsTr("Uninstall")
            onClicked: uninstall ()
            show: navigate && installedValid
            writeAccessLevel: User.AccessInstaller
        }
    }
}
