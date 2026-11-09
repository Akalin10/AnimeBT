import QtQuick
import QtQuick.Controls

Menu {
    id: menu
    required property GlassTheme colors
    required property GlassThemeManager optics
    property int backdropTier: GlassSurface.Scene
    property bool dimBackdrop: false
    popupType: Popup.Item
    dim: false
    padding: 6
    margins: 8
    width: 192
    background: GlassPopupFrame {
        colors: menu.colors
        optics: menu.optics
        radius: 13
        backdropTier: menu.backdropTier
        dimBackdrop: menu.dimBackdrop
    }
}
