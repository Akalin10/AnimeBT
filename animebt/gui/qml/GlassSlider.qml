import QtQuick
import QtQuick.Controls

Slider {
    id: control
    required property GlassTheme colors
    required property GlassThemeManager optics
    from: 0
    to: 1
    stepSize: 0.01
    implicitWidth: 240
    implicitHeight: 40
    leftPadding: 12
    rightPadding: 12
    hoverEnabled: true
    background: GlassSurface {
        optics: control.optics
        radius: 12
        compact: true
        tint: control.colors.controlBase
        focused: control.visualFocus
        Rectangle {
            x: control.leftPadding + 10
            y: (parent.height - height) / 2
            width: Math.max(0, control.availableWidth - 20)
            height: 3
            radius: 1.5
            color: control.colors.line
            Rectangle {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width * control.visualPosition
                height: parent.height
                radius: parent.radius
                color: control.colors.accent
            }
        }
    }
    handle: GlassSurface {
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        y: (control.height - height) / 2
        width: 20
        height: 20
        radius: 10
        optics: control.optics
        tint: control.pressed ? control.colors.accentPressed : control.colors.accentFill
        focused: control.pressed || control.visualFocus
        outline: control.visualFocus ? control.colors.accent : "transparent"
        readable: false
    }
}
