import QtQuick
import "../../animebt/gui/qml" as UI

Window {
    id: root
    width: 960
    height: 620
    visible: true
    color: "#101826"
    property bool dark: false
    property real bend: 1
    property real lightPower: 1
    property real blurPower: 0
    property real tintLevel: 0
    property real shift: 0
    property bool moving: false
    property var frameIntervals: []
    FrameAnimation {
        running: root.moving
        onTriggered: if (frameTime > 0) root.frameIntervals.push(frameTime * 1000)
    }
    NumberAnimation on shift { from: 0; to: 32; duration: 1200; loops: Animation.Infinite; running: root.moving }
    UI.GlassTheme { id: palette; dark: root.dark }
    Item {
        id: pattern
        anchors.fill: parent
        Rectangle { anchors.fill: parent; color: root.dark ? "#102037" : "#c8d9e8" }
        Item {
            x: root.shift - 32
            Repeater {
                model: 64
                Rectangle {
                    required property int index
                    x: index * 16
                    width: 7
                    height: root.height
                    color: root.dark ? "#6985ac" : "#2b6094"
                }
            }
        }
        Repeater {
            model: 17
            Rectangle {
                required property int index
                y: 42 + index * 34
                width: root.width
                height: 1
                color: root.dark ? "#d29666" : "#b97a45"
            }
        }
        Text {
            x: 50; y: 100
            text: "REAL BACKGROUND / 实时背景 / 背景の文字"
            color: root.dark ? "#eeeeee" : "#142334"
            font.pixelSize: 20
        }
    }
    UI.GlassBackdrop { id: texture; sourceItem: pattern }
    UI.GlassThemeManager {
        id: glassOptics
        colors: palette
        level: root.tintLevel
        enabled: true
        motion: 120
        viewport: Qt.size(root.width, root.height)
        ambientBackdrop: texture
        sceneBackdrop: texture
        dialogBackdrop: texture
        dialogRect: Qt.rect(0, 0, 0, 0)
        refractionStrength: root.bend
        edgeStrength: root.lightPower
        blurStrength: root.blurPower
    }
    Text { x: 40; y: 18; text: root.bend > 0 ? "实时纹理折射 / Fresnel" : "静态透色：折射、反射关闭"; color: "white"; font.pixelSize: 22 }
    UI.GlassSurface {
        objectName: "opticsProbe"
        x: 40; y: 100; width: 400; height: 90
        radius: 36
        readable: false
        optics: glassOptics
    }
    UI.GlassSurface {
        x: 520; y: 100; width: 400; height: 90
        radius: 36
        optics: glassOptics
        Text { anchors.centerIn: parent; text: "搜索框 · Search"; color: palette.ink; font.pixelSize: 22 }
    }
    UI.GlassSurface {
        x: 40; y: 230; width: 880; height: 64
        radius: 20
        material: UI.GlassSurface.Chrome
        optics: glassOptics
        Text { anchors.centerIn: parent; text: "固定顶栏 / Chrome"; color: palette.ink; font.pixelSize: 20 }
    }
    UI.GlassSurface {
        x: 40; y: 340; width: 400; height: 200
        radius: 20
        material: UI.GlassSurface.Panel
        readingPanel: true
        readingPlate: true
        optics: glassOptics
        Text { anchors.centerIn: parent; text: "弹窗阅读区域\n清晰文字，不采样自身"; color: palette.ink; font.pixelSize: 20 }
    }
    UI.GlassSurface {
        x: 520; y: 340; width: 400; height: 92
        radius: 14
        readingPlate: true
        compact: true
        optics: glassOptics
        Text { anchors.centerIn: parent; text: "资源卡片 · 阅读底板"; color: palette.ink; font.pixelSize: 20 }
    }
    UI.GlassSurface {
        x: 520; y: 458; width: 190; height: 64
        radius: 28
        focused: true
        optics: glassOptics
        Text { anchors.centerIn: parent; text: "悬停高光"; color: palette.ink; font.pixelSize: 18 }
    }
    UI.GlassSurface {
        objectName: "menuOpticsProbe"
        x: 730; y: 458; width: 190; height: 64
        radius: 13
        menuSurface: true
        readingPanel: true
        readingPlate: true
        material: UI.GlassSurface.Panel
        optics: glassOptics
        Text { anchors.centerIn: parent; text: "菜单消字"; color: palette.ink; font.pixelSize: 18 }
    }
}
