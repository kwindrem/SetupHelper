/////// new menu for package version edit

import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: platformItem.valid ? qsTr("Package Editor") : qsTr ("Package Manager not running")
    property string settingsPrefix: "com.victronenergy.settings/Settings/PackageMonitor"
    property string servicePrefix: "com.victronenergy.packageMonitor"
    property int packageIndex: 0
    property int defaultIndex:0
    property VBusItem defaultCountItem: VBusItem { bind: Utils.path(servicePrefix, "/DefaultCount") }
    property int defaultCount: defaultCountItem.valid ? defaultCountItem.value : 0
    property VBusItem packageCountItem: VBusItem { bind: Utils.path(settingsPrefix, "/Count") }
    property int count: packageCountItem.valid ? packageCountItem.value : 0
    property VBusItem editActionItem: VBusItem { bind: Utils.path(servicePrefix, "/GuiEditAction") }
    property string editAction: editActionItem.valid ? editActionItem.value : ""
    property VBusItem editStatus: VBusItem { bind: Utils.path(servicePrefix, "/GuiEditStatus") }

    property VBusItem rebootNeededItem: VBusItem { bind: getServiceBind ( "RebootNeeded") }
    property bool rebootNeeded: rebootNeededItem.valid && rebootNeededItem.value == 1
    property VBusItem incompatibleItem: VBusItem { bind: getServiceBind ( "Incompatible") }
    property string incompatibleReason: incompatibleItem.valid ? incompatibleItem.value : ""
    property bool compatible: incompatibleReason == ""
    property VBusItem platformItem: VBusItem { bind: Utils.path(servicePrefix, "/Platform") }
    property string platform: platformItem.valid ? platformItem.value : "??"

    property bool addPackage: requestedAction == 'Add'  && showControls    
    property bool showControls: editActionItem.valid
    property bool gitHubValid: gitHubVersion.item.valid && gitHubVersion.item.value.substring (0,1) === "v"
    property bool packageValid: packageVersion.item.valid && packageVersion.item.value.substring (0,1) === "v"
    property bool installedValid: installedVersion.item.valid && installedVersion.item.value.substring (0,1) === "v"
    property bool downloadOk: gitHubValid && gitHubVersion.item.value != ""
    property bool installOk: packageValid && packageVersion.item.value  != "" && compatible
    property string requestedAction: ""
    property bool navigate: requestedAction == '' && ! waitForAction && showControls
    property bool waitForAction: editAction != '' && showControls
    property bool moreActions: showControls && editAction == 'RebootNeeded'

    property VBusItem defaultPackageNameItem: VBusItem { bind: Utils.path ( servicePrefix, "/Default/", defaultIndex, "/", "PackageName" ) }
    property VBusItem defaultGitHubUserItem: VBusItem { bind: Utils.path ( servicePrefix, "/Default/", defaultIndex, "/", "GitHubUser" ) }
    property VBusItem defaultGitHubBranchItem: VBusItem { bind: Utils.path ( servicePrefix, "/Default/", defaultIndex, "/", "GitHubBranch" ) }
    property VBusItem editPackageNameItem: VBusItem { bind: Utils.path ( settingsPrefix, "/Edit/", "PackageName" ) }
    property VBusItem editGitHubUserItem: VBusItem { bind: Utils.path ( settingsPrefix, "/Edit/", "GitHubUser" ) }
    property VBusItem editGitHubBranchItem: VBusItem { bind: Utils.path ( settingsPrefix, "/Edit/", "GitHubBranch" ) }

	property string defaultPackageName: defaultPackageNameItem.valid ? defaultPackageNameItem.value : "??"
	property string defaultGitHubUser: defaultGitHubUserItem.valid ? defaultGitHubUserItem.value : "??"
	property string defaultGitHubBranch: defaultGitHubBranchItem.valid ? defaultGitHubBranchItem.value : "??"

	Component.onCompleted: defaultIndex = 0
	onCountChanged: resetPackageIndex ()
	onDefaultCountChanged: resetDefaultIndex ()
	
	function resetPackageIndex ()
	{
		if (packageIndex >= count)
			packageIndex = count - 1
	}
	
	function resetDefaultIndex ()
	{
		if (defaultIndex >= defaultCount)
			defaultIndex = defaultCount - 1
	}
	
	function getSettingsBind(param)
	{
		if (addPackage)
			return Utils.path(settingsPrefix, "/Edit/", param)
		else
			return Utils.path(settingsPrefix, "/", packageIndex, "/", param)
	}
	function getServiceBind(param)
	{
		if (addPackage)
			return Utils.path(servicePrefix, "/Default/", defaultIndex, "/", param)
		else
			return Utils.path(servicePrefix, "/Package/", packageIndex, "/", param)
	}
    
	// copy a set of default package values to Edit area when changing indexes
	function updateEdit ()
	{
		bindPrefix = Utils.path(servicePrefix, "/Default/", defaultIndex )
		editPackageNameItem.setValue ( defaultPackageName )
		editGitHubUserItem.setValue ( defaultGitHubUser )
		editGitHubBranchItem.setValue ( defaultGitHubBranch )
	}

    function nextIndex ()
    {
		if (addPackage)
		{
			defaultIndex += 1
			if (defaultIndex >= defaultCount)
				defaultIndex = defaultCount - 1
			updateEdit ()
		}
		else
			packageIndex += 1
			if (packageIndex >= count)
 							packageIndex = count - 1
   }
    function previousIndex ()
    {
		if (addPackage)
		{
			defaultIndex -= 1
			if (defaultIndex < 0)
				defaultIndex = 0
			updateEdit ()
		}
		else
			packageIndex -= 1
			if (packageIndex < 0)
				packageIndex = 0
    }
    function cancelEdit ()
    {
		requestedAction = ''
		editActionItem.setValue ( '' )
		editStatus.setValue ( '' )
    }
    function confirm ()
    {
        if (requestedAction != '')
        {
            editActionItem.setValue (requestedAction + ':' + packageName.item.value)
			requestedAction = ''
        }
        if (requestedAction == 'Remove')
        {
			previousIndex ()
        }
    }
    function install ()
    {
		requestedAction = 'Install'
    }
    function uninstall ()
    {
		requestedAction = 'Uninstall'
    }
    function gitHubDownload ()
    {
		requestedAction = 'Download'
    }
    function add ()
    {
		requestedAction = 'Add'
    }
    function remove ()
    {
		requestedAction = 'Remove'
    }
    function signalReboot ()
    {
		if (editAction == 'RebootNeeded')
			editActionItem.setValue ( 'Reboot' )
		
		requestedAction = ''
	}

	model: VisualItemModel
    {
        MbEditBox
        {
            id: packageName
            description: qsTr ("Package Name")
            maximumLength: 30
            item.bind: getSettingsBind ("PackageName")
            overwriteMode: false
            writeAccessLevel: User.AccessInstaller
            readonly: ! addPackage
            show: showControls
        }
        MbRowSmall
        {
            description: qsTr ("Versions")
            height: 25
            opacity: addPackage ? .0001 : 1
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
                text: "stored:"
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
                text: rebootNeeded ? "REBOOT\nfor:" : "installed:"
				horizontalAlignment: Text.AlignRight
				width: 50
                font.pixelSize: 10
				show: showControls && compatible
            }
            MbTextBlock
            {
                id: installedVersion
                item { bind: getServiceBind("InstalledVersion") }
                height: 25; width: 80
				show: showControls && compatible
            }
            Text
            {
				id: incompatibleText
				text:
				{
					if (incompatibleReason == 'PLATFORM')
						return ( "not compatible with\n" + platform )
					else if (incompatibleReason == 'VERSION')
						return ( "not compatible with\n" + vePlatform.version )
					else if (incompatibleReason == 'CMDLINE')
						return ( "must install\nfrom command line" )
					else
						return ( "compatible ???" ) // compatible or unknown reason
				}
				horizontalAlignment: Text.AlignHCenter
				width: 50 + 80 + 3
                font.pixelSize: 10
				show: showControls && ! compatible
			}
        }
        MbEditBox
        {
            id: gitHubUser
            description: qsTr ("GitHub User")
            maximumLength: 20
            item.bind: getSettingsBind ("GitHubUser")
            overwriteMode: false
            writeAccessLevel: User.AccessInstaller
			show: showControls
        }
        MbEditBox
        {
            id: gitHubBranch
            description: qsTr ("GitHub Branch or Tag")
            maximumLength: 20
            item.bind: getSettingsBind ("GitHubBranch")
            overwriteMode: false
            writeAccessLevel: User.AccessInstaller
			show: showControls
        }

        // top row of buttons
        MbOK
        {
            id: addButton
            width: 140
            anchors { right: removeButton.left }
            description: ""
            value: qsTr("Add Package")
            onClicked: add ()
            show: navigate
        }
        MbOK
        {
            id: removeButton
            width: 170
            anchors { right: parent.right; bottom: addButton.bottom }
            description: ""
            value: qsTr("Remove Package")
            onClicked: remove ()
            show: navigate && ! installedValid && packageName.item.value != "SetupHelper"
        }
        Text
        {
			id: removeDisabled
            text:
            {
				if (packageName.item.value == "SetupHelper")
					return "SetupHelper uninstall\n CAN NOT BE UNDONE"
				else
					return "can't remove\nwhile installed"
			}
			width: 170
			font.pixelSize:12
            anchors.fill: removeButton
			horizontalAlignment: Text.AlignHCenter
            show: navigate && installedValid
		}
        MbOK
        {
            id: cancelButton
            width: 90
            anchors { right: parent.right; bottom: addButton.bottom }
            description: ""
            value: qsTr("Cancel")
            onClicked: cancelEdit ()
            show: showControls && ! navigate && ! waitForAction
        }
        MbOK
        {
            id: dismissErrorButton
            width: 90
            anchors { right: parent.right; bottom: addButton.bottom }
            description: ""
            value: qsTr("OK")
            onClicked: cancelEdit ()
            show: showControls && editAction == 'ERROR'
        }
        MbOK
        {
            id: laterButton
            width: 90
            anchors { right: parent.right; bottom: addButton.bottom }
            description: ""
            value: qsTr("Later")
            onClicked: cancelEdit ()
            show: moreActions
        }
        MbOK
        {
            id: nowButton
            width: 90
            anchors { right: laterButton.left; bottom: addButton.bottom }
            description: ""
            value: qsTr("Now")
            onClicked: signalReboot ()
            show: moreActions
        }
        MbOK
        {
            id: confirmButton
            width: 375
            anchors { left: parent.left; bottom: addButton.bottom }
            description: ""
            value:
            {
				if (packageName.item.value == "SetupHelper" && requestedAction == 'Uninstall')
					var warning = qsTr(" CAN'T UNDO")
				else
					var warning = ""
				return qsTr( "Confirm " + requestedAction + " " + packageName.item.value + warning )
            }
            onClicked: confirm ()
            show: showControls && ! navigate && requestedAction != ""
        }
        Text
        {
            id: statusMessage
            width: 300
            anchors { left: parent.left; leftMargin: 10; bottom: addButton.bottom; bottomMargin: 10 }
            font.pixelSize: 12
            text: editStatus.valid ? editStatus.value : ""
            show: waitForAction 
        }

        // bottom row of buttons
        MbOK
        {
            id: previousButton
            width: addPackage ? 230 : 100
            anchors { left: parent.left ; top:addButton.bottom }
            description: addPackage ? "Import Default" : ""
            value: (addPackage && defaultIndex <= 0) || ( ! addPackage && packageIndex <= 0) ? qsTr ("First") : qsTr("Previous")
            onClicked: previousIndex ()
            show: showControls && ( ! addPackage && packageIndex > 0)
        }
        MbOK
        {
            id: nextButton
            width: 75
            anchors { left: previousButton.right; bottom: previousButton.bottom }
            description: ""
            value: (addPackage && defaultIndex >= defaultCount - 1) || ( ! addPackage && packageIndex >= count - 1) ? qsTr ("Last") : qsTr("Next")
            onClicked: nextIndex ()
            show: showControls && ( ! addPackage && packageIndex < count - 1)
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
        }
    }
}
