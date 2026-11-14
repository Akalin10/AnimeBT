import QtQuick

// Two shared Gaussian passes, never one full-image blur per glass control.
Item {
    id: blur
    objectName: "sharedBackdropBlur"
    required property var sourceTexture
    required property bool enabledBlur
    required property real radius
    required property size viewport
    width: viewport.width
    height: viewport.height
    readonly property bool running: enabledBlur && radius > 0.01
    readonly property var texture: running ? verticalTexture : sourceTexture
    Loader {
        id: horizontal
        anchors.fill: parent
        active: blur.running
        sourceComponent: ShaderEffect {
            objectName: "horizontalBackdropBlurShader"
            fragmentShader: "shaders/backdropblur.frag.qsb"
            property var sourceTexture: blur.sourceTexture
            property vector2d direction: Qt.vector2d(1 / Math.max(1,blur.width),0)
            property real radius: blur.radius
        }
    }
    GlassBackdrop {
        id: horizontalTexture
        objectName: "horizontalBlurCapture"
        sourceItem: blur.running ? horizontal.item : null
        hideSource: true
    }
    Loader {
        id: vertical
        anchors.fill: parent
        active: blur.running
        sourceComponent: ShaderEffect {
            objectName: "verticalBackdropBlurShader"
            fragmentShader: "shaders/backdropblur.frag.qsb"
            property var sourceTexture: horizontalTexture
            property vector2d direction: Qt.vector2d(0,1 / Math.max(1,blur.height))
            property real radius: blur.radius
        }
    }
    GlassBackdrop {
        id: verticalTexture
        objectName: "verticalBlurCapture"
        sourceItem: blur.running ? vertical.item : null
        hideSource: true
    }
}
