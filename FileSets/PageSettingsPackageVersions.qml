/////// new menu for package version display

import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: defaultCount.valid ? qsTr("Package Version List") : qsTr ("Package Manager not running")
    property string servicePrefix: "com.victronenergy.packageMonitor"
    property string settingsPrefix: "com.victronenergy.settings/Settings/PackageMonitor"
    property VBusItem count: VBusItem { bind: Utils.path(settingsPrefix, "/Count") }
	// use DefaultCount as an indication that PackageMonitor is running
    property VBusItem defaultCount: VBusItem { bind: Utils.path(servicePrefix, "/DefaultCount") }

    model: defaultCount.valid ? count.valid ? count.value : 0 : 0
    delegate: Component
    {
        MbDisplayPackageVersion
        {
            servicePrefix: root.servicePrefix
            settingsPrefix: root.settingsPrefix
            versionIndex: index
        }
    }
}
