pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as Plasma5Support

PlasmoidItem {
    id: root

    property bool recordingActive: false
    property bool hasUnlistedMutes: false
    property var apps: []
    property string errorMessage: ""
    property int requestId: 0
    property string activeCommand: ""
    property var queuedActions: []
    signal visibleRowLayoutChanged()

    ListModel { id: visibleRows }

    function normalizedRow(app) {
        return {
            key: String(app.key || ""),
            name: String(app.name || ""),
            icon: String(app.icon || ""),
            iconCategory: /^(voice|chat|browser|music|video|games|system)$/.test(app.iconCategory) ? app.iconCategory : "generic",
            muted: Boolean(app.muted)
        };
    }

    function syncVisibleRows() {
        var wanted = [];
        var keep = Object.create(null);
        for (var n = 0; n < apps.length; ++n) {
            var row = normalizedRow(apps[n]);
            wanted.push(row);
            keep[row.key] = true;
        }
        var layoutChanged = false;
        for (var j = visibleRows.count - 1; j >= 0; --j) {
            if (!keep[visibleRows.get(j).key]) {
                visibleRows.remove(j);
                layoutChanged = true;
            }
        }
        var fields = ["name", "icon", "iconCategory", "muted"];
        for (var i = 0; i < wanted.length; ++i) {
            var next = wanted[i];
            var current = -1;
            for (var k = i; k < visibleRows.count; ++k) {
                if (visibleRows.get(k).key === next.key) {
                    current = k;
                    break;
                }
            }
            if (current === -1) {
                visibleRows.insert(i, next);
                layoutChanged = true;
                continue;
            }
            if (current !== i) {
                visibleRows.move(current, i, 1);
                layoutChanged = true;
            }
            var existing = visibleRows.get(i);
            for (var f = 0; f < fields.length; ++f) {
                var field = fields[f];
                if (existing[field] !== next[field]) {
                    visibleRows.setProperty(i, field, next[field]);
                }
            }
        }
        if (layoutChanged) {
            visibleRowLayoutChanged();
        }
    }
    readonly property string backendPath: decodeURIComponent(Qt.resolvedUrl("../scripts/bridge.py").toString().replace(/^file:\/\//, ""))

    Plasmoid.icon: "org.cachy.discordstreamaudiocontrol"
    Plasmoid.title: "Discord Stream Audio Control"
    toolTipMainText: ""
    toolTipSubText: ""
    hideOnWindowDeactivate: true
    Plasmoid.status: root.recordingActive ? PlasmaCore.Types.ActiveStatus : PlasmaCore.Types.PassiveStatus
    Plasmoid.hasConfigurationInterface: false

    Component.onCompleted: Plasmoid.removeInternalAction("configure")

    function hexEncode(value) {
        var text = String(value || "");
        var result = "";
        for (var i = 0; i < text.length; ++i) {
            var chars = text.charCodeAt(i).toString(16);
            result += ("0000" + chars).slice(-4);
        }
        return result;
    }

    function quote(value) {
        return "'" + value.replace(/'/g, "'\\''") + "'";
    }

    function optimisticUpdate(action, key) {
        if (action === "share-all") {
            hasUnlistedMutes = false;
        }
        var updated = [];
        for (var i = 0; i < apps.length; ++i) {
            var next = Object.assign({}, apps[i]);
            if (action === "mute" && next.key === key) {
                next.muted = !Boolean(next.muted);
            } else if (action === "share-all") {
                next.muted = false;
            }
            updated.push(next);
        }
        apps = updated;
        syncVisibleRows();
    }

    function request(action, key) {
        if (action !== "status") {
            optimisticUpdate(action, key);
        }
        if (activeCommand) {
            if (action !== "status") {
                queuedActions.push({ action: action, key: key });
            }
            return;
        }
        startRequest(action, key);
    }

    function startRequest(action, key) {
        var argument = key ? hexEncode(key) : "''";
        activeCommand = "/usr/bin/python -B " + quote(backendPath) + " " + action + " " + argument + " " + (++requestId);
        commandEngine.connectSource(activeCommand);
    }

    function updateState(source, data) {
        if (source !== activeCommand) {
            return;
        }
        if (queuedActions.length > 0) {
            const next = queuedActions.shift();
            startRequest(next.action, next.key);
            return;
        }
        activeCommand = "";
        var response;
        try {
            response = JSON.parse(data["stdout"] || "{}");
        } catch (ex) {
            errorMessage = i18n("Invalid backend response: %1", ex);
            return;
        }
        recordingActive = Boolean(response.active);
        hasUnlistedMutes = Boolean(response.hasUnlistedMutes);
        apps = response.apps || [];
        syncVisibleRows();
        errorMessage = response.error || "";
    }

    Plasma5Support.DataSource {
        id: commandEngine
        engine: "executable"
        connectedSources: []
        onNewData: function(source, data) {
            disconnectSource(source);
            root.updateState(source, data);
        }
    }

    Timer {
        interval: 1300
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: root.request("status", "")
    }

    fullRepresentation: Item {
        id: panelContents
        Layout.minimumWidth: 370
        Layout.minimumHeight: 360
        Layout.preferredWidth: 440
        Layout.preferredHeight: 440
        Layout.maximumWidth: 440
        Layout.maximumHeight: 550

        property int rowLayoutRevision: 0
        readonly property int hoveredRowIndex: {
            var revision = rowLayoutRevision;
            if (!listPointer.hovered) {
                return -1;
            }
            return sourcesView.indexAt(
                listPointer.point.position.x + sourcesView.contentX,
                listPointer.point.position.y + sourcesView.contentY
            );
        }

        Connections {
            target: root
            function onVisibleRowLayoutChanged() {
                sourcesView.forceLayout();
                panelContents.rowLayoutRevision++;
            }
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            PlasmaComponents.ToolButton {
                Layout.alignment: Qt.AlignLeft
                Layout.margins: Kirigami.Units.smallSpacing * 2
                text: i18n("Share all audio")
                enabled: root.hasUnlistedMutes || root.apps.some(function(app) { return app.muted; })
                onClicked: root.request("share-all", "")
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.smallSpacing * 2
                Layout.rightMargin: Kirigami.Units.smallSpacing * 2
                Layout.bottomMargin: Kirigami.Units.smallSpacing
                spacing: Kirigami.Units.smallSpacing

                PlasmaComponents.Label {
                    text: i18n("Audio sources")
                    color: Kirigami.Theme.disabledTextColor
                    font.bold: true
                    font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    color: Kirigami.Theme.textColor
                    opacity: 0.16
                }
            }

            PlasmaComponents.Label {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.smallSpacing * 2
                Layout.rightMargin: Kirigami.Units.smallSpacing * 2
                Layout.bottomMargin: Kirigami.Units.smallSpacing
                visible: text.length > 0
                text: root.errorMessage || (!root.recordingActive && root.apps.length > 0 ? i18n("No active Discord stream") : "")
                wrapMode: Text.WordWrap
                color: root.errorMessage ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.disabledTextColor
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
            }

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                ListView {
                    id: sourcesView
                    anchors.fill: parent
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    model: visibleRows
                    spacing: 0

                    HoverHandler {
                        id: listPointer
                    }

                    delegate: Item {
                        id: sourceRow
                        required property int index
                        required property string key
                        required property string name
                        required property string icon
                        required property string iconCategory
                        required property bool muted
                        width: ListView.view.width
                        height: Kirigami.Units.gridUnit * 2.75

                        Rectangle {
                            anchors.fill: parent
                            anchors.leftMargin: 2
                            anchors.rightMargin: 2
                            anchors.topMargin: 2
                            anchors.bottomMargin: 2
                            visible: panelContents.hoveredRowIndex === sourceRow.index
                            color: "#264A5C"
                            border.color: "#3DAEE9"
                            border.width: 1
                            radius: 5
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Kirigami.Units.smallSpacing * 2
                            anchors.rightMargin: Kirigami.Units.smallSpacing * 2
                            spacing: Kirigami.Units.smallSpacing * 2

                            Kirigami.Icon {
                                readonly property url categoryIcon: Qt.resolvedUrl("../icons/fallback/" + sourceRow.iconCategory + ".png")
                                source: sourceRow.icon || categoryIcon
                                fallback: decodeURIComponent(categoryIcon.toString().replace(/^file:\/\//, ""))
                                Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                                Layout.preferredHeight: Kirigami.Units.iconSizes.medium
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                PlasmaComponents.Label {
                                    Layout.fillWidth: true
                                    text: sourceRow.name
                                    elide: Text.ElideRight
                                    color: Kirigami.Theme.textColor
                                }
                                PlasmaComponents.Label {
                                    Layout.fillWidth: true
                                    visible: text.length > 0
                                    text: sourceRow.muted ? (root.recordingActive ? i18n("Muted in Discord stream") :
                                                                                  i18n("Muted for next stream")) :
                                          root.recordingActive ? i18n("Being shared") : ""
                                    elide: Text.ElideRight
                                    color: Kirigami.Theme.disabledTextColor
                                    font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                                }
                            }

                            PlasmaComponents.ToolButton {
                                text: sourceRow.muted ? i18n("Unmute") : i18n("Mute")
                                hoverEnabled: true
                                display: QQC2.AbstractButton.IconOnly
                                icon.source: Qt.resolvedUrl(sourceRow.muted ? "../icons/muted.svg" : "../icons/audible.svg")
                                onClicked: root.request("mute", sourceRow.key)
                            }
                        }
                    }
                }

                PlasmaComponents.Label {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.verticalCenter: parent.verticalCenter
                    visible: visibleRows.count === 0
                    color: Kirigami.Theme.disabledTextColor
                    text: i18n("No audio sources detected")
                }
            }
        }
    }
}
