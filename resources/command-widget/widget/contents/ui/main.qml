import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.plasma.plasmoid

PlasmoidItem {
    id: root
    width: 760
    height: 306
    implicitWidth: 360
    implicitHeight: Math.max(120, contentColumn.implicitHeight + 20)

    property var telemetryData: ({})
    property var displayRows: []
    property double lastSuccessMs: 0
    property bool requestRunning: false
    property bool telemetryStale: lastSuccessMs === 0 || Date.now() - lastSuccessMs > Math.max(Plasmoid.configuration.refreshInterval, 1) * 2500
    readonly property bool compact: Plasmoid.configuration.layoutMode === 1

    function clamp(value, min, max) { return Math.max(min, Math.min(max, value)) }
    function percent(value) { return clamp(parseFloat(value) || 0, 0, 100) }
    function number(value) { return parseFloat(value) || 0 }
    function tempText(value) { var temp = number(value); return temp > 0 ? Math.round(temp) + "C" : "n/a" }
    function tempColor(value) {
        var temp = number(value)
        if (temp <= 0) return "#666b73"
        if (temp >= Plasmoid.configuration.temperatureWarning) return "#ff4d5e"
        if (temp >= Plasmoid.configuration.temperatureWarning - 10) return "#ffd24a"
        return "#42d66f"
    }
    function modeColor(value) {
        if (value === "performance") return "#ff6b5f"
        if (value === "balanced") return "#63dcc8"
        if (value === "power-saver") return "#43d17a"
        return "#a8b0bc"
    }
    function colors() {
        try { return JSON.parse(Plasmoid.configuration.barColors || "{}") } catch (error) { return {} }
    }
    function barColor(id, fallback) { return colors()[id] || fallback }
    function usageColor(value, normal) {
        return percent(value) >= Plasmoid.configuration.usageWarning ? barColor("warning", "#ff4d5e") : normal
    }
    function labels() {
        try { return JSON.parse(Plasmoid.configuration.deviceLabels || "{}") } catch (error) { return {} }
    }
    function rowLabel(id, fallback, legacyId) {
        var values = labels()
        return values[id] || (legacyId ? values[legacyId] : "") || fallback
    }
    function selected(csv, device, index) {
        if (!csv) return index === 0
        var ids = "," + csv + ","
        return ids.indexOf("," + device.id + ",") >= 0 || (device.legacy_id && ids.indexOf("," + device.legacy_id + ",") >= 0)
    }
    function addRow(rows, data) {
        data.visible = data.visible === undefined ? true : data.visible
        if (data.visible) rows.push(data)
    }
    function rowsForGroup(group) {
        var d = telemetryData
        var rows = []
        var autoHide = Plasmoid.configuration.autoHideUnavailable
        if (group === "mode" && Plasmoid.configuration.showMode) {
            addRow(rows, {"id":"mode", "title":"MODE", "value":d.power_profile_label || "Unknown", "detail":telemetryStale ? "OFFLINE" : "LIVE", "progress":100, "color":barColor("mode", modeColor(d.power_profile)), "detailColor":telemetryStale ? barColor("warning", "#ff4d5e") : modeColor(d.power_profile), "tooltip":"Current system power profile"})
        } else if (group === "cpu" && Plasmoid.configuration.showCpu) {
            addRow(rows, {"id":"cpu", "title":rowLabel("cpu", "CPU"), "value":percent(d.cpu_usage).toFixed(1) + "%  " + (d.cpu_frequency || "n/a"), "detail":tempText(d.cpu_temp), "progress":percent(d.cpu_usage), "color":usageColor(d.cpu_usage, barColor("cpu", "#43d17a")), "detailColor":tempColor(d.cpu_temp), "tooltip":"Total CPU usage, average frequency, and hottest reported temperature"})
        } else if (group === "cores" && Plasmoid.configuration.showCpuCores) {
            var cores = d.cpu_cores || []
            for (var c = 0; c < cores.length; c++) addRow(rows, {"id":cores[c].id, "title":cores[c].name, "value":percent(cores[c].usage).toFixed(1) + "%", "detail":"CORE", "progress":percent(cores[c].usage), "color":usageColor(cores[c].usage, barColor("cpu", "#43d17a")), "detailColor":"#8be0ae", "tooltip":"Individual logical CPU core utilization"})
        } else if (group === "ram" && Plasmoid.configuration.showRam) {
            addRow(rows, {"id":"ram", "title":rowLabel("ram", "RAM"), "value":d.ram_info || "n/a", "detail":percent(d.ram_usage).toFixed(1) + "%", "progress":percent(d.ram_usage), "color":usageColor(d.ram_usage, barColor("ram", "#4f93ff")), "detailColor":"#6aa7ff", "tooltip":"Used and total system memory"})
        } else if (group === "gpus") {
            var gpus = d.gpu_devices || []
            for (var g = 0; g < gpus.length; g++) if (selected(Plasmoid.configuration.gpuIds, gpus[g], g)) {
                var gpu = gpus[g]
                var fallback = gpu.kind && gpu.kind.indexOf("Integrated") >= 0 ? "iGPU" : "GPU"
                var gpuColor = fallback === "iGPU" ? barColor("igpu", "#f28acb") : barColor("gpu", "#ffae3d")
                addRow(rows, {"id":gpu.id, "title":rowLabel(gpu.id, fallback, gpu.legacy_id), "value":percent(gpu.usage).toFixed(0) + "%  VRAM " + gpu.vram, "detail":tempText(gpu.temp), "progress":percent(gpu.usage), "color":usageColor(gpu.usage, gpuColor), "detailColor":tempColor(gpu.temp), "tooltip":gpu.name + "\n" + gpu.kind + "\nVRAM " + gpu.vram})
            }
        } else if (group === "storage") {
            var disks = d.storage_devices || []
            for (var s = 0; s < disks.length; s++) if (selected(Plasmoid.configuration.storageIds, disks[s], s)) {
                var disk = disks[s]
                var diskWarn = percent(disk.percent) >= Plasmoid.configuration.storageWarning || disk.health === "Warning"
                addRow(rows, {"id":disk.id, "title":rowLabel(disk.id, disk.name), "value":disk.usage, "detail":compact ? percent(disk.percent).toFixed(0) + "%" : "R " + disk.read + " W " + disk.write, "progress":percent(disk.percent), "color":diskWarn ? barColor("warning", "#ff4d5e") : barColor("storage", "#b16dff"), "detailColor":diskWarn ? barColor("warning", "#ff4d5e") : "#c78bff", "tooltip":disk.model + "\nHealth: " + disk.health + "\nTemperature: " + tempText(disk.temp) + "\nRead " + disk.read + " · Write " + disk.write})
            }
        } else if (group === "fan" && Plasmoid.configuration.showFan) {
            var fanAvailable = number(d.fan_rpm) > 0
            addRow(rows, {"id":"fan", "title":rowLabel("fan", "FAN"), "value":number(d.fan_rpm).toFixed(0) + " RPM avg", "detail":percent(d.fan_percent).toFixed(0) + "%", "progress":percent(d.fan_percent), "color":barColor("fan", "#35c8b5"), "detailColor":"#63dcc8", "tooltip":"Average speed across detected hardware fans", "visible":!autoHide || fanAvailable})
        } else if (group === "network" && Plasmoid.configuration.showNetwork) {
            var interfaces = d.network_interfaces || []
            for (var n = 0; n < interfaces.length; n++) if (selected(Plasmoid.configuration.networkIds, interfaces[n], n)) {
                var net = interfaces[n]
                addRow(rows, {"id":net.id, "title":rowLabel(net.id, "NET"), "value":net.name + " ↓ " + net.down + " ↑ " + net.up, "detail":net.kind, "progress":percent(net.percent), "color":barColor("network", "#30bdf0"), "detailColor":"#5ed6ff", "tooltip":net.kind + " interface " + net.name + "\nState: " + net.state + "\nDownload " + net.down + " · Upload " + net.up, "visible":!autoHide || net.state === "up"})
            }
        } else if (group === "battery" && Plasmoid.configuration.showBattery) {
            var batteryAvailable = d.battery_status && d.battery_status !== "n/a"
            var low = batteryAvailable && percent(d.battery_percent) <= Plasmoid.configuration.batteryWarning && d.battery_status !== "Charging"
            addRow(rows, {"id":"battery", "title":rowLabel("battery", "BAT"), "value":(d.battery_status || "n/a") + " " + percent(d.battery_percent).toFixed(0) + "%", "detail":number(d.battery_watts).toFixed(1) + "W", "progress":percent(d.battery_percent), "color":low ? barColor("warning", "#ff4d5e") : barColor("battery", "#e6c84d"), "detailColor":low ? barColor("warning", "#ff4d5e") : "#f3d35d", "tooltip":"Battery state, charge level, and current power", "visible":!autoHide || batteryAvailable})
        }
        return rows
    }
    function rebuildRows() {
        var order = (Plasmoid.configuration.rowOrder || "mode,cpu,cores,ram,gpus,storage,fan,network,battery").split(",")
        var rows = []
        for (var index = 0; index < order.length; index++) rows = rows.concat(rowsForGroup(order[index]))
        displayRows = rows
        Qt.callLater(function() { if (root.height !== root.implicitHeight) root.height = root.implicitHeight })
    }
    function updateTelemetry() {
        if (requestRunning) return
        requestRunning = true
        var xhr = new XMLHttpRequest()
        xhr.open("GET", "http://127.0.0.1:9090/telemetry")
        xhr.timeout = 1800
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            requestRunning = false
            if (xhr.status === 200 && xhr.responseText) {
                try {
                    telemetryData = JSON.parse(xhr.responseText)
                    lastSuccessMs = Date.now()
                    rebuildRows()
                } catch (error) {}
            }
        }
        xhr.ontimeout = function() { requestRunning = false }
        xhr.onerror = function() { requestRunning = false }
        xhr.send()
    }

    Component.onCompleted: updateTelemetry()
    Connections {
        target: Plasmoid.configuration
        function onValueChanged() { root.rebuildRows() }
    }

    Rectangle {
        anchors.fill: parent
        color: "#101216"
        radius: 8
        border.color: root.telemetryStale ? "#ff4d5e" : "#2c313a"
        border.width: 1

        ColumnLayout {
            id: contentColumn
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 10
            spacing: root.compact ? 4 : 8

            Repeater {
                model: root.displayRows
                delegate: MetricBar {
                    required property var modelData
                    Layout.fillWidth: true
                    title: modelData.title
                    valueText: modelData.value
                    detailText: modelData.detail
                    progress: modelData.progress
                    barColor: modelData.color
                    detailColor: modelData.detailColor
                    tooltipText: modelData.tooltip
                }
            }

            Controls.Label {
                visible: root.displayRows.length === 0
                Layout.fillWidth: true
                text: root.telemetryStale ? i18n("Telemetry offline") : i18n("No rows selected")
                color: root.telemetryStale ? "#ff6b5f" : "#a8b0bc"
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }

    component MetricBar: Item {
        id: metric
        property string title: ""
        property string valueText: ""
        property string detailText: ""
        property string tooltipText: ""
        property color detailColor: "#ffffff"
        property color barColor: "#ffffff"
        property real progress: 0
        implicitHeight: root.compact ? 22 : 28
        Layout.preferredHeight: implicitHeight

        HoverHandler { id: hover }
        Controls.ToolTip.visible: hover.hovered && metric.tooltipText.length > 0
        Controls.ToolTip.text: metric.tooltipText
        Controls.ToolTip.delay: 400

        RowLayout {
            anchors.fill: parent
            spacing: root.compact ? 5 : 8
            Text {
                text: metric.title
                color: "#a8b0bc"
                font.pixelSize: root.compact ? 9 : 11
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                Layout.preferredWidth: root.compact ? 34 : 48
                Layout.fillHeight: true
                elide: Text.ElideRight
            }
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true
                color: "#1b2028"; radius: root.compact ? 4 : 6
                border.color: "#313844"; border.width: 1; clip: true
                Rectangle {
                    anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
                    width: parent.width * root.clamp(metric.progress, 0, 100) / 100
                    radius: parent.radius; color: metric.barColor; opacity: 0.82
                }
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: root.compact ? 7 : 10
                    anchors.rightMargin: root.compact ? 5 : 7
                    spacing: 6
                    Text {
                        text: metric.valueText; color: "#f4f7fb"
                        font.pixelSize: root.compact ? 9 : 11; font.bold: true
                        elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
                        Layout.fillWidth: true; Layout.fillHeight: true
                    }
                    Rectangle {
                        visible: !root.compact || metric.detailText.length > 0
                        Layout.preferredWidth: Math.max(root.compact ? 36 : 46, detailLabel.implicitWidth + (root.compact ? 10 : 16))
                        Layout.preferredHeight: root.compact ? 15 : 18
                        radius: root.compact ? 4 : 5; color: "#202631"
                        border.color: metric.detailColor; border.width: 1
                        Text {
                            id: detailLabel; anchors.centerIn: parent
                            text: metric.detailText; color: metric.detailColor
                            font.pixelSize: root.compact ? 8 : 10; font.bold: true
                        }
                    }
                }
            }
        }
    }

    Timer {
        interval: Math.max(Plasmoid.configuration.refreshInterval, 1) * 1000
        repeat: true; running: true
        onTriggered: root.updateTelemetry()
    }
    Timer {
        interval: 1000; repeat: true; running: true
        onTriggered: { var old = root.telemetryStale; root.telemetryStale = root.lastSuccessMs === 0 || Date.now() - root.lastSuccessMs > Math.max(Plasmoid.configuration.refreshInterval, 1) * 2500; if (old !== root.telemetryStale) root.rebuildRows() }
    }
}
