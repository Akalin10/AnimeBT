import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "titleSettingsDialog"
    required property QtObject assistant
    required property GlassTheme colors
    required property GlassThemeManager optics
    title: "AI 智能整理"
    palette.windowText: colors.ink
    palette.text: colors.ink
    palette.buttonText: colors.ink
    modal: true
    popupType: Popup.Item
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, dialog.optics.modalDim) }
    width: Math.min(parent.width - 40, 490)
    padding: 18
    closePolicy: endpoint.editingMenuOpen || model.editingMenuOpen || key.editingMenuOpen
        ? Popup.NoAutoClose : Popup.CloseOnEscape

    onOpened: {
        enabledSwitch.checked = assistant.enabled
        endpoint.text = assistant.baseUrl
        model.text = assistant.model
        key.text = ""
        removeKey.checked = false
    }
    onClosed: key.clear()

    background: GlassPopupFrame {
        colors: dialog.colors
        optics: dialog.optics
        radius: 18
        dimBackdrop: true
    }
    header: Label {
        text: dialog.title
        padding: 18
        bottomPadding: 0
        color: dialog.colors.ink
        font.pixelSize: 18
        font.weight: Font.DemiBold
    }
    contentItem: ColumnLayout {
        spacing: 6
        Switch {
            id: enabledSwitch
            objectName: "enableAi"
            text: "启用 AI 智能整理"
        }
        Label { text: "Base URL"; color: dialog.colors.ink }
        GlassTextField {
            id: endpoint
            colors: dialog.colors
            optics: dialog.optics
            inModalPanel: true
            objectName: "aiBaseUrl"
            Layout.fillWidth: true
            placeholderText: "https://example.com/v1"
            Accessible.name: "Base URL"
        }
        Label { text: "模型名称"; color: dialog.colors.ink }
        GlassTextField {
            id: model
            colors: dialog.colors
            optics: dialog.optics
            inModalPanel: true
            objectName: "aiModel"
            Layout.fillWidth: true
            Accessible.name: "模型名称"
        }
        Label { text: "API Key"; color: dialog.colors.ink }
        GlassTextField {
            id: key
            colors: dialog.colors
            optics: dialog.optics
            inModalPanel: true
            objectName: "aiApiKey"
            Layout.fillWidth: true
            echoMode: TextInput.Password
            inputMethodHints: Qt.ImhHiddenText | Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
            placeholderText: dialog.assistant.hasKey ? "已安全保存，留空沿用原 Key" : "可留空用于无需认证的服务"
            Accessible.name: "API Key"
            enabled: !removeKey.checked
        }
        CheckBox {
            id: removeKey
            visible: dialog.assistant.hasKey
            text: "清除已保存的 Key"
            onToggled: if (checked) key.clear()
        }
        Label {
            Layout.fillWidth: true
            text: "启用后，部分可见的疑难标题会发送到所填服务。更换服务地址时，请重新填写 Key。"
            wrapMode: Text.Wrap
            color: dialog.colors.muted
        }
        Label {
            objectName: "aiSettingsStatus"
            Layout.fillWidth: true
            text: dialog.assistant.status
            wrapMode: Text.Wrap
            color: dialog.colors.accentText
            visible: text.length > 0
        }
        RowLayout {
            Layout.fillWidth: true
            GlassButton {
                colors: dialog.colors
                optics: dialog.optics
                backdropTier: GlassSurface.Scene
                dimBackdrop: true
                objectName: "testAiConnection"
                text: "测试连接"
                enabled: !dialog.assistant.testing
                onClicked: dialog.assistant.testConnection(endpoint.text, model.text, key.text, removeKey.checked)
            }
            Item { Layout.fillWidth: true }
            GlassButton {
                colors: dialog.colors
                optics: dialog.optics
                backdropTier: GlassSurface.Scene
                dimBackdrop: true
                text: "取消"
                onClicked: dialog.close()
            }
            GlassButton {
                colors: dialog.colors
                optics: dialog.optics
                backdropTier: GlassSurface.Scene
                dimBackdrop: true
                objectName: "saveAiSettings"
                text: "保存"
                onClicked: {
                    if (dialog.assistant.save(enabledSwitch.checked, endpoint.text, model.text, key.text, removeKey.checked))
                        dialog.close()
                }
            }
        }
    }
}
