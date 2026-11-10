import QtQuick
import QtQuick.Controls

MenuItem {
    id: entry
    required property GlassTheme colors
    required property GlassThemeManager optics
    property int backdropTier: GlassSurface.Scene
    property bool dimBackdrop: false
    property bool selected: checked
    hoverEnabled: true
    padding: 8
    leftPadding: 12
    rightPadding: selected ? 32 : 12
    indicator: null
    arrow: null

    contentItem: Text {
        text: entry.text
        textFormat: Text.PlainText
        color: !entry.enabled ? entry.colors.muted : entry.selected ? entry.colors.accentText : entry.colors.ink
        font.pixelSize: 13
        font.weight: entry.selected ? Font.DemiBold : Font.Normal
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: GlassSurface {
        optics: entry.optics
        backdropTier: entry.backdropTier
        dimBackdrop: entry.dimBackdrop
        compact: true
        readingPlate: true
        implicitHeight: 34
        radius: 9
        tint: !entry.enabled ? entry.colors.controlBase
             : entry.down ? entry.colors.controlPressed
             : entry.highlighted || entry.hovered ? entry.colors.controlHover
             : entry.selected ? entry.colors.controlSelected : entry.colors.controlBase
        focused: entry.visualFocus || entry.highlighted
        Glyph {
            visible: entry.selected
            anchors.right: parent.right
            anchors.rightMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            width: 15
            height: 15
            ink: entry.colors.accentText
            path: "M4 10 L8 14 L16 6"
        }
    }
}
