import QtQuick
import QtQuick.Controls

ToolTip {
    id: tip
    required property GlassTheme colors
    required property GlassThemeManager optics
    padding: 9
    margins: 8
    contentItem: Text {
        text: tip.text
        textFormat: Text.PlainText
        color: tip.colors.ink
        wrapMode: Text.Wrap
        font.pixelSize: 13
    }
    background: GlassPopupFrame {
        colors: tip.colors
        optics: tip.optics
        radius: 10
    }
}
