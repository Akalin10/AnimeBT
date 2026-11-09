import QtQuick
import QtQuick.Controls

Popup {
    id: popup
    required property GlassTheme colors
    required property GlassThemeManager optics
    property real cornerRadius: 16
    palette.windowText: colors.ink
    palette.text: colors.ink
    palette.buttonText: colors.ink
    popupType: Popup.Item
    dim: false
    padding: 6
    margins: 8
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: GlassPopupFrame {
        colors: popup.colors
        optics: popup.optics
        radius: popup.cornerRadius
    }
    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: popup.optics.motion; easing.type: Easing.OutCubic }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; to: 0; duration: popup.optics.motion * 0.65; easing.type: Easing.OutCubic }
    }
}
