import QtQuick

// Share the existing cover shader on RHI. Canvas supplies an actual alpha clip
// on the software renderer, where ShaderEffect is unavailable.
Item {
    id: frame
    property alias source: image.source
    property alias sourceSize: image.sourceSize
    readonly property alias status: image.status
    property real radius: 8
    readonly property bool hardware: GraphicsInfo.api !== GraphicsInfo.Software

    Image {
        id: image
        objectName: "roundedCoverSource"
        anchors.fill: parent
        visible: false
        asynchronous: true
        cache: true
        smooth: true
        mipmap: true
        fillMode: Image.PreserveAspectCrop
    }
    ShaderEffect {
        objectName: "roundedCoverShader"
        anchors.fill: parent
        visible: frame.hardware && image.status === Image.Ready
        fragmentShader: "shaders/poster.frag.qsb"
        property var coverTexture: image
        property size frameSize: Qt.size(Math.max(1, width), Math.max(1, height))
        property size imageSize: Qt.size(Math.max(1, image.implicitWidth), Math.max(1, image.implicitHeight))
        property real corner: frame.radius
    }
    Canvas {
        id: software
        objectName: "roundedCoverSoftware"
        anchors.fill: parent
        visible: !frame.hardware
        property url loadedSource: ""
        function refresh() {
            if (!visible)
                return
            if (String(loadedSource) !== String(image.source)) {
                if (String(loadedSource))
                    unloadImage(loadedSource)
                loadedSource = image.source
                if (String(loadedSource))
                    loadImage(loadedSource)
            }
            requestPaint()
        }
        onVisibleChanged: refresh()
        Component.onCompleted: refresh()
        onImageLoaded: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Connections {
            target: image
            function onSourceChanged() { software.refresh() }
            function onStatusChanged() { software.refresh() }
        }
        Connections {
            target: frame
            function onRadiusChanged() { software.requestPaint() }
        }
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            ctx.clearRect(0, 0, width, height)
            if (!String(loadedSource) || !isImageLoaded(loadedSource) || image.status !== Image.Ready)
                return
            const r = Math.min(frame.radius, width / 2, height / 2)
            ctx.beginPath()
            ctx.moveTo(r, 0)
            ctx.lineTo(width - r, 0)
            ctx.quadraticCurveTo(width, 0, width, r)
            ctx.lineTo(width, height - r)
            ctx.quadraticCurveTo(width, height, width - r, height)
            ctx.lineTo(r, height)
            ctx.quadraticCurveTo(0, height, 0, height - r)
            ctx.lineTo(0, r)
            ctx.quadraticCurveTo(0, 0, r, 0)
            ctx.closePath()
            ctx.clip()
            const scale = Math.max(width / image.implicitWidth, height / image.implicitHeight)
            const w = image.implicitWidth * scale
            const h = image.implicitHeight * scale
            ctx.drawImage(loadedSource, (width - w) / 2, (height - h) / 2, w, h)
        }
    }
}
