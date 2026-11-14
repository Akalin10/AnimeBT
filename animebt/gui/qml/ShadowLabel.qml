import QtQuick
import QtQuick.Controls
import QtQuick.Effects

Label {
    id: label

    required property GlassTheme theme

    property real shadowStrength: 1.0
    property real shadowBlur: 1.0
    property int shadowSamples: 48
    property real shadowSpread: 1.06

    readonly property bool wallpaperShadowActive:
        theme.wallpaperTextShadow

    readonly property real textLuminance:
        color.r * 0.2126 +
        color.g * 0.7152 +
        color.b * 0.0722

    readonly property color contrastShadowColor:
        textLuminance > 0.5
        ? "#ff000000"
        : "#ffffffff"

    font.family: theme.readingFamily
    font.weight: wallpaperShadowActive
        ? Font.DemiBold
        : Font.Normal

    color: theme.ink
    style: Text.Normal

    layer.enabled: wallpaperShadowActive

    layer.effect: MultiEffect {
        shadowEnabled: true
        shadowColor: label.contrastShadowColor
        shadowOpacity: Math.min(1, label.shadowStrength)
        shadowBlur: label.shadowBlur
        shadowScale: label.shadowSpread
        blurMax: label.shadowSamples

        shadowHorizontalOffset: 0
        shadowVerticalOffset: 0

        autoPaddingEnabled: true
    }
}