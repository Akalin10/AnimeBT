import QtQuick
import QtQuick.Controls
ScrollBar {
 id:bar
 required property GlassTheme colors
 implicitWidth:8;implicitHeight:8;minimumSize:.06;padding:2
 contentItem:Rectangle {
  implicitWidth:4;implicitHeight:4;radius:2
  color:bar.pressed ? bar.colors.accent : bar.colors.scrollHandle
  opacity:bar.active || bar.pressed || bar.hovered ? .9 : .4
 }
 background:Item {}
}
