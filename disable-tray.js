var widgetName = "org.cachy.discordstreamaudiocontrol";
for (var panel of panels()) {
    for (var widget of panel.widgets()) {
        if (widget.type !== "org.kde.plasma.systemtray") {
            continue;
        }
        var tray = widget;
        var containmentId = widget.readConfig("SystrayContainmentId");
        if (containmentId) {
            tray = desktopById(Number(containmentId)) || widget;
        }
        tray.currentConfigGroup = ["General"];
        var changed = false;
        for (var key of ["extraItems", "shownItems", "hiddenItems", "knownItems"]) {
            var original = String(tray.readConfig(key) || "").split(",");
            var updated = original.filter(function(item) {
                return item !== widgetName;
            });
            if (original.length !== updated.length) {
                tray.writeConfig(key, updated);
                changed = true;
            }
        }
        if (changed) {
            tray.reloadConfig();
        }
    }
}
