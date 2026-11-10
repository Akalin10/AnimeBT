import QtQuick
import QtQuick.Controls

Item {
    id: section
    required property GlassTheme colors
    required property GlassThemeManager optics
    required property QtObject catalog
    required property QtObject subjects
    required property real viewportY
    required property real viewportHeight
    required property bool loading
    required property bool animateLoading
    property bool viewportMoving: false
    property int preferredWidth: 200
    property int motion: 160
    property int hiddenSubjectId: -1
    property real reflowScale: 1
    signal posterActivated(int subjectId, Item coverItem, url cover)
    readonly property var selected: catalog.selected
    readonly property int gap: 12
    readonly property int subjectCount: subjects.count
    readonly property int columnCount: columnsFor(preferredWidth)
    readonly property real cardWidth: widthFor(preferredWidth)
    readonly property real extraSpace: Math.max(0, width - cardWidth * columnCount - gap * (columnCount - 1)) / (columnCount + 1)
    readonly property int titleSize: Math.round(Math.max(15, Math.min(19, 11 + cardWidth / 28)))
    readonly property int captionSize: cardWidth < 170 ? 12 : 13
    readonly property int captionInset: cardWidth < 145 ? 8 : 12
    readonly property int infoHeight: 2 * captionInset + 2 * Math.ceil(titleMetrics.implicitHeight)
        + Math.ceil(Math.max(captionMetrics.implicitHeight, originalMetrics.implicitHeight))
        + Math.ceil(captionMetrics.implicitHeight) + 15
    readonly property real cardHeight: cardWidth * 1.5 + infoHeight
    readonly property real rowPitch: cardHeight + gap
    readonly property bool trailing: loading && subjectCount > 0
    readonly property int rowCount: Math.ceil((subjectCount + (trailing ? 1 : 0)) / columnCount)
    height: rowCount > 0 ? rowCount * rowPitch - gap : 0

    component LoadingGlyph: Glyph {
        id: loadingGlyph
        path: "M 10 2 A 8 8 0 1 1 2 10"
        ink: section.colors.accentText
        scale: 1.25
        NumberAnimation on rotation {
            running: loadingGlyph.visible && section.animateLoading
            from: 0
            to: 360
            duration: 900
            loops: Animation.Infinite
        }
    }

    LoadingGlyph {
        objectName: "catalogInitialLoader"
        visible: section.loading && section.subjectCount === 0
        anchors.horizontalCenter: parent.horizontalCenter
        y: Math.max(0, (section.viewportHeight + Math.min(0, section.viewportY) - height) / 2)
    }

    // Measure shaped lines so the CJK fallback contributes its actual height.
    Text {
        id: titleMetrics
        visible: false
        text: "动画 Season 2"
        font.pixelSize: section.titleSize
        font.weight: Font.Bold
    }
    Text {
        id: captionMetrics
        visible: false
        text: "2026年10月番"
        font.pixelSize: section.captionSize
    }
    Text {
        id: originalMetrics
        visible: false
        text: "アニメ Season 2"
        font: section.colors.originalFont(text, section.captionSize)
    }

    function columnsFor(targetWidth) {
        return Math.max(1, Math.round((width + gap) / (targetWidth + gap)))
    }

    function widthFor(targetWidth) {
        const count = columnsFor(targetWidth)
        return Math.max(0, Math.min(targetWidth, (width - gap * (count - 1)) / count))
    }

    Grid {
        id: grid
        objectName: "posterGrid"
        x: section.extraSpace
        width: section.width - 2 * x
        columns: section.columnCount
        columnSpacing: section.gap + section.extraSpace
        rowSpacing: section.gap

        Repeater {
            model: section.subjects

            ItemDelegate {
                id: card
                required property var subject
                required property int index
                readonly property var modelData: subject
                property real arrival: section.motion > 0 ? 0.55 : 1
                property int coverIndex: 0
                readonly property var alternatives: modelData.coverAlternatives || []
                readonly property bool inViewport: y + height > section.viewportY - 16
                    && y < section.viewportY + section.viewportHeight + 16
                readonly property bool nearViewport: section.viewportHeight > 0
                    && y + height > section.viewportY - section.viewportHeight * 0.25
                    && y < section.viewportY + section.viewportHeight * 1.25
                property bool coverRequested: false
                readonly property bool populated: modelData !== null
                readonly property bool chosen: populated && section.selected.id === modelData.id
                objectName: populated ? "subjectCard" : "posterSlot"
                width: section.cardWidth
                height: section.cardHeight
                padding: 0
                enabled: populated
                hoverEnabled: populated
                highlighted: chosen
                opacity: arrival
                transformOrigin: Item.Top
                scale: down ? 0.985 : hovered ? 1.018 : 1
                transform: Scale {
                    origin.x: card.width / 2
                    xScale: section.reflowScale
                    yScale: section.reflowScale
                }
                z: hovered ? 1 : 0
                Behavior on scale {
                    NumberAnimation { duration: section.motion; easing.type: Easing.OutCubic }
                }
                Component.onCompleted: if (section.motion > 0) enterMotion.start()
                Timer {
                    running: card.nearViewport && !card.coverRequested
                    interval: 24 + (card.index % 8) * 18
                    onTriggered: card.coverRequested = true
                }
                Connections {
                    target: section
                    function onMotionChanged() {
                        if (section.motion === 0) {
                            enterMotion.stop()
                            card.arrival = 1
                        }
                    }
                }
                NumberAnimation {
                    id: enterMotion
                    target: card
                    property: "arrival"
                    to: 1
                    duration: section.motion
                    easing.type: Easing.OutCubic
                }
                onClicked: section.posterActivated(modelData.id, poster, String(cover.source) ? cover.source : modelData.cover)
                Accessible.ignored: !populated
                Accessible.name: populated ? modelData.title : ""
                Accessible.description: populated ? [modelData.original, modelData.season].filter(Boolean).join(" · ") : ""

                GlassToolTip {
                    colors: section.colors
                    optics: section.optics
                    visible: card.populated && card.hovered && card.inViewport && !section.viewportMoving
                    // The popup is drawn in the overlay, outside Flickable's clip.
                    y: Math.max(-implicitHeight - 3, section.viewportY - card.y + 12)
                    delay: 680
                    width: 252
                    text: card.populated ? [card.modelData.title, card.modelData.original,
                                            card.modelData.season].filter(Boolean).join("\n") : ""
                }

                background: GlassSurface {
                    objectName: "posterCardGlass"
                    optics: section.optics
                    renderOptics: card.inViewport
                    compact: true
                    radius: 16
                    outline: card.chosen || card.visualFocus ? colors.accent : section.optics.edge
                    tint: card.hovered ? colors.controlHover : colors.controlBase
                }
                contentItem: Item {
                    Rectangle {
                        id: poster
                        objectName: "coverFrame"
                        width: parent.width
                        height: width * 1.5
                        radius: 16
                        opacity: card.modelData.id === section.hiddenSubjectId ? 0 : 1
                        color: colors.panelFaint
                        readonly property bool hardwareMask: GraphicsInfo.api !== GraphicsInfo.Software

                        Glyph {
                            anchors.centerIn: parent
                            visible: cover.opacity < 1
                            ink: colors.muted
                            path: "M5 3 H15 Q17 3 17 5 V15 Q17 17 15 17 H5 Q3 17 3 15 V5 Q3 3 5 3 Z M4 14 L8 10 L11 13 L14 9 L16 11 M7 7 h0.1"
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: 14
                            visible: card.populated && (cover.status === Image.Error
                                || (!card.modelData.cover && cover.status === Image.Null))
                            text: cover.status === Image.Error ? "封面加载失败" : "暂无封面"
                            color: colors.muted
                            font.pixelSize: 12
                        }
                        Image {
                            id: cover
                            objectName: "subjectCover"
                            anchors.fill: parent
                            source: !card.populated || !card.coverRequested ? "" : card.coverIndex === 0
                                    ? card.modelData.cover : card.alternatives[card.coverIndex - 1]
                            asynchronous: true
                            cache: true
                            smooth: true
                            mipmap: true
                            fillMode: Image.PreserveAspectCrop
                            clip: true
                            visible: !poster.hardwareMask && card.inViewport
                            opacity: status === Image.Ready ? 1 : 0
                            onStatusChanged: {
                                if (status === Image.Error && card.coverIndex < card.alternatives.length)
                                    ++card.coverIndex
                            }
                            Behavior on opacity { NumberAnimation { duration: section.motion } }
                        }
                        ShaderEffect {
                            // Clip the original texture directly at screen resolution, without a card-sized layer.
                            anchors.fill: parent
                            visible: poster.hardwareMask && card.inViewport && cover.status === Image.Ready && opacity > 0
                            opacity: cover.opacity
                            fragmentShader: "shaders/poster.frag.qsb"
                            property var coverTexture: cover
                            property size frameSize: Qt.size(Math.max(1, width), Math.max(1, height))
                            property size imageSize: cover.sourceSize
                            property real corner: poster.radius
                        }
                        Rectangle {
                            anchors.fill: parent
                            radius: poster.radius
                            color: "transparent"
                            border.width: card.chosen || card.visualFocus ? 2 : 1
                            border.color: card.chosen || card.visualFocus ? colors.accent : section.optics.edge
                        }
                    }

                    Item {
                        id: captions
                        objectName: "posterCaption"
                        visible: card.populated
                        x: section.captionInset
                        y: poster.height + section.captionInset
                        width: parent.width - 2 * x
                        height: section.infoHeight - 2 * section.captionInset

                        Text {
                            id: title
                            objectName: "posterTitle"
                            width: parent.width
                            text: card.populated ? card.modelData.title : ""
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            maximumLineCount: 2
                            elide: Text.ElideRight
                            color: colors.ink
                            font.pixelSize: section.titleSize
                            font.weight: Font.Bold
                        }
                        Text {
                            id: original
                            objectName: "posterOriginal"
                            width: parent.width
                            anchors.top: title.bottom
                            anchors.topMargin: 2
                            visible: text.length > 0 && text !== title.text
                            text: card.populated ? card.modelData.original : ""
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            color: colors.muted
                            font: colors.originalFont(text, section.captionSize)
                        }
                        Text {
                            objectName: "posterAirtime"
                            anchors.top: original.visible ? original.bottom : title.bottom
                            anchors.topMargin: 9
                            width: parent.width
                            visible: text.length > 0
                            text: {
                                const season = card.populated ? card.modelData.season || "" : ""
                                const label = section.cardWidth < 150 ? season.split(" · ").pop() : season
                                return label.replace(/ 年 /, "年").replace(/ 月番/, "月番")
                            }
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            color: colors.accentText
                            font.pixelSize: section.captionSize
                            font.weight: Font.Medium
                        }
                    }
                }
            }
        }
        Item {
            objectName: "catalogTrailingSlot"
            visible: section.trailing
            width: section.cardWidth
            height: section.cardHeight
            LoadingGlyph {
                anchors.centerIn: parent
            }
        }
    }
}
