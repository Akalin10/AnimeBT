import QtQuick
import QtQuick.Controls

Button {
    id: control
    required property GlassTheme colors
    required property GlassThemeManager optics
    property int backdropTier: GlassSurface.Ambient
    property bool dimBackdrop: false
    hoverEnabled: true
    leftPadding: 12
    rightPadding: 12
    scale: optics.motion > 0 && down ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: control.optics.motion; easing.type: Easing.OutCubic } }

    contentItem: ShadowText { theme: control.colors;
        text: control.text
        textFormat: Text.PlainText
        color: control.enabled ? control.colors.accentText : control.colors.muted
        font.pixelSize: control.colors.textSize
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: GlassSurface {
        material: GlassSurface.Control
        optics: control.optics
        implicitHeight: 38
        radius: control.colors.controlRadius
        backdropTier: control.backdropTier
        readingPlate: control.backdropTier !== GlassSurface.Ambient
        dimBackdrop: control.dimBackdrop
        tint: control.down ? control.colors.controlPressed
             : control.hovered ? control.colors.controlHover : control.colors.controlBase
        focused: control.visualFocus
        highlight: control.hovered || control.visualFocus ? 1 : 0
    }
}
