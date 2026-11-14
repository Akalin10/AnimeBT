import QtQuick
import QtQuick.Controls

ComboBox {
    id: control
    required property GlassTheme colors
    required property GlassThemeManager optics
    hoverEnabled: true
    leftPadding: 12
    rightPadding: 32
    topPadding: 4
    bottomPadding: 4
    scale: optics.motion > 0 && down ? 0.98 : 1
    Behavior on scale { NumberAnimation { duration: control.optics.motion; easing.type: Easing.OutCubic } }

    contentItem: ShadowText { theme: control.colors;
        text: control.displayText
        textFormat: Text.PlainText
        color: control.enabled ? control.colors.ink : control.colors.muted
        font.pixelSize: control.colors.textSize
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    indicator: Glyph {
        x: control.width - width - 10
        y: (control.height - height) / 2
        width: 15
        height: 15
        ink: control.colors.accentText
        path: "M5 8 L10 13 L15 8"
        rotation: control.popup.visible ? 180 : 0
    }
    background: GlassSurface {
        objectName: "comboGlass"
        optics: control.optics
        radius: control.colors.controlRadius
        implicitHeight: 38
        tint: control.down ? control.colors.controlPressed
             : control.hovered ? control.colors.controlHover : control.colors.controlBase
        focused: control.visualFocus || control.popup.visible
    }
    delegate: GlassMenuItem {
        required property var model
        required property int index
        width: ListView.view ? ListView.view.width : control.width
        colors: control.colors
        optics: control.optics
        text: control.textRole ? model[control.textRole] : model.modelData
        selected: control.currentIndex === index
        highlighted: control.highlightedIndex === index
    }
    popup: GlassPopup {
        id: options
        objectName: "glassOptions"
        colors: control.colors
        optics: control.optics
        cornerRadius: 13
        width: Math.max(control.width, 192)
        height: Math.min(278, space, choices.contentHeight + topPadding + bottomPadding)
        y: opensAbove ? -height - 5 : control.height + 5
        property bool opensAbove: false
        property real space: 278
        onAboutToShow: {
            const overlay = Overlay.overlay
            const top = control.mapToItem(overlay, 0, 0).y
            const above = top - 13
            const below = overlay.height - top - control.height - 13
            const preferred = Math.min(278, control.count * 38 + topPadding + bottomPadding)
            opensAbove = below < preferred && above > below
            space = Math.max(50, opensAbove ? above : below)
        }
        contentItem: ListView {
            id: choices
            clip: true
            model: control.delegateModel
            currentIndex: control.highlightedIndex
            highlightMoveDuration: 0
            boundsBehavior: Flickable.StopAtBounds
            ScrollIndicator.vertical: ScrollIndicator {}
        }
    }
}
