import QtQuick

Item {
    id: wallpaper
    objectName: "wallpaperBackground"
    property url source
    property bool enabledWallpaper: false
    property bool fit: false
    property real brightness: 100
    readonly property real shadeOpacity: 0.6 * (1 - Math.max(0, Math.min(100, brightness)) / 100)
    property real radius: 0
    readonly property bool hardware: GraphicsInfo.api !== GraphicsInfo.Software
    readonly property int decodeEdge: Math.min(4096, Math.max(2048, Math.ceil(Math.max(Screen.width, Screen.height) * Screen.devicePixelRatio / 512) * 512))
    readonly property bool active: enabledWallpaper && hardware && image.status === Image.Ready
    readonly property alias imageStatus: image.status
    readonly property size decodedSize: Qt.size(image.implicitWidth, image.implicitHeight)
    signal failed()
    signal ready()

    Image {
        id: image
        objectName: "wallpaperImageSource"
        visible: false
        source: wallpaper.enabledWallpaper && wallpaper.hardware ? wallpaper.source : ""
        asynchronous: true
        cache: true
        mipmap: true
        smooth: true
        autoTransform: true
        // A stable decode budget avoids reloading during window resize/DPI changes.
        sourceSize: Qt.size(wallpaper.decodeEdge, wallpaper.decodeEdge)
        // This hidden Image provides texture pixels only. Qt's aspect modes
        // expand the requested decode box; Stretch bounds decode to that box.
        // The wallpaper shader preserves the original decoded aspect for display.
        fillMode: Image.Stretch
        onStatusChanged: {
            if (status === Image.Error) wallpaper.failed()
            if (status === Image.Ready) wallpaper.ready()
        }
    }
    Loader {
        anchors.fill: parent
        active: wallpaper.active
        sourceComponent: ShaderEffect {
            objectName: "wallpaperShader"
            fragmentShader: "shaders/wallpaper.frag.qsb"
            property var coverTexture: image
            property size frameSize: Qt.size(Math.max(1,width), Math.max(1,height))
            property size imageSize: Qt.size(Math.max(1,image.implicitWidth), Math.max(1,image.implicitHeight))
            property real corner: wallpaper.radius
            property real fit: wallpaper.fit ? 1 : 0
            property real shadeOpacity: wallpaper.shadeOpacity
        }
    }
}
