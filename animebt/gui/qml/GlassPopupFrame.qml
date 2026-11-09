import QtQuick
import QtQuick.Effects

Item {
    id: frame
    required property GlassTheme colors
    required property GlassThemeManager optics
    property real radius: 16
    property int backdropTier: GlassSurface.Scene
    property bool dimBackdrop: false

    Rectangle {
        id: silhouette
        anchors.fill: parent
        radius: frame.radius
        color: frame.colors.controlBase
        visible: false
    }

    MultiEffect {
        anchors.fill: parent
        visible: GraphicsInfo.api !== GraphicsInfo.Software
        source: silhouette
        shadowEnabled: true
        shadowBlur: 0.72
        blurMax: 18
        shadowVerticalOffset: 5
        shadowColor: frame.colors.shadow
    }

    GlassSurface {
        objectName: "popupGlass"
        anchors.fill: parent
        optics: frame.optics
        radius: frame.radius
        backdropTier: frame.backdropTier
        dimBackdrop: frame.dimBackdrop
        readingPanel: true
        readingPlate: true
        tint: frame.colors.controlBase
        shine: 0.30
    }
}
