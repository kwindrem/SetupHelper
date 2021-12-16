import QtQuick 1.1
import com.victron.velib 1.0
import "utils.js" as Utils

MbItem {
	id: root

	property int versionIndex
	property string servicePrefix
	property string settingsPrefix

    VBusItem { id: packageName; bind: getSettingsBind ("PackageName") }
    property VBusItem rebootNeededItem: VBusItem { bind: getServiceBind ( "RebootNeeded") }
    property bool rebootNeeded: rebootNeededItem.valid && rebootNeededItem.value == 1

    VBusItem { id: platformItem; bind: Utils.path("com.victronenergy.packageMonitor", "/Platform" ) }
    VBusItem { id: incompatibleItem; bind: getServiceBind ( "Incompatible" ) }
    property string incompatibleReason: incompatibleItem.valid ? incompatibleItem.value : ""
    property bool compatible: incompatibleReason == ""
    property string platform: platformItem.valid ? platformItem.value : "??"


	function statusText ()
	{
		if (rebootNeeded)
			return ("         REBOOT needed")
		else if (incompatibleReason == 'PLATFORM')
			return ( "not compatible with " + platform )
		else if (incompatibleReason == 'VERSION')
			return ( "not compatible with " + vePlatform.version )
		else if (incompatibleReason == 'CMDLINE' && installedVersion.item.value == "")
			return ( "must install from command line" )
		else
			return ""
	}

	function getSettingsBind(param)
	{
		return Utils.path(settingsPrefix, "/", versionIndex, "/", param)
	}
	function getServiceBind(param)
	{
		return Utils.path(servicePrefix, "/Package/", versionIndex, "/", param)
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
				font.pixelSize: 14
				horizontalAlignment: Text.AlignLeft
			}
			Text
			{
				text: statusText ()
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
				text: "Stored"
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
				text: "Installed"
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
