import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.plasma.plasmoid 2.0

PlasmoidItem {
    id: root
    width: 760
    height: 306

    property var telemetryData: ({})

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value))
    }

    function percent(value) {
        return clamp(parseFloat(value) || 0, 0, 100)
    }

    function number(value) {
        return parseFloat(value) || 0
    }

    function tempColor(value) {
        var temp = parseFloat(value) || 0
        if (temp <= 0) return "#666b73"
        if (temp <= 80) return "#42d66f"
        if (temp <= 90) return "#ffd24a"
        return "#ff4d5e"
    }

    function tempText(value) {
        var temp = parseFloat(value) || 0
        return temp > 0 ? Math.round(temp) + "C" : "n/a"
    }

    function modeColor(value) {
        if (value === "performance") return "#ff6b5f"
        if (value === "balanced") return "#63dcc8"
        if (value === "power-saver") return "#43d17a"
        return "#a8b0bc"
    }

    function readTelemetry() {
        try {
            var xhr = new XMLHttpRequest()
            xhr.open("GET", "http://127.0.0.1:9090/telemetry", false)
            xhr.timeout = 1000
            xhr.send()

            if (xhr.status === 200 && xhr.responseText) {
                return JSON.parse(xhr.responseText)
            }
        } catch (e) {
        }

        return {}
    }

    function updateTelemetry() {
        root.telemetryData = root.readTelemetry()
    }

    Component.onCompleted: root.updateTelemetry()

    Rectangle {
        anchors.fill: parent
        color: "#101216"
        radius: 8
        border.color: "#2c313a"
        border.width: 1

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 8

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 26
                radius: 6
                color: "#181d24"
                border.color: root.modeColor(root.telemetryData.power_profile || "")
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    spacing: 8

                    Text {
                        text: "MODE"
                        color: "#a8b0bc"
                        font.pixelSize: 11
                        font.bold: true
                        verticalAlignment: Text.AlignVCenter
                        Layout.preferredWidth: 38
                        Layout.fillHeight: true
                    }

                    Text {
                        text: root.telemetryData.power_profile_label || "Unknown"
                        color: root.modeColor(root.telemetryData.power_profile || "")
                        font.pixelSize: 12
                        font.bold: true
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                    }
                }
            }

            MetricBar {
                Layout.fillWidth: true
                title: "CPU"
                valueText: root.percent(root.telemetryData.cpu_usage).toFixed(1) + "% " + (root.telemetryData.cpu_frequency || "n/a")
                detailText: root.tempText(root.telemetryData.cpu_temp)
                detailColor: root.tempColor(root.telemetryData.cpu_temp)
                barColor: "#43d17a"
                progress: root.percent(root.telemetryData.cpu_usage)
            }

            MetricBar {
                Layout.fillWidth: true
                title: "RAM"
                valueText: root.telemetryData.ram_info || "n/a"
                detailText: root.percent(root.telemetryData.ram_usage).toFixed(1) + "%"
                detailColor: "#6aa7ff"
                barColor: "#4f93ff"
                progress: root.percent(root.telemetryData.ram_usage)
            }

            MetricBar {
                Layout.fillWidth: true
                title: "GPU"
                valueText: "VRAM " + (root.telemetryData.gpu_vram || "n/a") + " " + root.percent(root.telemetryData.gpu_usage).toFixed(0) + "%"
                detailText: root.tempText(root.telemetryData.gpu_temp)
                detailColor: root.tempColor(root.telemetryData.gpu_temp)
                barColor: "#ffae3d"
                progress: root.percent(root.telemetryData.gpu_usage)
            }

            MetricBar {
                Layout.fillWidth: true
                title: root.telemetryData.storage_name || "SSD"
                valueText: root.telemetryData.storage_usage || "n/a"
                detailText: "R " + (root.telemetryData.storage_read || "0 B/s") + " W " + (root.telemetryData.storage_write || "0 B/s")
                detailColor: "#c78bff"
                barColor: "#b16dff"
                progress: root.percent(root.telemetryData.storage_percent)
            }

            MetricBar {
                Layout.fillWidth: true
                title: "FAN"
                valueText: root.number(root.telemetryData.fan_rpm).toFixed(0) + " RPM avg"
                detailText: root.percent(root.telemetryData.fan_percent).toFixed(0) + "%"
                detailColor: "#63dcc8"
                barColor: "#35c8b5"
                progress: root.percent(root.telemetryData.fan_percent)
            }

            MetricBar {
                Layout.fillWidth: true
                title: "NET"
                valueText: ((root.telemetryData.network_iface || "net") + " ↓ " + (root.telemetryData.network_down || "0 B/s") + " ↑ " + (root.telemetryData.network_up || "0 B/s") + " " + (root.telemetryData.vpn_status || "VPN OFF"))
                detailText: root.percent(root.telemetryData.network_percent).toFixed(1) + "%"
                detailColor: "#5ed6ff"
                barColor: "#30bdf0"
                progress: root.percent(root.telemetryData.network_percent)
            }

            MetricBar {
                Layout.fillWidth: true
                title: "BAT"
                valueText: ((root.telemetryData.battery_status || "n/a") + " " + root.percent(root.telemetryData.battery_percent).toFixed(0) + "%")
                detailText: root.number(root.telemetryData.battery_watts).toFixed(1) + "W"
                detailColor: "#f3d35d"
                barColor: "#e6c84d"
                progress: root.percent(root.telemetryData.battery_percent)
            }
        }
    }

    component MetricBar: Item {
        id: metric

        property string title: ""
        property string valueText: ""
        property string detailText: ""
        property color detailColor: "#ffffff"
        property color barColor: "#ffffff"
        property real progress: 0

        implicitHeight: 28
        Layout.preferredHeight: 28

        RowLayout {
            anchors.fill: parent
            spacing: 8

            Text {
                text: metric.title
                color: "#a8b0bc"
                font.pixelSize: 11
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                Layout.preferredWidth: 38
                Layout.fillHeight: true
            }

            Rectangle {
                id: track
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#1b2028"
                radius: 6
                border.color: "#313844"
                border.width: 1
                clip: true

                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: parent.width * root.clamp(metric.progress, 0, 100) / 100
                    radius: 6
                    color: metric.barColor
                    opacity: 0.82
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 7
                    spacing: 8

                    Text {
                        text: metric.valueText
                        color: "#f4f7fb"
                        font.pixelSize: 11
                        font.bold: true
                        elide: Text.ElideRight
                        verticalAlignment: Text.AlignVCenter
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                    }

                    Rectangle {
                        Layout.preferredWidth: Math.max(46, detailLabel.implicitWidth + 16)
                        Layout.preferredHeight: 18
                        radius: 5
                        color: "#202631"
                        border.color: metric.detailColor
                        border.width: 1

                        Text {
                            id: detailLabel
                            anchors.centerIn: parent
                            text: metric.detailText
                            color: metric.detailColor
                            font.pixelSize: 10
                            font.bold: true
                        }
                    }
                }
            }
        }
    }

    Timer {
        interval: 5000
        repeat: true
        running: true
        onTriggered: root.updateTelemetry()
    }
}
