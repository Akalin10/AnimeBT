import QtQuick
import QtQuick.Controls

MenuItem {
    id: entry
    required property GlassTheme colors
    required property GlassThemeManager optics
    property int backdropTier: GlassSurface.Ambient
    property bool dimBackdrop: false
    property bool selected: checked
    hoverEnabled: true
    padding: 8
    leftPadding: 12
    rightPadding: selected ? 32 : 12
    indicator: null
    arrow: null

    contentItem: ShadowText { theme: entry.colors;
        baseStyle: entry.colors.liquidGlass ? Text.Outline : Text.Normal

        text: entry.text
        textFormat: Text.PlainText
        color: !entry.enabled ? entry.colors.muted : entry.selected ? entry.colors.accentText : entry.colors.ink
        font.pixelSize: entry.colors.textSize
        font.weight: entry.selected ? Font.Bold : Font.DemiBold
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: GlassSurface {
        visible: entry.selected || entry.highlighted || entry.hovered || entry.down || entry.visualFocus
        menuSurface: true
        material: GlassSurface.Control
        optics: entry.optics
        backdropTier: entry.backdropTier
        dimBackdrop: entry.dimBackdrop
        compact: true
        readingPlate: true
        implicitHeight: 38
        radius: 9
        tint: !entry.enabled ? entry.colors.controlBase
             : entry.down ? entry.colors.controlPressed
             : entry.highlighted || entry.hovered ? entry.colors.controlHover
             : entry.selected ? entry.colors.controlSelected : entry.colors.controlBase
        focused: entry.visualFocus
        outline: entry.visualFocus ? entry.colors.accent : "transparent"
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
