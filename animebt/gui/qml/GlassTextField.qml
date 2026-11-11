import QtQuick
import QtQuick.Controls
import QtQuick.Templates as T
import QtQml.Models

T.TextField {
    id: control
    required property GlassTheme colors
    required property GlassThemeManager optics
    property bool inModalPanel: false
    property list<Action> extraActions
    property bool showExtraActions: false
    implicitHeight: Math.max(implicitBackgroundHeight, contentHeight + topPadding + bottomPadding)
    hoverEnabled: true
    selectByMouse: true
    font.pixelSize: colors.textSize
    padding: 8
    leftPadding: 11
    rightPadding: 11
    verticalAlignment: TextInput.AlignVCenter
    color: enabled ? colors.ink : colors.muted
    placeholderTextColor: colors.muted
    selectionColor: colors.controlSelected
    selectedTextColor: colors.ink
    readonly property bool editingMenuOpen: editingMenu.visible

    Text {
        x: control.leftPadding
        y: control.topPadding
        width: control.width - control.leftPadding - control.rightPadding
        height: control.height - control.topPadding - control.bottomPadding
        text: control.placeholderText
        textFormat: Text.PlainText
        color: control.placeholderTextColor
        font: control.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        visible: !control.length && !control.preeditText
    }

    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: eventPoint => {
            control.forceActiveFocus()
            editingMenu.popup(control, eventPoint.position)
        }
    }
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Menu || (event.key === Qt.Key_F10 && event.modifiers & Qt.ShiftModifier)) {
            editingMenu.popup(control, Qt.point(0, control.height))
            event.accepted = true
        }
    }
    GlassMenu {
        id: editingMenu
        objectName: "glassEditingMenu"
        colors: control.colors
        optics: control.optics
        backdropTier: control.inModalPanel ? GlassSurface.Dialog : GlassSurface.Scene
        dimBackdrop: control.inModalPanel
        GlassMenuItem {
            colors: control.colors
            optics: control.optics
            backdropTier: editingMenu.backdropTier
            dimBackdrop: editingMenu.dimBackdrop
            text: "撤销"
            enabled: !control.readOnly && control.canUndo
            onTriggered: control.undo()
        }
        GlassMenuItem {
            colors: control.colors
            optics: control.optics
            backdropTier: editingMenu.backdropTier
            dimBackdrop: editingMenu.dimBackdrop
            text: "重做"
            enabled: !control.readOnly && control.canRedo
            onTriggered: control.redo()
        }
        GlassMenuItem {
            colors: control.colors
            optics: control.optics
            backdropTier: editingMenu.backdropTier
            dimBackdrop: editingMenu.dimBackdrop
            text: "剪切"
            enabled: !control.readOnly && control.echoMode === TextInput.Normal && control.selectionStart !== control.selectionEnd
            onTriggered: control.cut()
        }
        GlassMenuItem {
            colors: control.colors
            optics: control.optics
            backdropTier: editingMenu.backdropTier
            dimBackdrop: editingMenu.dimBackdrop
            text: "复制"
            enabled: control.echoMode === TextInput.Normal && control.selectionStart !== control.selectionEnd
            onTriggered: control.copy()
        }
        GlassMenuItem {
            colors: control.colors
            optics: control.optics
            backdropTier: editingMenu.backdropTier
            dimBackdrop: editingMenu.dimBackdrop
            text: "粘贴"
            enabled: !control.readOnly && control.canPaste
            onTriggered: control.paste()
        }
        GlassMenuItem {
            colors: control.colors
            optics: control.optics
            backdropTier: editingMenu.backdropTier
            dimBackdrop: editingMenu.dimBackdrop
            text: "删除"
            enabled: !control.readOnly && control.selectionStart !== control.selectionEnd
            onTriggered: control.remove(control.selectionStart, control.selectionEnd)
        }
        GlassMenuItem {
            colors: control.colors
            optics: control.optics
            backdropTier: editingMenu.backdropTier
            dimBackdrop: editingMenu.dimBackdrop
            text: "全选"
            enabled: control.length > 0
            onTriggered: control.selectAll()
        }
        MenuSeparator {
            visible: control.showExtraActions && control.extraActions.length > 0
            height: visible ? implicitHeight : 0
            topPadding: 6
            bottomPadding: 6
            leftPadding: 6
            rightPadding: 6
            contentItem: Rectangle {
                implicitHeight: 1
                color: control.colors.softLine
            }
        }
        Instantiator {
            model: control.extraActions
            delegate: GlassMenuItem {
                required property var modelData
                action: modelData
                visible: control.showExtraActions
                height: visible ? implicitHeight : 0
                colors: control.colors
                optics: control.optics
                backdropTier: editingMenu.backdropTier
                dimBackdrop: editingMenu.dimBackdrop
            }
            onObjectAdded: (index, object) => editingMenu.addItem(object)
            onObjectRemoved: (index, object) => editingMenu.removeItem(object)
        }
    }

    background: GlassSurface {
        optics: control.optics
        implicitHeight: 35
        radius: 10
        backdropTier: control.inModalPanel ? GlassSurface.Scene : GlassSurface.Ambient
        readingPlate: control.inModalPanel
        dimBackdrop: control.inModalPanel
        tint: control.hovered ? control.colors.controlHover : control.colors.controlBase
        focused: control.activeFocus
    }
}
