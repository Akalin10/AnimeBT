import QtQuick

Item {
    id: loading
    required property GlassTheme colors
    required property GlassThemeManager optics
    property bool animate: true
    implicitWidth: 64
    implicitHeight: 56
    width: implicitWidth
    height: implicitHeight

    GlassSurface {
        anchors.fill: parent
        optics: loading.optics
        radius: 16
        compact: true
        tint: loading.colors.controlBase
    }
    Glyph {
        id: spinner
        anchors.centerIn: parent
        path: "M10 2 A8 8 0 1 1 2 10"
        ink: loading.colors.accentText
        scale: 1.25
        NumberAnimation on rotation {
            running: loading.visible && loading.animate
            from: 0
            to: 360
            duration: 900
            loops: Animation.Infinite
        }
    }
}
