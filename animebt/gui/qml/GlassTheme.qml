import QtQuick

QtObject {
    property bool dark: false
    property bool liquidGlass: true
    property bool wallpaperTextShadow: false
    readonly property color wallpaperShadowColor: dark ? "#70000000" : "#75ffffff"
    readonly property bool plainDark: dark && !liquidGlass
    property QtObject typography: null
    readonly property int textSize: wallpaperTextShadow ? 17 : 15
    readonly property int smallTextSize: wallpaperTextShadow ? 14 : 13
    readonly property int detailTextSize: wallpaperTextShadow ? 15 : 14

    readonly property string readingFamily: wallpaperTextShadow && typography ? typography.readableFont("", textSize).family : Qt.application.font.family

    function originalFont(title, pixels) {
        if (wallpaperTextShadow && typography) return typography.readableFont(title, pixels)
        return typography ? typography.originalFont(title, pixels) : Qt.font({pixelSize: pixels})
    }

    readonly property color ink: plainDark ? "#f2f0f3" : (liquidGlass ? (dark ? "#f4f1f5" : "#202843") : (dark ? "#eef1ff" : "#202843"))
    readonly property color muted: wallpaperTextShadow && dark ? "#f0edf3" : plainDark ? "#bbb8c0" : (liquidGlass ? (dark ? "#d2cad7" : "#535e77") : (dark ? "#b8c3df" : "#535e77"))
    readonly property color accent: plainDark ? "#e998bd" : (liquidGlass ? (dark ? "#eab0cf" : "#a42b64") : (dark ? "#ffacd2" : "#a42b64"))
    readonly property color accentText: plainDark ? "#f0b4d0" : (liquidGlass ? (dark ? "#f1c6dd" : "#8d2457") : (dark ? "#ffc5e0" : "#8d2457"))
    readonly property color accentFill: accent
    readonly property color accentHover: plainDark ? "#f1afcf" : (dark ? "#f4c7e0" : "#a7366c")
    readonly property color accentPressed: plainDark ? "#d881a8" : (dark ? "#d898bc" : "#84214f")
    readonly property color accentInk: plainDark ? "#2b1822" : (dark ? "#35202f" : "#ffffff")
    readonly property color danger: dark ? "#f3b2c3" : "#832d46"
    readonly property color warning: dark ? "#e9c6a7" : "#7a4b3c"
    readonly property color success: dark ? "#96d8b2" : "#187548"
    readonly property color successFill: dark ? "#263a31" : "#e5f5ec"

    // DWM pixels behind a translucent window are not a Qt texture. Keep the
    // application canvas opaque; only actual in-app lower layers are refracted.
    // The rounded window corners remain transparent.
    readonly property color backgroundTop: plainDark ? "#19191c" : (liquidGlass ? (dark ? "#25242c" : "#f6f8ff") : (dark ? "#222a40" : "#f6f8ff"))
    readonly property color backgroundMiddle: plainDark ? "#19191c" : (liquidGlass ? (dark ? "#17171d" : "#e7edf9") : (dark ? "#171f35" : "#e7edf9"))
    readonly property color backgroundBottom: plainDark ? "#19191c" : (liquidGlass ? (dark ? "#1d1b23" : "#f0f5ff") : (dark ? "#11192c" : "#f0f5ff"))
    readonly property color accentGlow: dark ? "#705f3458" : "#a0f4dceb"
    readonly property color tealGlow: dark ? "#504d405d" : "#90d6f6f4"
    readonly property color silhouette: dark ? "#a015141b" : "#6034405b"
    readonly property color shadow: dark ? "#a0000000" : "#982b365f"
    readonly property color frame: plainDark ? "#38373e" : (liquidGlass ? (dark ? "#32ffffff" : "#faffffff") : (dark ? "#7d8cb5" : "#d4daea"))
    readonly property color badgeTop: plainDark ? "#2d2b30" : (dark ? "#453b47" : "#fff3f8")
    readonly property color badgeBottom: plainDark ? "#252529" : (dark ? "#302b36" : "#efbfd6")

    readonly property color panel: plainDark ? "#252529" : (liquidGlass ? (dark ? "#b32c2932" : "#b0ffffff") : (dark ? "#2a344d" : "#ffffff"))
    readonly property color panelSoft: plainDark ? "#222226" : (liquidGlass ? (dark ? "#8c302c36" : "#9cffffff") : (dark ? "#2c3650" : "#ffffff"))
    readonly property color panelFaint: plainDark ? "#2a2a2f" : (liquidGlass ? (dark ? "#4d38313f" : "#50ffffff") : (dark ? "#364161" : "#ffffff"))
    readonly property color panelHover: plainDark ? "#30292f" : (liquidGlass ? (dark ? "#ba403744" : "#f4ffffff") : (dark ? "#424e70" : "#ffffff"))
    readonly property color panelPressed: plainDark ? "#48313e" : (dark ? "#4c3549" : "#edc9dc")
    readonly property color line: plainDark ? "#3b3a41" : (liquidGlass ? (dark ? "#4dada0b4" : "#a4b4bad0") : (dark ? "#748aac" : "#b4bad0"))
    readonly property color softLine: plainDark ? "#303035" : (dark ? "#26c0b2ca" : "#26626e97")
    readonly property color popup: plainDark ? "#242428" : (liquidGlass ? (dark ? "#fa25222c" : "#fcf7f9ff") : (dark ? "#252d44" : "#f7f9ff"))
    readonly property color controlBase: plainDark ? "#252529" : (liquidGlass ? (dark ? "#28252e" : "#f7f9ff") : (dark ? "#252f47" : "#f7f9ff"))
    readonly property color controlHover: plainDark ? "#343037" : (liquidGlass ? (dark ? "#39323e" : "#e5eaf9") : (dark ? "#354362" : "#e5eaf9"))
    readonly property color controlSelected: plainDark ? "#45313e" : (liquidGlass ? (dark ? "#463244" : "#f8dfec") : (dark ? "#4f364b" : "#f8dfec"))
    readonly property color controlPressed: plainDark ? "#523342" : (liquidGlass ? (dark ? "#51374d" : "#edc9dc") : (dark ? "#5b3b52" : "#edc9dc"))
    readonly property color field: plainDark ? "#222226" : (liquidGlass ? (dark ? "#b32c2832" : "#ccffffff") : (dark ? "#29344f" : "#ffffff"))
    readonly property color fieldHover: plainDark ? "#2c292e" : (liquidGlass ? (dark ? "#cf38313e" : "#e9ffffff") : (dark ? "#303c5a" : "#ffffff"))
    readonly property color fieldFocus: plainDark ? "#30272e" : (liquidGlass ? (dark ? "#d9423647" : "#f5ffffff") : (dark ? "#354160" : "#ffffff"))
    readonly property color disabledFill: plainDark ? "#2c282d" : (dark ? "#405f3c51" : "#1da42b64")
    readonly property color imageBase: plainDark ? "#252529" : (liquidGlass ? (dark ? "#302b37" : "#dde3f4") : (dark ? "#3e4b6c" : "#dde3f4"))
    readonly property color coverVeil: dark ? "#b51c1922" : "#b8f2f3f8"
    readonly property color scrollHandle: plainDark ? "#68636d" : (dark ? "#788e8498" : "#80887c93")
    readonly property color glassHighlight: dark ? "#80ead8eb" : "#d9ffffff"
    readonly property real controlRadius: plainDark ? 10 : 12
    readonly property real panelRadius: plainDark ? 16 : 20
    readonly property real cardRadius: plainDark ? 16 : 20
    readonly property color hoverLine: plainDark ? "#70475c" : line
    readonly property color dangerFill: dark ? "#ed3b2834" : "#f8fff0f4"
    readonly property color dangerLine: dark ? "#ab667b" : "#d3a8b5"
}
