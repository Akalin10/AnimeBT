import QtQuick

QtObject {
    required property GlassTheme colors
    required property real level
    required property bool enabled
    required property int motion
    required property size viewport
    required property var ambientBackdrop
    required property var sceneBackdrop
    required property var dialogBackdrop
    required property rect dialogRect
    property int sceneUsers: 0
    property int dialogUsers: 0

    readonly property color tint: colors.dark ? "#242e46" : "#f4f7ff"
    readonly property color tintedTone: colors.dark ? "#374b68" : "#d5e0f7"
    readonly property color edge: Qt.rgba(colors.frame.r, colors.frame.g, colors.frame.b,
                                         colors.frame.a * (0.68 + 0.32 * level))
    readonly property color focusColor: colors.accent
    readonly property real tintAmount: 0.16 + 0.77 * level
    readonly property real blurRadius: 0.65 + 4.0 * level
    readonly property real refraction: 18 - 6 * level
    readonly property real highlight: 0.86 - 0.16 * level
    readonly property real modalDim: 0.32
    readonly property vector2d readingRange: colors.dark ? Qt.vector2d(0, 0.27) : Qt.vector2d(0.86, 1)

    function changeConsumers(tier, delta) {
        if (tier >= 1)
            sceneUsers += delta
        if (tier === 2)
            dialogUsers += delta
    }

    function materialColor(seed) {
        const mix = 0.42 * level
        return Qt.rgba(seed.r + (tintedTone.r - seed.r) * mix,
                       seed.g + (tintedTone.g - seed.g) * mix,
                       seed.b + (tintedTone.b - seed.b) * mix, 1)
    }

    function flatColor(tintColor, readable) {
        const tone = materialColor(tintColor)
        const lo = readable && !colors.dark ? 0.90 : 0
        const hi = readable && colors.dark ? 0.26 : 1
        const r = Math.max(lo, Math.min(hi, tone.r))
        const g = Math.max(lo, Math.min(hi, tone.g))
        const b = Math.max(lo, Math.min(hi, tone.b))
        return Qt.rgba(r, g, b, readable ? 0.95 + 0.048 * level : 0.38 + 0.57 * level)
    }

    function readingColor(seed) {
        const tone = materialColor(seed)
        const lo = readingRange.x
        const hi = readingRange.y
        return Qt.rgba(Math.max(lo, Math.min(hi, tone.r)),
                       Math.max(lo, Math.min(hi, tone.g)),
                       Math.max(lo, Math.min(hi, tone.b)), 1)
    }
}
