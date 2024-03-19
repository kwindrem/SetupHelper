/////// new menu for package version display

import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: defaultCount.valid ? qsTr("Active packages (tap to edit)        ") : qsTr ("Package manager not running")
    property string servicePrefix: "com.victronenergy.packageManager"
    property string settingsPrefix: "com.victronenergy.settings/Settings/PackageManager"
    property VBusItem count: VBusItem { bind: Utils.path(settingsPrefix, "/Count") }
	// use DefaultCount as an indication that PackageManager is running
    property VBusItem defaultCount: VBusItem { bind: Utils.path(servicePrefix, "/DefaultCount") }
	property VBusItem editAction: VBusItem { bind: Utils.path(servicePrefix, "/GuiEditAction") }

	// notify PackageManager to refresh GitHub versions for all packages
	// when this menu goes active (entering from parent or returning from child)
	// or if first package's GitHub version age is greater than 60 seconds
	onActiveChanged: refreshGitHubVersions ()

	function refreshGitHubVersions ()
	{
		if (! active)
			return
		else if ( editAction.value != "" )
			return

		editAction.setValue ('gitHubScan:ALL')
	}


	model: defaultCount.valid ? count.valid ? count.value : 0 : 0
    delegate: Component
    {
        MbDisplayPackageVersion
        {
            servicePrefix: root.servicePrefix
            settingsPrefix: root.settingsPrefix
            packageIndex: index
        }
    }
}
