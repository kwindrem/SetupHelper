/////// new menu for package version display

import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: qsTr("Package Version List")
    property string bindPrefix: "com.victronenergy.settings/Settings/PackageVersion"
    property VBusItem count: VBusItem { bind: Utils.path(bindPrefix, "/Count") }

    model: count.valid ? count.value : 0
    delegate: Component
    {
        MbDisplayPackageVersion
        {
            bindPrefix: root.bindPrefix
            versionIndex: index
        }
    }
}
