import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import org.kde.kquickcontrols as KQuickControls

KCM.SimpleKCM {
    id: page
    signal configurationChanged

    property alias cfg_showMode: showMode.checked
    property alias cfg_showCpu: showCpu.checked
    property alias cfg_showRam: showRam.checked
    property alias cfg_showFan: showFan.checked
    property alias cfg_showNetwork: showNetwork.checked
    property alias cfg_showBattery: showBattery.checked
    property alias cfg_showCpuCores: showCpuCores.checked
    property alias cfg_autoHideUnavailable: autoHide.checked
    property alias cfg_layoutMode: layoutMode.currentIndex
    property alias cfg_refreshInterval: refreshRate.value
    property alias cfg_temperatureWarning: temperatureWarning.value
    property alias cfg_usageWarning: usageWarning.value
    property alias cfg_storageWarning: storageWarning.value
    property alias cfg_batteryWarning: batteryWarning.value
    property string cfg_gpuIds: ""
    property string cfg_storageIds: ""
    property string cfg_networkIds: ""
    property string cfg_deviceLabels: "{}"
    property string cfg_barColors: "{}"
    property string cfg_rowOrder: "mode,cpu,cores,ram,gpus,storage,fan,network,battery"

    property bool cfg_showModeDefault: true
    property bool cfg_showCpuDefault: true
    property bool cfg_showRamDefault: true
    property bool cfg_showFanDefault: true
    property bool cfg_showNetworkDefault: true
    property bool cfg_showBatteryDefault: true
    property bool cfg_showCpuCoresDefault: false
    property bool cfg_autoHideUnavailableDefault: true
    property int cfg_layoutModeDefault: 0
    property int cfg_refreshIntervalDefault: 5
    property int cfg_temperatureWarningDefault: 80
    property int cfg_usageWarningDefault: 85
    property int cfg_storageWarningDefault: 90
    property int cfg_batteryWarningDefault: 20
    property string cfg_gpuIdsDefault: ""
    property string cfg_storageIdsDefault: ""
    property string cfg_networkIdsDefault: ""
    property string cfg_deviceLabelsDefault: "{}"
    property string cfg_barColorsDefault: "{}"
    property string cfg_rowOrderDefault: "mode,cpu,cores,ram,gpus,storage,fan,network,battery"

    property var telemetryData: ({"gpu_devices": [], "storage_devices": [], "network_interfaces": []})
    property var orderModel: []
    readonly property var rowNames: ({
        "mode": i18n("Power mode"), "cpu": i18n("CPU"), "cores": i18n("CPU cores"),
        "ram": i18n("Memory"), "gpus": i18n("Graphics devices"), "storage": i18n("Storage devices"),
        "fan": i18n("Fans"), "network": i18n("Network"), "battery": i18n("Battery")
    })

    function selected(csv, device, index) {
        if (!csv) return index === 0
        var ids = "," + csv + ","
        return ids.indexOf("," + device.id + ",") >= 0 || (device.legacy_id && ids.indexOf("," + device.legacy_id + ",") >= 0)
    }

    function devicesFor(kind) {
        if (kind === "gpu") return telemetryData.gpu_devices || []
        if (kind === "storage") return telemetryData.storage_devices || []
        return telemetryData.network_interfaces || []
    }

    function csvFor(kind) {
        if (kind === "gpu") return cfg_gpuIds
        if (kind === "storage") return cfg_storageIds
        return cfg_networkIds
    }

    function setCsv(kind, value) {
        if (kind === "gpu") cfg_gpuIds = value
        else if (kind === "storage") cfg_storageIds = value
        else cfg_networkIds = value
        page.configurationChanged()
    }

    function setSelected(kind, device, checked) {
        var value = csvFor(kind)
        var devices = devicesFor(kind)
        var ids = value && value !== "__none__" ? value.split(",").filter(function(item) { return item.length > 0 }) : []
        if (!value && devices.length) ids = [devices[0].id]
        var candidates = [device.id, device.legacy_id || ""]
        ids = ids.filter(function(item) { return candidates.indexOf(item) < 0 })
        if (checked) ids.push(device.id)
        setCsv(kind, ids.length ? ids.join(",") : "__none__")
    }

    function labels() {
        try { return JSON.parse(cfg_deviceLabels || "{}") } catch (error) { return {} }
    }

    function labelFor(id, fallback) {
        var values = labels()
        return values[id] || fallback
    }

    function setLabel(id, value) {
        var values = labels()
        if (value.trim()) values[id] = value.trim().toUpperCase().slice(0, 12)
        else delete values[id]
        cfg_deviceLabels = JSON.stringify(values)
        page.configurationChanged()
    }

    function colors() {
        try { return JSON.parse(cfg_barColors || "{}") } catch (error) { return {} }
    }

    function colorFor(id, fallback) {
        return colors()[id] || fallback
    }

    function setColor(id, value) {
        var values = colors()
        values[id] = value.toString()
        cfg_barColors = JSON.stringify(values)
        page.configurationChanged()
    }

    function updateOrder() {
        orderModel = cfg_rowOrder.split(",").filter(function(key) { return rowNames[key] !== undefined })
    }

    function moveRow(index, delta) {
        var target = index + delta
        if (target < 0 || target >= orderModel.length) return
        var values = orderModel.slice()
        var moved = values.splice(index, 1)[0]
        values.splice(target, 0, moved)
        cfg_rowOrder = values.join(",")
        orderModel = values
        page.configurationChanged()
    }

    function refreshDevices() {
        var xhr = new XMLHttpRequest()
        xhr.open("GET", "http://127.0.0.1:9090/telemetry")
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
                try { telemetryData = JSON.parse(xhr.responseText) } catch (error) {}
            }
        }
        xhr.send()
    }

    function resetAll() {
        showMode.checked = true; showCpu.checked = true; showRam.checked = true
        showFan.checked = true; showNetwork.checked = true; showBattery.checked = true
        showCpuCores.checked = false; autoHide.checked = true; layoutMode.currentIndex = 0
        refreshRate.value = 5; temperatureWarning.value = 80; usageWarning.value = 85
        storageWarning.value = 90; batteryWarning.value = 20
        cfg_gpuIds = ""; cfg_storageIds = ""; cfg_networkIds = ""
        cfg_deviceLabels = "{}"; cfg_barColors = "{}"; cfg_rowOrder = cfg_rowOrderDefault
        updateOrder(); page.configurationChanged()
    }

    Component.onCompleted: { updateOrder(); refreshDevices() }

    Kirigami.FormLayout {
        Controls.ComboBox {
            id: layoutMode
            Kirigami.FormData.label: i18n("Layout:")
            model: [i18n("Detailed"), i18n("Compact")]
        }
        Controls.SpinBox {
            id: refreshRate
            Kirigami.FormData.label: i18n("Refresh interval:")
            from: 1; to: 30
            textFromValue: function(value) { return i18np("%1 second", "%1 seconds", value) }
        }
        Controls.CheckBox {
            id: autoHide
            Kirigami.FormData.label: i18n("Availability:")
            text: i18n("Hide unavailable battery, fan, and device rows")
        }

        ColumnLayout {
            Kirigami.FormData.label: i18n("Visible rows:")
            Controls.CheckBox { id: showMode; text: i18n("Power mode") }
            Controls.CheckBox { id: showCpu; text: i18n("CPU") }
            Controls.CheckBox { id: showCpuCores; text: i18n("Individual CPU cores") }
            Controls.CheckBox { id: showRam; text: i18n("Memory") }
            Controls.CheckBox { id: showFan; text: i18n("Fans") }
            Controls.CheckBox { id: showNetwork; text: i18n("Network") }
            Controls.CheckBox { id: showBattery; text: i18n("Battery") }
        }

        ColumnLayout {
            Kirigami.FormData.label: i18n("Row order:")
            Controls.Label { text: i18n("Drag rows or use the arrow buttons."); color: Kirigami.Theme.disabledTextColor }
            ListView {
                id: orderList
                model: page.orderModel
                Layout.fillWidth: true
                Layout.preferredHeight: contentHeight
                interactive: false
                spacing: 2
                delegate: Item {
                    required property string modelData
                    required property int index
                    property int rowIndex: index
                    width: orderList.width
                    height: 34
                    z: rowDrag.active ? 2 : 0
                    Drag.active: rowDrag.active
                    Drag.source: this
                    Drag.hotSpot.x: width / 2
                    Drag.hotSpot.y: height / 2
                    RowLayout {
                        anchors.fill: parent
                        Kirigami.Icon { source: "handle-sort"; Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
                        Controls.Label { text: page.rowNames[modelData]; Layout.fillWidth: true }
                        Controls.ToolButton { icon.name: "go-up"; enabled: index > 0; onClicked: page.moveRow(index, -1) }
                        Controls.ToolButton { icon.name: "go-down"; enabled: index < page.orderModel.length - 1; onClicked: page.moveRow(index, 1) }
                    }
                    DragHandler { id: rowDrag; target: parent }
                    DropArea {
                        anchors.fill: parent
                        onEntered: function(drag) {
                            if (drag.source && drag.source.rowIndex !== index)
                                page.moveRow(drag.source.rowIndex, index - drag.source.rowIndex)
                        }
                    }
                }
            }
        }

        DeviceSection { kind: "gpu"; heading: i18n("Graphics:"); devices: page.telemetryData.gpu_devices || [] }
        DeviceSection { kind: "storage"; heading: i18n("Storage:"); devices: page.telemetryData.storage_devices || [] }
        DeviceSection { kind: "network"; heading: i18n("Network interfaces:"); devices: page.telemetryData.network_interfaces || [] }

        GridLayout {
            columns: 2
            Kirigami.FormData.label: i18n("Custom labels:")
            Repeater {
                model: [{"id":"cpu","name":"CPU"},{"id":"ram","name":"RAM"},{"id":"fan","name":"FAN"},{"id":"battery","name":"BAT"}]
                delegate: Controls.TextField {
                    required property var modelData
                    placeholderText: modelData.name
                    text: page.labelFor(modelData.id, modelData.name)
                    maximumLength: 12
                    onEditingFinished: page.setLabel(modelData.id, text)
                }
            }
        }

        GridLayout {
            columns: 2
            Kirigami.FormData.label: i18n("Bar colours:")
            Repeater {
                model: [
                    {"id":"mode","name":i18n("Power mode"),"color":"#63dcc8"},
                    {"id":"cpu","name":i18n("CPU and cores"),"color":"#43d17a"},
                    {"id":"ram","name":i18n("Memory"),"color":"#4f93ff"},
                    {"id":"gpu","name":i18n("Dedicated GPU"),"color":"#ffae3d"},
                    {"id":"igpu","name":i18n("Integrated GPU"),"color":"#f28acb"},
                    {"id":"storage","name":i18n("Storage"),"color":"#b16dff"},
                    {"id":"fan","name":i18n("Fans"),"color":"#35c8b5"},
                    {"id":"network","name":i18n("Network"),"color":"#30bdf0"},
                    {"id":"battery","name":i18n("Battery"),"color":"#e6c84d"},
                    {"id":"warning","name":i18n("Warnings"),"color":"#ff4d5e"}
                ]
                delegate: RowLayout {
                    required property var modelData
                    Controls.Label { text: modelData.name; Layout.fillWidth: true }
                    KQuickControls.ColorButton {
                        color: page.colorFor(modelData.id, modelData.color)
                        showAlphaChannel: false
                        dialogTitle: i18n("Choose %1 bar colour", modelData.name)
                        onAccepted: function(color) { page.setColor(modelData.id, color) }
                    }
                }
            }
        }

        Controls.SpinBox { id: temperatureWarning; Kirigami.FormData.label: i18n("Temperature warning:"); from: 40; to: 110; textFromValue: function(value) { return value + " °C" } }
        Controls.SpinBox { id: usageWarning; Kirigami.FormData.label: i18n("Usage warning:"); from: 50; to: 100; textFromValue: function(value) { return value + "%" } }
        Controls.SpinBox { id: storageWarning; Kirigami.FormData.label: i18n("Storage warning:"); from: 50; to: 100; textFromValue: function(value) { return value + "%" } }
        Controls.SpinBox { id: batteryWarning; Kirigami.FormData.label: i18n("Low battery warning:"); from: 5; to: 50; textFromValue: function(value) { return value + "%" } }

        RowLayout {
            Controls.Button { text: i18n("Refresh devices"); icon.name: "view-refresh"; onClicked: page.refreshDevices() }
            Controls.Button { text: i18n("Reset defaults"); icon.name: "edit-undo"; onClicked: page.resetAll() }
        }
    }

    component DeviceSection: ColumnLayout {
        required property string kind
        required property string heading
        required property var devices
        Kirigami.FormData.label: heading
        Repeater {
            model: devices
            delegate: RowLayout {
                required property var modelData
                required property int index
                Controls.CheckBox {
                    checked: page.selected(page.csvFor(kind), modelData, index)
                    text: modelData.name + (modelData.kind ? " — " + modelData.kind : "")
                    Layout.fillWidth: true
                    onToggled: page.setSelected(kind, modelData, checked)
                }
                Controls.TextField {
                    placeholderText: modelData.name
                    text: page.labelFor(modelData.id, modelData.name)
                    maximumLength: 12
                    Layout.preferredWidth: 130
                    onEditingFinished: page.setLabel(modelData.id, text)
                }
            }
        }
        Controls.Label { visible: !devices.length; text: i18n("No devices detected") }
    }
}
