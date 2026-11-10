import QtQuick

Item {
    id: glass
    enum Backdrop { Ambient, Scene, Dialog }
    required property GlassThemeManager optics
    property int backdropTier: GlassSurface.Ambient
    property bool dimBackdrop: false
    property bool readable: true
    property bool readingPanel: false
    property bool readingPlate: false
    property real readingRim: 4
    property bool compact: false
    property bool renderOptics: true
    property real radius: 14
    property bool focused: false
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
        anchors.fill: parent
        visible: !glass.refracting && !glass.readingPlate
        radius: glass.radius
        color: glass.optics.flatColor(glass.tint, glass.readable)
        border.color: glass.optics.edge
    }

    Loader {
        anchors.fill: parent
        active: glass.visible && glass.refracting
        sourceComponent: ShaderEffect {
            objectName: "liquidGlassShader"
            vertexShader: "shaders/glass.vert.qsb"
            fragmentShader: "shaders/glass.frag.qsb"
            property var backdrop: glass.backdropTier === GlassSurface.Ambient
                                   ? glass.optics.ambientBackdrop : glass.optics.sceneBackdrop
            property var upperBackdrop: glass.backdropTier === GlassSurface.Dialog
                                        ? glass.optics.dialogBackdrop : glass.optics.ambientBackdrop
            property rect upperRect: glass.backdropTier === GlassSurface.Dialog
                                     ? glass.optics.dialogRect : Qt.rect(0, 0, 0, 0)
            property real dim: glass.dimBackdrop ? glass.optics.modalDim : 0
            property real corner: glass.radius
            property real tintAmount: glass.optics.tintAmount
            property real blurRadius: glass.optics.blurRadius
            property real refraction: glass.optics.refraction
            property real compact: glass.compact ? 1 : 0
            property real panel: glass.readingPanel ? 1 : 0
            property vector2d readingRange: glass.readable ? glass.optics.readingRange : Qt.vector2d(0, 1)
            property size controlSize: Qt.size(width, height)
            property size viewportSize: glass.optics.viewport
            property color tintColor: glass.optics.materialColor(glass.tint)
        }
    }

    // Keep sampled detail at the rim, outside the foreground reading area.
    Rectangle {
        objectName: "glassReadingPlate"
        visible: glass.readingPlate
        anchors.fill: parent
        anchors.margins: glass.refracting ? glass.readingRim : 0
        radius: Math.max(0, glass.radius - anchors.margins)
        color: glass.optics.readingColor(glass.tint)
    }

    Rectangle {
        anchors.fill: parent
        visible: glass.outline.a > 0
        radius: glass.radius
        color: "transparent"
        border.color: glass.outline
    }
}
