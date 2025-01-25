import QtQuick 1.1
import com.victron.velib 1.0
import net.connman 0.1
import "utils.js" as Utils

MbPage {
	title: qsTr("Settings")
	property string bindPrefix: "com.victronenergy.settings"
	property VBusItem relay0Item: VBusItem {bind: "com.victronenergy.system/Relay/0/State"}
	property bool hasRelay0: relay0Item.valid

	model: VisibleItemModel {
		MbSubMenu {
			id: generalItem
			description: qsTr("General")
			subpage: Component {
				PageSettingsGeneral {
					title: generalItem.description
				}
			}
		}

		MbSubMenu {
			description: qsTr("Firmware")
			subpage: Component {
				PageSettingsFirmware {
					title: qsTr("Firmware")
				}
			}
		}

		MbSubMenu {
			description: qsTr("Date & Time")
			subpage: Component {
				PageTzInfo {
					title: qsTr("Date & Time")
				}
			}
		}

		MbSubMenu {
			description: qsTr("Remote Console")
			subpage: Component { PageSettingsRemoteConsole {} }
		}

		MbSubMenu {
			id: systemSetupItem
			description: qsTr("System setup")
			subpage: Component {
				PageSettingsSystem {
					title: systemSetupItem.description
				}
			}
		}

		MbSubMenu {
			id: dvcc
			description: qsTr("DVCC")
			subpage: Component {
				PageSettingsDVCC {
					title: dvcc.description
				}
			}
		}

		MbSubMenu {
			id: displayItem
			description: qsTr("Display & language")
			subpage: Component {
				PageSettingsDisplay {
					title: displayItem.description
				}
			}
		}

		MbSubMenu {
			id: vrmLoggerItem
			description: qsTr("VRM online portal")
			subpage: Component {
				PageSettingsLogger {
					title: vrmLoggerItem.description
				}
			}
		}

		MbSubMenu {
			VBusItem {
				id: systemType
				bind: "com.victronenergy.system/SystemType"
			}
			description: systemType.value === "Hub-4" ? systemType.value : qsTr("ESS")
			subpage: Component { PageSettingsHub4 {} }
		}

		MbSubMenu {
			description: qsTr("Energy meters")
			subpage: Component { PageSettingsCGwacsOverview {} }
		}

		MbSubMenu {
			description: qsTr("PV inverters")
			subpage: Component { PageSettingsFronius {} }
		}

		MbSubMenu {
			show: App.withQwacs
			description: qsTr("Wireless AC sensors")
			subpage: Component { PageSettingsQwacs {} }
		}

		MbSubMenu {
			description: qsTr("Modbus TCP/UDP devices")
			subpage: Component { PageSettingsModbus {} }
		}

		MbSubMenu {
			id: ethernetItem
			description: qsTr("Ethernet")
			subpage: Component { PageSettingsTcpIp { showLinkLocal: true } }
		}

		MbSubMenu {
			description: qsTr("Wi-Fi")
			property VeQuickItem accessPoint: VeQuickItem { uid: "dbus/com.victronenergy.platform/Services/AccessPoint/Enabled" }
			subpage: accessPoint.value !== undefined ? wifiWithAP : wifiWithoutAP
			Component { id: wifiWithoutAP; PageSettingsWifi {} }
			Component { id: wifiWithAP; PageSettingsWifiWithAccessPoint {} }
		}

		MbSubMenu {
			description: qsTr("GSM modem")
			subpage: Component { PageSettingsGsm {} }
		}

		MbSubMenu {
			description: qsTr("Bluetooth")
			subpage: Component { PageSettingsBluetooth {} }
			show: Connman.technologyList.indexOf("bluetooth") !== -1
		}

		MbSubMenu {
			description: qsTr("GPS")
			subpage: Component { PageSettingsGpsList {} }
		}

		MbSubMenu {
			description: qsTr("Generator start/stop")
			subpage: Component { PageRelayGenerator {} }
			show: hasRelay0
		}

		MbSubMenu {
			description: qsTr("Tank pump")
			subpage: Component { PageSettingsTankPump {} }
		}

		MbSubMenu {
			description: qsTr("Relay")
			subpage: Component { PageSettingsRelay {} }
			show: hasRelay0
		}

		MbSubMenu {
			description: qsTr("Services")
			subpage: Component { PageSettingsServices {} }
		}

		MbSubMenu {
			description: qsTr("I/O")
			subpage: ioSettings
			show: ioSettings.haveSubMenus
			PageSettingsIo { id: ioSettings }
		}

		/*
		MbSubMenu {
			description: qsTr("Backup & Restore")
			subpage: Component { PageSettingsBackup {} }
		}
		*/

		MbSubMenu {
			description: qsTr("Venus OS Large features")
			subpage: Component { PageSettingsLarge {} }
			property VBusItem signalK: VBusItem { bind: "com.victronenergy.platform/Services/SignalK/Enabled" }
			property VBusItem nodeRed: VBusItem { bind: "com.victronenergy.platform/Services/NodeRed/Mode" }
			show: signalK.valid || nodeRed.valid
		}

		MbSubMenu {
			description: "Debug"
			subpage: Component { PageDebug {} }
			showAccessLevel: User.AccessService
		}
//////// added for PackageManager
		MbSubMenu
		{
			description: qsTr("Package manager")
			subpage: Component { PageSettingsPackageManager {} }
		}
	}
}
