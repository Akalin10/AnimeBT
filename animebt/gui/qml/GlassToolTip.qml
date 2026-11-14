import QtQuick
import QtQuick.Controls

ToolTip {
    id: tip
    required property GlassTheme colors
    required property GlassThemeManager optics
    padding: 12
    margins: 8
    contentItem: ShadowText { theme: tip.colors;
        baseStyle: tip.colors.liquidGlass ? Text.Outline : Text.Normal

        text: tip.text
        textFormat: Text.PlainText
        color: tip.colors.ink
        wrapMode: Text.Wrap
        font.pixelSize: tip.colors.detailTextSize
    }
    background: GlassPopupFrame {
        colors: tip.colors
        optics: tip.optics
        radius: 14
        menuSurface: true
    }
}
