import QtQuick

Item {
    id: frame
    required property GlassTheme colors
    required property GlassThemeManager optics
    property real radius: 20
    property int backdropTier: GlassSurface.Ambient
    property bool dimBackdrop: false
    property bool menuSurface: false

    GlassSurface {
        objectName: "popupGlass"
        anchors.fill: parent
        optics: frame.optics
        radius: frame.radius
        backdropTier: frame.backdropTier
        dimBackdrop: frame.dimBackdrop
        readingPanel: true
        menuSurface: frame.menuSurface
        material: GlassSurface.Panel
        readingPlate: true
        tint: frame.colors.controlBase
    }
}
