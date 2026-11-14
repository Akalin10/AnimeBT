import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

GlassPopup {
    id: notice
    objectName: "startupSearchNotice"
    signal acknowledged(bool doNotShowAgain)
    // Square panel scales with the shorter window dimension, like the reference.
    implicitWidth: Math.min(parent.width, parent.height) * 0.40
    implicitHeight: implicitWidth
    width: implicitWidth
    height: implicitHeight
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2
    padding: Math.max(10, width * 0.065)
    cornerRadius: Math.max(16, width * 0.055)
    modal: true
    focus: true
    closePolicy: Popup.NoAutoClose
    readonly property int messageSize: Math.max(13, Math.min(19, Math.round(width / 22)))
    onOpened: { suppress.checked = false; understood.forceActiveFocus() }

    contentItem: ColumnLayout {
        spacing: Math.max(8, notice.width * 0.045)
        ScrollView {
            id: messageScroll
            objectName: "startupNoticeMessageScroll"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            contentWidth: availableWidth
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical: GlassScrollBar {
                colors: notice.colors
                x: messageScroll.width - width
                height: messageScroll.height
                visible: messageScroll.contentHeight > messageScroll.availableHeight + 1
            }
            ShadowText {
                objectName: "startupNoticeMessage"
                theme: notice.colors
                width: messageScroll.availableWidth
                height: Math.max(implicitHeight, messageScroll.availableHeight)
                verticalAlignment: Text.AlignVCenter
                text: "⚠️因为Bangumi被墙，所以没开代理是一般是用不了图鉴检索的，但有Anlist源，所以还是能用的，但是尽量用列表检索，更全面⚠️"
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                font.pixelSize: notice.messageSize
                lineHeight: 1.45
                color: notice.colors.ink
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Math.max(6, notice.width * 0.025)
            GlassButton {
                id: understood
                objectName: "startupNoticeUnderstood"
                colors: notice.colors
                optics: notice.optics
                text: "了解"
                Layout.preferredWidth: Math.max(46, notice.width * 0.25)
                onClicked: {
                    notice.acknowledged(suppress.checked)
                    notice.close()
                }
            }
            GlassCheckBox {
                id: suppress
                objectName: "startupNoticeSuppress"
                colors: notice.colors
                optics: notice.optics
                text: "下次不再提示"
                Layout.fillWidth: true
                contentItem: ShadowText {
                    theme: notice.colors
                    text: suppress.text
                    color: notice.colors.ink
                    font.pixelSize: Math.min(16, notice.messageSize)
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }
}
