//////// new for PackageManager

import QtQuick 1.1
import com.victron.velib 1.0
import "utils.js" as Utils

MbItem {
	id: root

	property int defaultIndex
	property string servicePrefix

    property bool isCurrentItem: root.ListView.isCurrentItem
	property MbStyle style: MbStyle { isCurrentItem: root.ListView.isCurrentItem }

    VBusItem { id: packageName; bind: getServiceBind ("PackageName") }


	onClicked: rootWindow.pageStack.push ("/opt/victronenergy/gui/qml/PageSettingsPackageAdd.qml", {defaultIndex: defaultIndex})


	function getServiceBind(param)
	{
		return Utils.path(servicePrefix, "/Default/", defaultIndex, "/", param)
	}


    MbRowSmall
    {
        description: ""

        anchors.verticalCenter: parent.verticalCenter
		Column
		{
			width: root.width - gitHubUser.width - gitHubBranch.width - 20
			Text // puts a bit of space above package name
			{
				text: " "
                font.pixelSize: 6
			}
			Text
			{
				text:packageName.valid ? packageName.value : ""
				color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
				font.pixelSize: 14
				horizontalAlignment: Text.AlignLeft
			}
			Text
			{
				text: ""
				font.pixelSize: 10
				horizontalAlignment: Text.AlignLeft
			}
		}
		Column
		{
			Text // puts a bit of space above version boxes
			{
				text: " "
                font.pixelSize: 3
			}
			Text
			{
				text: "GitHub User"
				color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
                font.pixelSize: 10
			}
			MbTextBlock
			{
				id: gitHubUser
				item { bind: getServiceBind("GitHubUser") }
				height: 20; width: 120
			}
			Text // puts a bit of space below version boxes - only needed in one column
			{
				text: " "
                font.pixelSize: 6
			}
        }
		Column
		{
			Text // puts a bit of space above version boxes
			{
				text: " "
                font.pixelSize: 3
			}
			Text
			{
				text: qsTr ("GitHub Tag")
				color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
                font.pixelSize: 10
			}
			MbTextBlock
			{
				id: gitHubBranch
				item { bind: getServiceBind("GitHubBranch") }
				height: 20; width: 120
			}
		}
    }
}
