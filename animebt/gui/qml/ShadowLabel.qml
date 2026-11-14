import QtQuick
import QtQuick.Controls
Label {
 id: label
 required property GlassTheme theme
 readonly property bool wallpaperShadowActive: theme.wallpaperTextShadow
 color: theme.ink
 style: wallpaperShadowActive ? Text.Raised : Text.Normal
 styleColor: theme.wallpaperShadowColor
}
