//////// new for PackageManager

import QtQuick 1.1
import com.victron.velib 1.0
import "utils.js" as Utils

MbItem {
	id: root

	property int packageIndex
	property string servicePrefix
	property string settingsPrefix

    property bool isCurrentItem: root.ListView.isCurrentItem
	property MbStyle style: MbStyle { isCurrentItem: root.ListView.isCurrentItem }

	VBusItem { id: packageName; bind: getSettingsBind ("PackageName") }
    property VBusItem rebootNeededItem: VBusItem { bind: getServiceBind ( "RebootNeeded") }
    property VBusItem guiRestartNeededItem: VBusItem { bind: getServiceBind ( "GuiRestartNeeded") }
    property bool rebootNeeded: rebootNeededItem.valid && rebootNeededItem.value == 1
    property bool guiRestartNeeded: guiRestartNeededItem.valid && guiRestartNeededItem.value == 1

    VBusItem { id: incompatibleItem; bind: getServiceBind ( "Incompatible" ) }
    property string incompatibleReason: incompatibleItem.valid ? incompatibleItem.value : ""
    property bool compatible: incompatibleReason == ""
    VBusItem { id: platformItem; bind: Utils.path("com.victronenergy.packageManager", "/Platform" ) }
    property string platform: platformItem.valid ? platformItem.value : "???"

	// version info may be in platform service or in vePlatform.version
    VBusItem { id: osVersionItem; bind: Utils.path("com.victronenergy.platform", "/Firmware/Installed/Version" ) }
    property string osVersion: osVersionItem.valid ? osVersionItem.value : vePlatform.version

	onClicked: rootWindow.pageStack.push ("/opt/victronenergy/gui/qml/PageSettingsPackageEdit.qml", {packageIndex: packageIndex})


	function statusText ()
	{
		if (rebootNeeded)
			return qsTr ("         REBOOT needed")
		if (guiRestartNeeded)
			return qsTr ("         GUI restart needed")
		else if (incompatibleReason == 'PLATFORM')
			return qsTr ( "  not compatible with " + platform )
		else if (incompatibleReason == 'VERSION')
			return qsTr ( "  not compatible with " + osVersion )
		else if (incompatibleReason == 'CMDLINE' && installedVersion.item.value == "")
			return qsTr ( "  must install from command line" )
		else
			return ""
	}

	function getSettingsBind(param)
	{
		return Utils.path(settingsPrefix, "/", packageIndex, "/", param)
	}
	function getServiceBind(param)
	{
		return Utils.path(servicePrefix, "/Package/", packageIndex, "/", param)
	}

	function versionToNumber (item)
	{
		var parts=["x", "x", "x", "x", "x"]
		var versionNumber = 0

		if (item.valid && item.value.substring  (0,1) == "v")
		{
			parts = item.value.split (/[v.~]+/ , 4)
			{
				if (parts.length >= 2)
					versionNumber += parseInt(parts[1]) * 1000000
				if (parts.length >= 3)
					versionNumber += parseInt(parts[2]) * 1000
				if (parts.length >= 4)
					versionNumber += parseInt(parts[3])
				else
					versionNumber += 999
			}
		}
		return versionNumber
	}

    MbRowSmall
    {
        description: ""

        anchors.verticalCenter: parent.verticalCenter
		Column
		{
			width: root.width - gitHubVersion.width - packageVersion.width - installedVersion.width - 20
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
				text: statusText ()
				color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
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
				text: "GitHub"
				color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
                font.pixelSize: 10
			}
			MbTextBlock
			{
				id: gitHubVersion
				item { bind: getServiceBind("GitHubVersion") }
				height: 20; width: 80
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
				text: qsTr ("Stored")
				color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
                font.pixelSize: 10
			}
			MbTextBlock
			{
				id: packageVersion
				item { bind: getServiceBind("PackageVersion") }
				height: 20; width: 80
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
				text: qsTr ("Installed")
				color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
                font.pixelSize: 10
			}
			MbTextBlock
			{
				id: installedVersion
				item { bind: getServiceBind("InstalledVersion") }
				height: 20; width: 80
			}
		}
    }
}
