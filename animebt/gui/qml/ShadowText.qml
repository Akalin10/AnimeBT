import QtQuick
Text {
 id: label
 required property GlassTheme theme
 property int baseStyle: Text.Normal
 readonly property bool wallpaperShadowActive: theme.wallpaperTextShadow
 color: theme.ink
 style: wallpaperShadowActive ? Text.Raised : baseStyle
 styleColor: wallpaperShadowActive ? theme.wallpaperShadowColor : (color.r+color.g+color.b>1.5 ? "#a0000000" : "#c0ffffff")
}
