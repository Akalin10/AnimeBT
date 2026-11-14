import QtQuick
import QtQuick.Controls
Switch {
 id: control
 required property GlassTheme colors
 required property GlassThemeManager optics
 hoverEnabled:true
 leftPadding:54;rightPadding:4;topPadding:10;bottomPadding:10
 indicator: Rectangle {
  x:0;y:(control.height-height)/2;width:44;height:26;radius:13
  color:control.colors.plainDark ? (control.checked ? control.colors.accentPressed : control.colors.panelFaint) : "transparent"
  border.width:1;border.color:control.visualFocus ? control.colors.accent : control.colors.line
  Rectangle {
   x:control.checked ? 21 : 3;y:3;width:20;height:20;radius:10
   color:control.colors.plainDark && control.checked ? control.colors.ink : control.checked ? control.colors.accentText : control.colors.muted
   Behavior on x { NumberAnimation { duration:control.optics.motion;easing.type:Easing.OutCubic } }
  }
 }
 contentItem:ShadowText { theme: control.colors;text:control.text;color:control.enabled ? control.colors.ink : control.colors.muted;font.pixelSize:control.colors.textSize;verticalAlignment:Text.AlignVCenter}
}
