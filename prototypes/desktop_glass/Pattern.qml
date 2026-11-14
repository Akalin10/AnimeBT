import QtQuick
Window {
    id: root; width:1920;height:1080;visible:true;color:"#e5d9c3"
    title:"Controlled desktop pattern — no personal content"
    property real offset:0;property bool moving:true
    NumberAnimation on offset { from:0;to:80;duration:1600;loops:Animation.Infinite;running:root.moving }
    Repeater {
        model:70
        Rectangle { required property int index; x:index*40-root.offset;y:0;width:20;height:root.height;color:index%2 ? "#285d83" : "#c4627c" }
    }
    Repeater {
        model:14
        Text { required property int index;x:80+(index%3)*100;y:index*80;text:"DESKTOP 012345 · 实时桌面 · 日本語";font.pixelSize:32;color:index%2 ? "white" : "#162539" }
    }
}

