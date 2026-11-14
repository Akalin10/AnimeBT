import QtQuick
Item {
    id: backdrop
    required property GlassTheme colors
    property real radius: 0
    property real strength: 1
    Rectangle {
        anchors.fill: parent
        visible: !backdrop.colors.liquidGlass || GraphicsInfo.api === GraphicsInfo.Software
        radius: backdrop.radius
        color: backdrop.colors.backgroundTop
        gradient: backdrop.colors.liquidGlass ? softwareGradient : null
        Gradient {
            id: softwareGradient
            GradientStop { position: 0; color: backdrop.colors.backgroundTop }
            GradientStop { position: 1; color: backdrop.colors.backgroundBottom }
        }
    }
    Loader {
        anchors.fill: parent
        active: backdrop.visible && backdrop.colors.liquidGlass && GraphicsInfo.api !== GraphicsInfo.Software
        sourceComponent: ShaderEffect {
            objectName: "ambientGlassShader"
            vertexShader: "shaders/ambient.vert.qsb"
            fragmentShader: "shaders/ambient.frag.qsb"
            property real dark: backdrop.colors.dark ? 1 : 0
            property real corner: backdrop.radius
            property real strength: backdrop.strength
            property size size: Qt.size(width,height)
            property color topColor: backdrop.colors.backgroundTop
            property color bottomColor: backdrop.colors.backgroundBottom
        }
    }
}
