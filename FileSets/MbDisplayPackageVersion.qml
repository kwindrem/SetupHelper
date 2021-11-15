import QtQuick 1.1
import com.victron.velib 1.0
import "utils.js" as Utils

MbItem {
	id: root
/////////////	height: 30

	property int versionIndex
	property string bindPrefix

	function getBind(param)
	{
		return Utils.path(bindPrefix, "/", versionIndex, "/", param)
	}

    VBusItem { id: packageName; bind: getBind ("PackageName") }
    VBusItem { id: packageVersion; bind: getBind ("PackageVersion") }

    MbItemValue
    {
        description: packageName.valid ? packageName.value : ""
        item.bind: getBind ("PackageVersion")
        show: item.valid && packageName.valid
    }
}
