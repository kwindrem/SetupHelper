/////// new menu for package add edit

import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: editActionItem.valid ? qsTr("Add package") : qsTr ("Package manager not running")

    property bool isCurrentItem: root.ListView.isCurrentItem
	property MbStyle style: MbStyle { isCurrentItem: root.ListView.isCurrentItem }

    property string settingsPrefix: "com.victronenergy.settings/Settings/PackageManager"
    property string servicePrefix: "com.victronenergy.packageManager"
    property int defaultIndex:0
    property VBusItem defaultCount: VBusItem { bind: Utils.path(servicePrefix, "/DefaultCount") }
    property VBusItem editActionItem: VBusItem { bind: Utils.path(servicePrefix, "/GuiEditAction") }
    property VBusItem editStatus: VBusItem { bind: Utils.path(servicePrefix, "/GuiEditStatus") }
    property string packageName: packageNameBox.item.valid ? packageNameBox.item.value : ""
    property string editAction: editActionItem.valid ? editActionItem.value : ''

    property VBusItem defaultPackageName: VBusItem { bind: Utils.path ( servicePrefix, "/Default/", defaultIndex, "/", "PackageName" ) }
    property VBusItem defaultGitHubUser: VBusItem { bind: Utils.path ( servicePrefix, "/Default/", defaultIndex, "/", "GitHubUser" ) }
    property VBusItem defaultGitHubBranch: VBusItem { bind: Utils.path ( servicePrefix, "/Default/", defaultIndex, "/", "GitHubBranch" ) }
    property VBusItem editPackageName: VBusItem { bind: Utils.path ( settingsPrefix, "/Edit/", "PackageName" ) }
    property VBusItem editGitHubUser: VBusItem { bind: Utils.path ( settingsPrefix, "/Edit/", "GitHubUser" ) }
    property VBusItem editGitHubBranch: VBusItem { bind: Utils.path ( settingsPrefix, "/Edit/", "GitHubBranch" ) }
	property bool addPending: false
	property bool entryValid: editPackageName.value != "" && editGitHubUser.value != "" && editGitHubBranch.value != ""

	Component.onCompleted:
	{
		updateEdit ()
	}

	onEditActionChanged:
	{
		if (addPending && editAction == '')
		{
			addPending = false
			pageStack.pop()
		}
	}

	function getSettingsBind(param)
	{
		return Utils.path(settingsPrefix, "/Edit/", param)
	}
	function getServiceBind(param)
	{
		return Utils.path(servicePrefix, "/Default/", defaultIndex, "/", param)
	}

	// copy a set of default package values to Edit area when changing indexes
	function updateEdit ()
	{
		bindPrefix = Utils.path(servicePrefix, "/Default/", defaultIndex )
		var defaultName = defaultPackageName.valid ? defaultPackageName.value : "??"
		if (defaultName == "new")
			defaultName = ""
		editPackageName.setValue ( defaultName )
		editGitHubUser.setValue ( defaultGitHubUser.valid ? defaultGitHubUser.value : "??" )
		editGitHubBranch.setValue ( defaultGitHubBranch.valid ? defaultGitHubBranch.value : "??" )
		editStatus.setValue ("")
		editActionItem.setValue ("")
		addPending = false
	}

    function cancelEdit ()
    {
		addPending = false
		if (editAction == '')
			pageStack.pop()
		else
		{
			editStatus.setValue ("")
			editActionItem.setValue ("")
		}
	}
    function confirm ()
    {
		if (entryValid)
		{
			addPending = true
			// provide local confirmation of action - takes PackageManager too long
			editStatus.setValue ( "adding " + packageName)
			editActionItem.setValue ('add:' + packageName)
		}
    }
	model: VisibleItemModel
    {
        MbEditBox
        {
            id: packageNameBox
            description: qsTr ("Package name")
            maximumLength: 30
            item.bind: getSettingsBind ("PackageName")
            overwriteMode: false
            writeAccessLevel: User.AccessInstaller
        }
        MbEditBox
        {
            id: gitHubUserBox
            description: qsTr ("GitHub user")
            maximumLength: 20
            item.bind: getSettingsBind ("GitHubUser")
            overwriteMode: false
            writeAccessLevel: User.AccessInstaller
        }
        MbEditBox
        {
            id: gitHubBranchBox
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
            anchors { right: parent.right  }
            description: ""
            value: editAction == '' ? qsTr("Cancel") : qsTr("OK")
            onClicked: cancelEdit ()
        }
        MbOK
        {
            id: proceedButton
            width: 100
            anchors { right: cancelButton.left; bottom: cancelButton.bottom }
            description: ""
            value: qsTr ("Proceed")
            onClicked: confirm ()
            show: editAction == '' && entryValid
            writeAccessLevel: User.AccessInstaller
        }
        Text
        {
            id: statusMessage
            width: 250
            wrapMode: Text.WordWrap
            anchors { left: parent.left; leftMargin: 10; bottom: cancelButton.bottom; bottomMargin: 5 }
            font.pixelSize: 12
            text:
            {
				if (editStatus.valid && editStatus.value != "")
					return editStatus.value
				else if (entryValid)
					return ("add " + packageName + " ?")
				else if (editPackageName.value == "")
					return ("enter package name")
				else if (editGitHubUser.value == "")
					return ("enter GitHub user")
				else if (editGitHubBranch.value == "")
					return ("enter GitHub branch")
				else
					return ("")
			}
            color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
        }
    }
}
