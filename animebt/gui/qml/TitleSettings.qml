import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: dialog
    objectName: "titleSettingsDialog"
    required property QtObject assistant
    required property GlassTheme colors
    required property GlassThemeManager optics
    modal: true
    focus: true
    popupType: Popup.Item
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, dialog.optics.modalDim) }
    implicitWidth: 520
    implicitHeight: contentItem.implicitHeight + topPadding + bottomPadding
    width: Math.max(0, Math.min(parent.width - 32, implicitWidth))
    height: Math.max(0, Math.min(implicitHeight, parent.height - 32))
    topInset: 0
    bottomInset: 0
    leftInset: 0
    rightInset: 0
    padding: 20
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
        objectName: "aiSettingsBackground"
        colors: dialog.colors
        optics: dialog.optics
        radius: 22
        menuSurface: true
        dimBackdrop: true
    }

    contentItem: ColumnLayout {
        clip: true
        spacing: 14
        ShadowLabel { theme: dialog.colors;
            text: "AI 智能整理"
            color: dialog.colors.ink
            font.pixelSize: 22
            font.weight: Font.DemiBold
        }
        ScrollView {
            id: settingsScroll
            objectName: "aiSettingsScroll"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            Layout.preferredHeight: settingsForm.implicitHeight
            implicitHeight: settingsForm.implicitHeight
            contentWidth: availableWidth
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical: GlassScrollBar { colors: dialog.colors }
            ColumnLayout {
                id: settingsForm
                objectName: "aiSettingsForm"
                width: settingsScroll.availableWidth
                spacing: 8
                GlassSwitch {
                    colors: dialog.colors
                    optics: dialog.optics
                    id: enabledSwitch
                    objectName: "enableAi"
                    text: "启用 AI 智能整理"
                    onToggled: dialog.assistant.setEnabled(checked)
                }
                ShadowLabel { theme: dialog.colors;
                    Layout.fillWidth: true
                    text: "只发送可见资源的原始标题，返回字段须通过原文校验。关闭后显示无着色的原标题。"
                    wrapMode: Text.Wrap
                    color: dialog.colors.muted
                    font.pixelSize: dialog.colors.smallTextSize
                }
                ShadowLabel { theme: dialog.colors;
                    text: "Base URL"
                    color: dialog.colors.ink
                }
                GlassTextField {
                    id: endpoint
                    colors: dialog.colors
                    optics: dialog.optics
                    inModalPanel: true
                    objectName: "aiBaseUrl"
                    Layout.fillWidth: true
                    placeholderText: "https://api.deepseek.com 或兼容服务地址"
                    Accessible.name: "Base URL"
                }
                ShadowLabel { theme: dialog.colors;
                    text: "模型名称"
                    color: dialog.colors.ink
                }
                GlassTextField {
                    id: model
                    colors: dialog.colors
                    optics: dialog.optics
                    inModalPanel: true
                    objectName: "aiModel"
                    Layout.fillWidth: true
                    Accessible.name: "模型名称"
                }
                ShadowLabel { theme: dialog.colors;
                    text: "API Key"
                    color: dialog.colors.ink
                }
                GlassTextField {
                    id: key
                    colors: dialog.colors
                    optics: dialog.optics
                    inModalPanel: true
                    objectName: "aiApiKey"
                    Layout.fillWidth: true
                    echoMode: TextInput.Password
                    inputMethodHints: Qt.ImhHiddenText | Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
                    placeholderText: dialog.assistant.hasKey ? "已安全保存，留空沿用原 Key" : "输入服务的 API Key"
                    Accessible.name: "API Key"
                    enabled: !removeKey.checked
                }
                GlassCheckBox {
                    colors: dialog.colors
                    optics: dialog.optics
                    id: removeKey
                    visible: dialog.assistant.hasKey
                    text: "清除已保存的 Key"
                    onToggled: if (checked) key.clear()
                }
                ShadowLabel { theme: dialog.colors;
                    objectName: "aiSettingsStatus"
                    Layout.fillWidth: true
                    text: dialog.assistant.status
                    wrapMode: Text.Wrap
                    color: dialog.assistant.statusError ? dialog.colors.danger : dialog.colors.accentText
                    visible: text.length > 0
                    font.pixelSize: dialog.colors.detailTextSize
                }
            }
        }
        RowLayout {
            objectName: "aiSettingsButtons"
            Layout.fillWidth: true
            GlassButton {
                colors: dialog.colors
                optics: dialog.optics
                backdropTier: GlassSurface.Dialog
                dimBackdrop: true
                objectName: "testAiConnection"
                text: dialog.assistant.testing ? "测试中…" : "测试连接"
                enabled: !dialog.assistant.testing
                onClicked: dialog.assistant.testConnection(endpoint.text, model.text, key.text, removeKey.checked)
            }
            Item { Layout.fillWidth: true }
            GlassButton {
                colors: dialog.colors
                optics: dialog.optics
                backdropTier: GlassSurface.Dialog
                dimBackdrop: true
                text: "取消"
                onClicked: dialog.close()
            }
            GlassButton {
                colors: dialog.colors
                optics: dialog.optics
                backdropTier: GlassSurface.Dialog
                dimBackdrop: true
                objectName: "saveAiSettings"
                text: "保存"
                enabled: !dialog.assistant.testing
                onClicked: {
                    if (dialog.assistant.save(enabledSwitch.checked, endpoint.text, model.text, key.text, removeKey.checked))
                        dialog.close()
                }
            }
        }
    }
}
