import QtQuick
import QtQuick.Controls
import DesktopGlass 1.0
import "../../animebt/gui/qml" as UI
Window {
    id: root
    width: 920; height: 590; visible: true
    title: "AnimeBT — Desktop Glass Prototype (capture OFF by default)"
    color: "transparent"
    property bool dark: false
    property real testBend:1;property real testBlur:1;property real testEdge:1
    UI.GlassTheme { id: palette; dark: root.dark }
    UI.GlassThemeManager {
        id: optics; colors: palette; level: tint.value; enabled: true; motion: 180
        viewport: Qt.size(root.width,root.height)
        ambientBackdrop: capture.available ? liveSource : fallbackSource
        sceneBackdrop: ambientBackdrop; dialogBackdrop: ambientBackdrop; dialogRect: Qt.rect(0,0,0,0)
        refractionStrength: bend.value * root.testBend; blurStrength: blur.value * root.testBlur;edgeStrength:root.testEdge
    }
    Item {
        id: fallback; anchors.fill: parent
        Rectangle { anchors.fill: parent; color: root.dark ? "#19243c" : "#e5ecf7" }
        Text { anchors.centerIn: parent; text: "Application background\nCapture is disabled"; color: palette.ink; horizontalAlignment: Text.AlignHCenter }
    }
    ShaderEffectSource { id: fallbackSource; sourceItem: fallback; hideSource: true; live: true }
    DesktopTexture { id: desktop; controller:capture; anchors.fill: parent }
    ShaderEffectSource { id: liveSource; sourceItem: desktop; hideSource: true; live: true; textureSize: Qt.size(root.width * root.devicePixelRatio, root.height * root.devicePixelRatio) }
    UI.GlassSurface { anchors.fill: parent; optics: optics; radius: 24; readable: false }
    UI.GlassSurface { x:16;y:16;width:root.width-32;height:143;radius:18;optics:optics;readingPanel:true;readingPlate:true;material:UI.GlassSurface.Panel }
    Button { x:root.width-140;y:root.height-40;width:120;height:30;text:"Input probe";onPressed:capture.inputProbe() }
    Column {
        anchors.fill: parent; anchors.margins: 30; spacing: 22
        Row {
            spacing: 16
            Text { text: "AnimeBT · Desktop Glass"; color: palette.ink; font.pixelSize: 24 }
            Button { text: capture.active ? "Stop capture" : "Enable desktop capture"; onClicked: capture.active ? capture.stop() : capture.start() }
            Switch { text: "Dark"; checked: root.dark; onToggled: root.dark=checked }
        }
        Text { text: capture.message; color: palette.ink; font.pixelSize: 14 }
        Row {
            spacing: 12
            Text { text: "Tint"; color: palette.ink }
            Slider { id: tint; from:0;to:1;value:.12;width:150 }
            Text { text: "Blur";color:palette.ink }
            Slider { id: blur; from:0;to:3;value:1;width:150 }
            Text { text: "Refraction";color:palette.ink }
            Slider { id:bend;from:0;to:2;value:1.4;width:150 }
        }
        UI.GlassSurface {
            width: parent.width; height:150; optics:optics;radius:28; readable:false
            Text { anchors.centerIn:parent;text:"Real desktop pixels · continuous refraction";font.pixelSize:24;color:palette.ink }
        }
        UI.GlassSurface {
            width:parent.width;height:120;optics:optics;radius:20;readingPanel:true;readingPlate:true; material:UI.GlassSurface.Panel
            Text { anchors.centerIn:parent;text:"Protected reading surface\nWGC / Direct3D 11 / Qt Quick";horizontalAlignment:Text.AlignHCenter;font.pixelSize:20;color:palette.ink }
        }
        Text { text:"Capture is opt-in and stays in GPU memory.\nExcluding this window may hide it from recordings and screen sharing.";color:palette.ink;font.pixelSize:13 }
    }
}




