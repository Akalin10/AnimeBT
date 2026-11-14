import QtQuick
import QtQuick.Controls

Menu {
    id: menu
    required property GlassTheme colors
    required property GlassThemeManager optics
    property int backdropTier: GlassSurface.Ambient
    property bool dimBackdrop: false
    popupType: Popup.Item
    topInset: 0
    bottomInset: 0
    leftInset: 0
    rightInset: 0
    dim: false
    padding: 6
    margins: 8
    width: 192
    background: GlassPopupFrame {
        menuSurface: true
        colors: menu.colors
        optics: menu.optics
        radius: 13
        backdropTier: menu.backdropTier
        dimBackdrop: menu.dimBackdrop
    }
}
