//////// new for PackageManager

import QtQuick 1.1
import com.victron.velib 1.0
import "utils.js" as Utils

MbItem
{
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

	property VBusItem installedVersionItem: VBusItem { bind: getServiceBind ("InstalledVersion") }
	property string installedVersion: installedVersionItem.valid ? installedVersionItem.text : ""
	property bool installedValid: installedVersion != "" && installedVersion != "--"

	onClicked: pageStack.push ("/opt/victronenergy/gui/qml/PageSettingsPackageEdit.qml", {newPackageIndex: packageIndex})


	function statusText ()
	{
		if (rebootNeeded)
			return qsTr ("REBOOT needed")
		if (guiRestartNeeded)
			return qsTr ("GUI restart needed")
		else if (incompatibleReason == 'PLATFORM')
			return qsTr ( "incompatible with " + platform )
		// don't show warning incompatibilities here - they are shown in the editor menu	
		else if (incompatibleReason != ""
				&& incompatibleReason.toLowerCase().indexOf ("warning") == -1 )
			return incompatibleReason
		else if (installedValid)
			return installedVersion + qsTr (" installed")
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

	// needed to make list elements the correct size !!!
	height: versionColumn.height + 2
    Row
    {
		leftPadding: 3
		Column
		{
			width: root.width - versionColumn.width - 6;
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
				width: parent.width
				wrapMode: Text.Wrap
			}
		}
		Column
		{
			id: versionColumn
			Row
			{
				height: 23
				spacing: 3
				anchors.right: parent.right
				Text
				{
					text: "GitHub:"
					color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
					font.pixelSize: 9
					anchors.verticalCenter: parent.verticalCenter 
				}
				MbTextBlock
				{
					id: gitHubVersion
					item { bind: getServiceBind("GitHubVersion") }
					height: 20; width: 200
					anchors.verticalCenter: parent.verticalCenter 
				}
			}
			Row
			{
				height: 23
				spacing: 3
				anchors.right: parent.right
				Text
				{
					text: qsTr ("Stored:")
					color: isCurrentItem ? root.style.textColorSelected : root.style.textColor
					font.pixelSize: 9
					anchors.verticalCenter: parent.verticalCenter 
				}
				MbTextBlock
				{
					id: packageVersion
					item { bind: getServiceBind("PackageVersion") }
					height: 20; width: 200
					anchors.verticalCenter: parent.verticalCenter 
				}
			}
		}
	}
}
