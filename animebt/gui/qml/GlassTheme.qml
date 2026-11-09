import QtQuick

QtObject {
    property bool dark: false
    property QtObject typography: null

    function originalFont(title, pixels) {
        return typography ? typography.originalFont(title, pixels) : Qt.font({pixelSize: pixels})
    }

    readonly property color ink: dark ? "#eef1ff" : "#202843"
    readonly property color muted: dark ? "#b8c3df" : "#535e77"
    readonly property color accent: dark ? "#bcb8ff" : "#5653ad"
    readonly property color accentText: dark ? "#cbc7ff" : "#454089"
    readonly property color accentFill: dark ? "#bcb8ff" : "#5653ad"
    readonly property color accentHover: dark ? "#d0ccff" : "#6560be"
    readonly property color accentPressed: dark ? "#a5a1e8" : "#433f93"
    readonly property color accentInk: dark ? "#211b46" : "#ffffff"
    readonly property color danger: dark ? "#ffbdcd" : "#832d46"
    readonly property color warning: dark ? "#f2c7aa" : "#7a4b3c"

    readonly property color backgroundTop: dark ? "#f1222a40" : "#edf6f8ff"
    readonly property color backgroundMiddle: dark ? "#eb171f35" : "#e5e7edf9"
    readonly property color backgroundBottom: dark ? "#f011192c" : "#edf0f5ff"
    readonly property color blueGlow: dark ? "#70404478" : "#a0d8e1ff"
    readonly property color tealGlow: dark ? "#50305264" : "#90d6f6f4"
    readonly property color silhouette: dark ? "#a0131725" : "#6034405b"
    readonly property color shadow: dark ? "#a0000000" : "#982b365f"
    readonly property color frame: dark ? "#607d8cb5" : "#faffffff"
    readonly property color badgeTop: dark ? "#464574" : "#f7f3ff"
    readonly property color badgeBottom: dark ? "#313658" : "#c1c5f4"

    readonly property color panel: dark ? "#d92a344d" : "#b0ffffff"
    readonly property color panelSoft: dark ? "#aa2c3650" : "#9cffffff"
    readonly property color panelFaint: dark ? "#65364161" : "#50ffffff"
    readonly property color panelHover: dark ? "#e0424e70" : "#f4ffffff"
    readonly property color panelPressed: dark ? "#585581" : "#c3c1ed"
    readonly property color line: dark ? "#64748aac" : "#a4b4bad0"
    readonly property color softLine: dark ? "#4964739d" : "#26626e97"
    readonly property color popup: dark ? "#fc252d44" : "#fcf7f9ff"
    readonly property color controlBase: dark ? "#252f47" : "#f7f9ff"
    readonly property color controlHover: dark ? "#354362" : "#e5eaf9"
    readonly property color controlSelected: dark ? "#41466c" : "#dce1f7"
    readonly property color controlPressed: dark ? "#4a5079" : "#d1d9f4"
    readonly property color field: dark ? "#df29344f" : "#ccffffff"
    readonly property color fieldHover: dark ? "#ef303c5a" : "#e9ffffff"
    readonly property color fieldFocus: dark ? "#f1354160" : "#f5ffffff"
    readonly property color disabledFill: dark ? "#406965a4" : "#1d5653ad"
    readonly property color imageBase: dark ? "#3e4b6c" : "#dde3f4"
    readonly property color dangerFill: dark ? "#f03d283b" : "#f8fff0f4"
    readonly property color dangerLine: dark ? "#ab667b" : "#d3a8b5"
}
