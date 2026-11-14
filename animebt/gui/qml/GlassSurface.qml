import QtQuick

Item {
    id: glass
    enum Backdrop { Ambient, Scene, Dialog }
    enum Material { Control, Chrome, Panel, Card }
    required property GlassThemeManager optics
    property int backdropTier: GlassSurface.Ambient
    property bool dimBackdrop: false
    property bool readable: true
    property bool readingPanel: false
    property bool readingPlate: false
    property bool menuSurface: false
    property int material: readingPlate ? GlassSurface.Card : readingPanel ? GlassSurface.Panel : GlassSurface.Control
    property real readingRim: 4
    property bool compact: false
    property bool renderOptics: true
    property real radius: 14
    property bool focused: false
    property real highlight: focused ? 1 : 0
    Behavior on highlight { NumberAnimation { duration: glass.optics.motion; easing.type: Easing.OutCubic } }
    property color outline: focused ? optics.focusColor : "transparent"
    property color tint: optics.tint
    readonly property bool refracting: optics.enabled && renderOptics
    readonly property int requestedTier: visible && refracting ? backdropTier : GlassSurface.Ambient
    property int registeredTier: GlassSurface.Ambient

    onRequestedTierChanged: {
        optics.changeConsumers(registeredTier, -1)
        optics.changeConsumers(requestedTier, 1)
        registeredTier = requestedTier
    }
    Component.onDestruction: if (optics) optics.changeConsumers(registeredTier, -1)

    Rectangle {
        objectName: "plainSurface"
        anchors.fill: parent
        visible: !glass.optics.liquidGlass
        radius: glass.radius
        color: glass.optics.flatColor(glass.tint, glass.readable)
        border.color: glass.optics.colors.plainDark && glass.highlight > 0
                      ? glass.optics.colors.hoverLine : glass.optics.colors.line
    }

    Loader {
        anchors.fill: parent
        active: glass.visible && glass.refracting
        sourceComponent: ShaderEffect {
            objectName: "liquidGlassShader"
            vertexShader: "shaders/glass.vert.qsb"
            fragmentShader: "shaders/glass.frag.qsb"
            property var backdrop: glass.backdropTier === GlassSurface.Scene
                                   ? glass.optics.sceneBackdrop : glass.optics.ambientBackdrop
            property var upperBackdrop: glass.backdropTier === GlassSurface.Dialog
                                        ? glass.optics.dialogBackdrop : glass.optics.ambientBackdrop
            property rect upperRect: glass.backdropTier === GlassSurface.Dialog
                                     ? glass.optics.dialogRect : Qt.rect(0, 0, 0, 0)
            property real dim: glass.dimBackdrop ? glass.optics.modalDim : 0
            property real corner: glass.radius
            property real tintAmount: glass.optics.tintAmount
            property real blurRadius: glass.optics.sharedBlur ? 0 : glass.optics.blurRadius
            property real refraction: glass.optics.refraction
            property real compact: glass.compact ? 1 : 0
            property real panel: glass.menuSurface ? 2 : glass.readingPanel ? 1 : 0
            property real material: glass.material
            property real highlight: glass.highlight
            property real opticalStrength: glass.optics.edgeStrength
            property real plateRim: glass.readingPlate ? glass.readingRim : -1
            property vector2d readingRange: glass.readable ? glass.optics.readingRange : Qt.vector2d(0, 1)
            property size controlSize: Qt.size(width, height)
            property size viewportSize: glass.optics.viewport
            property color tintColor: glass.optics.materialColor(glass.tint)
        }
    }

    // Software/disabled fallback is clear: never restore a reading plate.
    Rectangle {
        anchors.fill: parent
        visible: glass.outline.a > 0
        radius: glass.radius
        color: "transparent"
        border.color: glass.outline
    }
}
