//////// PackageManager gui-v2 plugin
// values and commands shared by all PackageManager pages
//
// PackageManager publishes its state in com.victronenergy.packageManager
// and keeps the package list in com.victronenergy.settings /Settings/PackageManager
// the GUI requests an action by writing "action:packageName" to /GuiEditAction
// PackageManager sets /GuiEditAction back to "" when the action is done, or to "ERROR"

import QtQuick
import Victron.GuiPlugins

QtObject {
	id: root

	readonly property string settingsPath: "/Settings/PackageManager"

	readonly property PluginDataItem pmStatusItem: PluginDataItem {
		serviceType: "packageManager"
		path: "/PmStatus"
	}
	readonly property PluginDataItem editActionItem: PluginDataItem {
		serviceType: "packageManager"
		path: "/GuiEditAction"
	}
	readonly property PluginDataItem editStatusItem: PluginDataItem {
		serviceType: "packageManager"
		path: "/GuiEditStatus"
	}
	readonly property PluginDataItem actionNeededItem: PluginDataItem {
		serviceType: "packageManager"
		path: "/ActionNeeded"
	}

	// PackageManager publishes /PmStatus while it is running
	readonly property bool running: pmStatusItem.valid
	readonly property string pmStatus: stringValue (pmStatusItem)

	readonly property bool editActionValid: editActionItem.valid
	readonly property string editAction: stringValue (editActionItem)
	readonly property string editStatus: stringValue (editStatusItem)
	readonly property bool editError: editAction === "ERROR"
	// PackageManager is working on an earlier command
	readonly property bool busy: editAction !== "" && ! editError
	// a new command can be sent
	readonly property bool idle: running && editActionValid && editAction === ""

	// text such as "GuiMods requires REBOOT\nREBOOT system ?" or "... restart GUI ?"
	readonly property string actionNeeded: stringValue (actionNeededItem)
	readonly property bool rebootNeeded: actionNeeded.indexOf ("REBOOT") !== -1
	readonly property bool guiRestartNeeded: ! rebootNeeded && actionNeeded.indexOf ("restart") !== -1

	function stringValue (item)
	{
		if (! item.valid || item.value === undefined || item.value === null)
			return ""
		return String (item.value)
	}

	// send a command to PackageManager
	// statusText (optional) is shown in /GuiEditStatus until PackageManager replaces it
	// returns false if PackageManager is still busy or an error has not been acknowledged
	function send (command, statusText)
	{
		if (! idle)
			return false
		if (statusText !== undefined && statusText !== "")
			editStatusItem.setValue (statusText)
		editActionItem.setValue (command)
		return true
	}

	// clear an error reported by PackageManager and its status message
	function acknowledgeError ()
	{
		if (editError)
		{
			editActionItem.setValue ("")
			editStatusItem.setValue ("")
		}
	}
}
