import QtQuick

QtObject {
    required property GlassTheme colors
    required property real level
    property bool liquidGlass: true
    property bool sharedBlur: false
    required property bool enabled
    required property int motion
    required property size viewport
    required property var ambientBackdrop
    required property var sceneBackdrop
    required property var dialogBackdrop
    required property rect dialogRect
    property int sceneUsers: 0
    property int dialogUsers: 0
    // Global optical parameters, shared by all material tiers.
    property real refractionStrength: 1.0
    property real blurStrength: 1.0
    property real edgeStrength: 0.75

    readonly property color tint: liquidGlass ? (colors.dark ? "#26232d" : "#f4f7ff") : colors.controlBase
    readonly property color tintedTone: colors.dark ? "#443747" : "#d5e0f7"
    readonly property color edge: Qt.rgba(colors.frame.r, colors.frame.g, colors.frame.b,
                                         colors.frame.a * (0.62 + 0.28 * level))
    readonly property color focusColor: colors.accent
    readonly property real tintAmount: 0
    readonly property real blurRadius: 18 * Math.pow(Math.max(0, Math.min(1, level)), 1.25) * Math.max(0, blurStrength)
    readonly property real refraction: (12 - 4 * level) * Math.max(0, refractionStrength)
    readonly property real modalDim: 0
    readonly property vector2d readingRange: Qt.vector2d(0, 1)

    function changeConsumers(tier, delta) {
        if (tier === 1)
            sceneUsers += delta
        if (tier === 2)
            dialogUsers += delta
    }

    // Compatibility helpers for existing callers. All surfaces transmit without fill.
    function materialColor(seed) { return "transparent" }
    function flatColor(seed, readable) { return liquidGlass ? "transparent" : Qt.rgba(seed.r, seed.g, seed.b, 1) }
    function readingColor(seed) { return "transparent" }
}
