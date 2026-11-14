import QtQuick
import QtQuick.Controls
CheckBox {
 id:control
 required property GlassTheme colors
 required property GlassThemeManager optics
 hoverEnabled:true;leftPadding:32;rightPadding:4;topPadding:8;bottomPadding:8
 indicator:Rectangle {
  x:0;y:(control.height-height)/2;width:22;height:22;radius:7
  color:"transparent"
  border.color:control.checked || control.visualFocus ? control.colors.accent : control.colors.line
  Glyph {anchors.centerIn:parent;width:15;height:15;visible:control.checked;ink:control.colors.accentText;path:"M4 10 L8 14 L16 6"}
 }
 contentItem:ShadowText { theme: control.colors;text:control.text;color:control.colors.ink;font.pixelSize:control.colors.textSize;verticalAlignment:Text.AlignVCenter}
}
