import QtQuick
import QtQuick.Controls

RadioButton {
    id: control
    required property GlassTheme colors
    required property GlassThemeManager optics
    leftPadding: 32
    rightPadding: 12
    topPadding: 8
    bottomPadding: 8
    hoverEnabled: true
    indicator: Rectangle {
        x: 10
        anchors.verticalCenter: parent.verticalCenter
        width: 14
        height: 14
        radius: 7
        color: "transparent"
        border.color: control.checked ? colors.accent : colors.muted
        Rectangle {
            anchors.centerIn: parent
            width: 8
            height: 8
            radius: 4
            visible: control.checked
            color: colors.accent
        }
    }
    contentItem: ShadowText { theme: control.colors;
        text: control.text
        color: control.colors.ink
        font.pixelSize: control.colors.textSize
        verticalAlignment: Text.AlignVCenter
    }
    background: GlassSurface {
        optics: control.optics
        radius: control.colors.controlRadius
        focused: control.visualFocus
        tint: control.checked ? colors.controlPressed : control.hovered ? colors.controlHover : colors.controlBase
    }
}
