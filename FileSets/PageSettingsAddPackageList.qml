/////// new menu for package version display

import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: defaultCount.valid ? qsTr("Inactive packages (tap to activate)         ") : qsTr ("Package manager not running")

    property string servicePrefix: "com.victronenergy.packageManager"
	// use DefaultCount as an indication that PackageManager is running
    property VBusItem defaultCount: VBusItem { bind: Utils.path(servicePrefix, "/DefaultCount") }

    model: defaultCount.valid ? defaultCount.value : 0
    delegate: Component
    {
        MbDisplayDefaultPackage
        {
            servicePrefix: root.servicePrefix
            defaultIndex: index
        }
    }
}
