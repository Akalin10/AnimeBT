import QtQuick

Text {
    id: label
    property int baseStyle: Text.Normal
    property bool softTextShadow: true // Retained for existing resource-title declarations.
    required property GlassTheme theme
    readonly property bool wallpaperShadowActive: theme.wallpaperTextShadow
    readonly property real textLuminance: color.r * 0.2126 + color.g * 0.7152 + color.b * 0.0722
    readonly property bool lightTextOnWallpaper: wallpaperShadowActive && textLuminance > 0.5
    font.family: theme.readingFamily
    font.weight: Font.Medium
    renderType: Text.QtRendering
    renderTypeQuality: 104
    antialiasing: true
    color: theme.ink
    // Smooth high-quality glyphs with a small native shadow, never a full outline.
    style: lightTextOnWallpaper ? Text.Raised : Text.Normal
    styleColor: "#80000000"
}
