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
    property bool confirmedUnlistedMutes: false
    property var confirmedApps: []
    property bool hasMutes: false
    property string errorMessage: ""
    property int requestId: 0
    readonly property string requestNamespace: Math.random().toString(36).slice(2)
    property var activeRequest: null
    property var queuedActions: []
    signal visibleRowLayoutChanged()

    ListModel { id: visibleRows }

    function normalizedRow(app, muted) {
        return {
            key: String(app.key || ""),
            name: String(app.name || ""),
            icon: String(app.icon || ""),
            iconCategory: /^(voice|chat|browser|music|video|games|system)$/.test(app.iconCategory) ? app.iconCategory : "generic",
            shared: Boolean(app.shared),
            muted: muted
        };
    }

    function syncVisibleRows() {
        let clearMutes = false;
        let pendingMutes = Object.create(null);
        const actions = activeRequest ? [activeRequest, ...queuedActions] : queuedActions;
        for (const action of actions) {
            if (action.action === "share-all") {
                clearMutes = true;
                pendingMutes = Object.create(null);
            } else if (action.key) {
                pendingMutes[action.key] = action.action === "set-muted";
            }
        }

        let anyMutes = confirmedUnlistedMutes && !clearMutes;
        var wanted = [];
        var keep = Object.create(null);
        for (const app of confirmedApps) {
            const pendingMute = pendingMutes[app.key];
            var row = normalizedRow(app, pendingMute ?? (!clearMutes && Boolean(app.muted)));
            wanted.push(row);
            keep[row.key] = true;
            anyMutes = anyMutes || row.muted;
        }
        hasMutes = anyMutes;
        var layoutChanged = false;
        for (var j = visibleRows.count - 1; j >= 0; --j) {
            if (!keep[visibleRows.get(j).key]) {
                visibleRows.remove(j);
                layoutChanged = true;
            }
        }
        var fields = ["name", "icon", "iconCategory", "shared", "muted"];
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

    Plasmoid.icon: decodeURIComponent(Qt.resolvedUrl("../icons/discord-stream-audio-control.png").toString().replace(/^file:\/\//, ""))
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

    function request(action, key) {
        if (action === "status") {
            if (!activeRequest && queuedActions.length === 0) {
                startRequest(action, key);
            }
            return;
        }
        queuedActions = action === "share-all" ? [] : queuedActions.filter(entry => entry.key !== key);
        queuedActions.push({ action: action, key: key });
        startNextAction();
        syncVisibleRows();
    }

    function startNextAction() {
        if (!activeRequest && queuedActions.length > 0) {
            const next = queuedActions.shift();
            startRequest(next.action, next.key);
        }
    }

    function startRequest(action, key) {
        const nonce = requestNamespace + "-" + (++requestId);
        const argument = key ? hexEncode(key) : "''";
        const command = "/usr/bin/python3 -B " + quote(backendPath) + " " + action + " " + argument + " " + nonce;
        activeRequest = requestSource.createObject(root, { action: action, key: key, command: command });
        if (activeRequest) {
            requestTimeout.restart();
            activeRequest.connectSource(command);
        } else {
            errorMessage = i18n("The audio backend did not respond.");
            Qt.callLater(root.startNextAction);
        }
    }

    function completeRequest(worker, data) {
        if (!worker || worker !== activeRequest) {
            return;
        }
        requestTimeout.stop();
        worker.disconnectSource(worker.command);
        activeRequest = null;
        worker.destroy();

        if (!data) {
            errorMessage = i18n("The audio backend did not respond.");
        } else if (data["exit code"] !== 0) {
            errorMessage = i18n("Audio backend error: %1", String(data["stderr"] || data["exit code"]).trim().slice(0, 240));
        } else {
            try {
                const reply = JSON.parse(data["stdout"]);
                if (!reply || typeof reply.error !== "string") {
                    throw new Error("Missing backend status");
                }
                if (reply.apps !== undefined) {
                    if (!Array.isArray(reply.apps) || typeof reply.active !== "boolean" ||
                        !reply.apps.every(app => app && typeof app.key === "string" && app.key &&
                            typeof app.name === "string" && typeof app.icon === "string" &&
                            typeof app.iconCategory === "string")) {
                        throw new Error("Invalid audio source data");
                    }
                    const liveKeys = new Set(reply.apps.map(app => app.key));
                    if (liveKeys.size !== reply.apps.length) {
                        throw new Error("Duplicate audio source key");
                    }
                    recordingActive = reply.active;
                    confirmedUnlistedMutes = Boolean(reply.hasUnlistedMutes);
                    confirmedApps = reply.apps;
                    queuedActions = queuedActions.filter(entry => !entry.key || liveKeys.has(entry.key));
                } else if (!reply.error) {
                    throw new Error("No audio source data");
                }
                errorMessage = reply.error ? i18n("Audio backend error: %1", reply.error) : "";
            } catch (ex) {
                errorMessage = i18n("Invalid backend response: %1", String(ex).slice(0, 240));
            }
        }
        syncVisibleRows();
        Qt.callLater(root.startNextAction);
    }

    Component {
        id: requestSource
        Plasma5Support.DataSource {
            id: worker
            property string action
            property string key
            property string command
            engine: "executable"
            onNewData: function(source, data) {
                if (source === worker.command) {
                    root.completeRequest(worker, data);
                }
            }
        }
    }

    Timer {
        id: requestTimeout
        interval: 25000
        onTriggered: root.completeRequest(root.activeRequest, null)
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
                enabled: root.hasMutes
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
                text: root.errorMessage || (!root.recordingActive && visibleRows.count > 0 ? i18n("No active Discord stream") : "")
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
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
                        required property bool shared
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

                            Item {
                                Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                                Layout.preferredHeight: Kirigami.Units.iconSizes.medium

                                Kirigami.Icon {
                                    id: applicationIcon
                                    anchors.fill: parent
                                    source: sourceRow.icon
                                    fallback: ""
                                    visible: sourceRow.icon.length > 0
                                }

                                Image {
                                    anchors.fill: parent
                                    visible: !applicationIcon.visible || applicationIcon.status !== Kirigami.Icon.Ready
                                    source: visible ? Qt.resolvedUrl("../icons/fallback/" + sourceRow.iconCategory + ".png") : ""
                                    sourceSize.width: Math.ceil(width * Screen.devicePixelRatio)
                                    sourceSize.height: Math.ceil(height * Screen.devicePixelRatio)
                                    fillMode: Image.PreserveAspectFit
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                PlasmaComponents.Label {
                                    Layout.fillWidth: true
                                    text: sourceRow.name
                                    textFormat: Text.PlainText
                                    elide: Text.ElideRight
                                    color: Kirigami.Theme.textColor
                                }
                                PlasmaComponents.Label {
                                    Layout.fillWidth: true
                                    visible: text.length > 0
                                    text: sourceRow.muted ? (root.recordingActive ? i18n("Muted in Discord stream") :
                                                                                  i18n("Muted for next stream")) :
                                          sourceRow.shared ? i18n("Being shared") : ""
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
                                onClicked: root.request(sourceRow.muted ? "set-unmuted" : "set-muted", sourceRow.key)
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
