import QtQuick 1.1
import com.victron.velib 1.0
import "utils.js" as Utils

MbItem {
	id: root

	property int versionIndex
	property string bindPrefix

	function getBind(param)
	{
		return Utils.path(bindPrefix, "/", versionIndex, "/", param)
	}

    VBusItem { id: packageName; bind: getBind ("PackageName") }

    MbRowSmall
    {
        anchors.verticalCenter: parent.verticalCenter
        height: 20
    
        isCurrentItem: root.isCurrentItem
        description: packageName.valid ? packageName.value : ""
        MbTextBlock
        {
            id: gitUser
            item { bind: getBind("GitHubUser") }
            width: 100
            show: packageName.valid && item.valid
        }
        MbTextBlock
        {
            item { bind: getBind("GitHubBranch") }
            show: packageName.valid && gitUser.item.valid
            width: 80
        }
        MbTextBlock
        {
            item { bind: getBind("PackageVersion") }
            width: 80
            show: packageName.valid
        }
    }
}
