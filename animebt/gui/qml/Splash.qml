import QtQuick

Rectangle {
    id: splash
    objectName: "animebtSplash"
    required property GlassTheme colors
    property bool started: false
    property bool revealing: false
    signal finished()

    function start() {
        if (!started) {
            started = true
            timeline.start()
        }
    }

    function opaque(color) {
        return Qt.rgba(color.r, color.g, color.b, 1)
    }

    border.color: colors.frame
    gradient: Gradient {
        GradientStop { position: 0; color: splash.opaque(splash.colors.backgroundTop) }
        GradientStop { position: 0.58; color: splash.opaque(splash.colors.backgroundMiddle) }
        GradientStop { position: 1; color: splash.opaque(splash.colors.backgroundBottom) }
    }

    Column {
        anchors.centerIn: parent
        spacing: 16

        Image {
            id: logo
            anchors.horizontalCenter: parent.horizontalCenter
            source: "../assets/icon.png"
            width: 96
            height: 96
            fillMode: Image.PreserveAspectFit
            smooth: true
            mipmap: true
            opacity: 0
            scale: 0.95
        }

        Text {
            id: brand
            anchors.horizontalCenter: parent.horizontalCenter
            text: "AnimeBT"
            color: colors.ink
            font.pixelSize: 27
            font.weight: Font.DemiBold
            opacity: 0
        }
    }

    SequentialAnimation {
        id: timeline
        ParallelAnimation {
            OpacityAnimator { target: logo; from: 0; to: 1; duration: 500; easing.type: Easing.OutCubic }
            ScaleAnimator { target: logo; from: 0.95; to: 1; duration: 500; easing.type: Easing.OutCubic }
            SequentialAnimation {
                PauseAnimation { duration: 130 }
                OpacityAnimator { target: brand; from: 0; to: 1; duration: 430; easing.type: Easing.OutCubic }
            }
        }
        PauseAnimation { duration: 430 }
        ScriptAction { script: splash.revealing = true }
        NumberAnimation {
            target: splash
            property: "opacity"
            from: 1
            to: 0
            duration: 320
            easing.type: Easing.InOutCubic
        }
        onFinished: splash.finished()
    }
}
