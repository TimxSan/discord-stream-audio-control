var widgetName = "org.cachy.discordstreamaudiocontrol";
var trayCount = 0;
var changed = 0;
for (var panel of panels()) {
    for (var widget of panel.widgets()) {
        if (widget.type !== "org.kde.plasma.systemtray") {
            continue;
        }
        var tray = widget;
        var legacyContainmentId = Number(widget.readConfig("SystrayContainmentId"));
        if (Number.isInteger(legacyContainmentId) && legacyContainmentId > 0) {
            var legacyTray = desktopById(legacyContainmentId);
            if (legacyTray && legacyTray.type === "org.kde.plasma.private.systemtray") {
                tray = legacyTray;
            }
        }
        trayCount++;
        tray.currentConfigGroup = ["General"];
        var items = String(tray.readConfig("extraItems") || "").split(",").filter(function(item) {
            return item.length > 0;
        });
        if (items.indexOf(widgetName) === -1) {
            items.push(widgetName);
            tray.writeConfig("extraItems", items);
            tray.reloadConfig();
            changed++;
        }
    }
}
print("DISCORD_AUDIO_TRAYS=" + trayCount + ";ADDED=" + changed);
