import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Item {
    id: page
    objectName: "resourcePage"
    required property GlassTheme colors
    required property QtObject backend
    required property QtObject assistant
    required property GlassThemeManager optics
    property url coverOverride: ""
    readonly property url coverSource: String(coverOverride) ? coverOverride : backend.subject.cover || ""
    property bool hidePoster: false
    readonly property alias posterAnchor: detailPoster
    signal backRequested()
    property bool highlightTitles: true
    property int motion: 160
    property real filterOffset: 0
    property bool showSources: false
    readonly property int subjectId: backend.subject.id || 0
    readonly property int completedSources: backend.sources.filter(source => source.status !== "搜索中").length
    readonly property bool compactHeader: height < 470
    onSubjectIdChanged: showSources = false
    property string episodeFilter: ""
    property string resolutionFilter: ""
    property string fansubFilter: ""
    property string categoryFilter: ""
    property var menuRow: null
    readonly property QtObject actions: backend.actions
    readonly property bool actionPopupOpen: resourceMenu.opened || saveDialog.visible
        || category.popupOpen || episode.popupOpen || resolution.popupOpen || fansub.popupOpen

    readonly property var filtered: backend.rows.filter(row =>
        (!categoryFilter || row.category === categoryFilter) &&
        (!episodeFilter || row.episode === episodeFilter) &&
        (!resolutionFilter || row.resolution === resolutionFilter) &&
        (!fansubFilter || row.fansub === fansubFilter))

    readonly property var categoryCounts: {
        const counts = {"独立资源": 0, "合集资源": 0}
        for (const row of backend.rows)
            counts[row.category]++
        return counts
    }
    readonly property var categoryOptions: [{label: "全部 · " + backend.rows.length, value: ""}]
        .concat(Object.keys(categoryCounts).map(key => ({label: key + " · " + categoryCounts[key], value: key})))

    function animateFilter() {
        if (motion > 0) {
            filterOffset = 4
            filterMotion.restart()
        }
    }
    onCategoryFilterChanged: animateFilter()
    onEpisodeFilterChanged: animateFilter()
    onResolutionFilterChanged: animateFilter()
    onFansubFilterChanged: animateFilter()
    onMotionChanged: if (motion === 0) {
        filterMotion.stop()
        filterOffset = 0
    }
    NumberAnimation {
        id: filterMotion
        target: page
        property: "filterOffset"
        to: 0
        duration: page.motion
        easing.type: Easing.OutCubic
    }

    function options(key, selected) {
        const values = [...new Set(backend.rows.map(row => row[key]))]
        if (selected && !values.includes(selected))
            values.push(selected)
        values.sort((a, b) => a.localeCompare(b, "zh-CN", { numeric: true }))
        return [{label: "全部", value: ""}].concat(values.map(value => ({label: value, value: value})))
    }

    GlassMenu {
        id: resourceMenu
        objectName: "resourceMenu"
        colors: page.colors
        optics: page.optics
        GlassMenuItem {
            colors: page.colors
            optics: page.optics
            objectName: "copyTitleMenu"
            text: "复制资源标题"
            enabled: page.menuRow !== null && !page.actions.busy
            onTriggered: page.actions.copyTitle(page.menuRow)
        }
        GlassMenuItem {
            colors: page.colors
            optics: page.optics
            objectName: "copyMagnetMenu"
            text: "复制磁链"
            enabled: page.menuRow !== null && !page.actions.busy
            onTriggered: page.actions.copyMagnet(page.menuRow)
        }
        GlassMenuItem {
            colors: page.colors
            optics: page.optics
            objectName: "saveTorrentMenu"
            text: "保存 Torrent 文件"
            enabled: !!page.menuRow?.torrent_url && !page.actions.busy
            onTriggered: {
                saveDialog.resource = page.menuRow
                saveDialog.selectedFile = page.actions.suggestedTorrent(saveDialog.resource)
                saveDialog.open()
            }
        }
    }

    FileDialog {
        id: saveDialog
        objectName: "saveTorrentDialog"
        title: "保存 Torrent 文件"
        fileMode: FileDialog.SaveFile
        nameFilters: ["Torrent 文件 (*.torrent)"]
        defaultSuffix: "torrent"
        options: FileDialog.DontConfirmOverwrite
        property var resource: null
        onAccepted: page.actions.saveTorrent(resource, selectedFile)
    }

    component ResourceFilter: GridLayout {
        id: field
        property string label
        property string selectedValue
        property var choices
        readonly property bool popupOpen: combo.popup.visible
        signal picked(string value)
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        Layout.preferredWidth: 1
        columns: page.compactHeader ? 2 : 1
        columnSpacing: 5
        rowSpacing: 3

        Text {
            text: field.label
            color: colors.muted
            font.pixelSize: 12
        }
        GlassComboBox {
            id: combo
            colors: page.colors
            optics: page.optics
            objectName: field.label + "Filter"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.preferredHeight: 32
            model: field.choices
            textRole: "label"
            valueRole: "value"
            currentIndex: Math.max(0, field.choices.findIndex(option => option.value === field.selectedValue))
            onActivated: field.picked(currentValue)
            Accessible.name: field.label
        }
    }

    Item {
        anchors.fill: parent

        ColumnLayout {
            id: resourceHeader
            objectName: "resourceHeader"
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: implicitHeight
            z: 1
            spacing: 7

            Item {
                Layout.fillWidth: true
                implicitHeight: workInfo.implicitHeight + 20

                GlassSurface {
                    anchors.fill: parent
                    optics: page.optics
                    compact: true
                    readingPlate: true
                    tint: colors.controlBase
                }

                RowLayout {
                    id: workInfo
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 14
                    Item {
                        id: detailPoster
                        objectName: "detailPosterAnchor"
                        visible: String(page.coverSource).length > 0
                        Layout.preferredWidth: 80
                        Layout.preferredHeight: 120
                        Image {
                            objectName: "detailCoverImage"
                            anchors.fill: parent
                            visible: !page.hidePoster
                            source: page.coverSource
                            asynchronous: true
                            cache: true
                            smooth: true
                            mipmap: true
                            fillMode: Image.PreserveAspectFit
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 3
                        RowLayout {
                            Layout.fillWidth: true
                            GlassButton {
                                objectName: "backToCatalog"
                                colors: page.colors
                                optics: page.optics
                                text: "返回"
                                onClicked: page.backRequested()
                            }
                            Item { Layout.fillWidth: true }
                            GlassButton {
                                colors: page.colors
                                optics: page.optics
                                text: "重新搜索"
                                enabled: !page.backend.loading
                                onClicked: page.backend.refresh()
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: page.backend.subject.title || ""
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            color: colors.ink
                            font.pixelSize: page.width < 720 ? 24 : 29
                            font.weight: Font.Bold
                        }
                        Item {
                            Layout.fillWidth: true
                            visible: original.visible || airtime.visible
                            implicitHeight: Math.max(original.visible ? original.implicitHeight : 0,
                                                     airtime.visible ? airtime.implicitHeight : 0)
                            Text {
                                id: original
                                anchors.verticalCenter: parent.verticalCenter
                                width: visible ? Math.min(implicitWidth, Math.max(0, parent.width
                                       - (airtime.visible ? airtime.implicitWidth + 8 : 0))) : 0
                                text: page.backend.subject.original || ""
                                visible: text.length > 0
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                color: colors.muted
                                font: colors.originalFont(text, 13)
                            }
                            Text {
                                id: airtime
                                anchors.verticalCenter: parent.verticalCenter
                                x: original.visible ? original.width + 8 : 0
                                text: page.backend.subject.season || ""
                                visible: text.length > 0
                                color: colors.accentText
                                font.pixelSize: 12
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            BusyIndicator {
                                Layout.preferredWidth: 18
                                Layout.preferredHeight: 18
                                visible: page.backend.loading && page.motion > 0
                                running: visible
                            }
                            Text {
                                objectName: "resourceStatus"
                                Layout.fillWidth: true
                                text: page.backend.error || (page.backend.loading
                                    ? "正在搜索 · 已完成 " + page.completedSources + "/" + page.backend.sources.length
                                      + " 个来源 · 已确认 " + page.backend.rows.length + " 条"
                                    : page.backend.rows.length
                                      ? "已确认 " + page.backend.rows.length + " 条"
                                        + " · 当前显示 " + page.filtered.length + " 条"
                                      : "未找到该作品的 BT 资源")
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                color: page.backend.error ? colors.danger : colors.accentText
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                            }
                            GlassButton {
                                colors: page.colors
                                optics: page.optics
                                objectName: "sourceDetailsToggle"
                                text: page.showSources ? "收起来源" : "来源详情"
                                visible: page.backend.sources.length > 0
                                checkable: true
                                checked: page.showSources
                                onToggled: page.showSources = checked
                            }
                        }
                    }
                }
            }

            Item {
                objectName: "sourceDetails"
                Layout.fillWidth: true
                implicitHeight: sourceGrid.implicitHeight + 2 * sourceGrid.anchors.margins
                visible: page.showSources && page.backend.sources.length > 0

                GlassSurface {
                    anchors.fill: parent
                    optics: page.optics
                    compact: true
                    readingPlate: true
                    tint: colors.controlBase
                }

                GridLayout {
                    id: sourceGrid
                    anchors.fill: parent
                    anchors.margins: page.compactHeader ? 5 : 8
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    columns: 5
                    columnSpacing: 6
                    rowSpacing: page.compactHeader ? 3 : 6
                    Repeater {
                        model: page.backend.sources
                        delegate: Item {
                            id: source
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            implicitHeight: 29
                            Column {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.leftMargin: 7
                                anchors.rightMargin: 7
                                spacing: 2
                                Text {
                                    width: parent.width
                                    text: source.modelData.name
                                    textFormat: Text.PlainText
                                    elide: Text.ElideRight
                                    color: colors.ink
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    width: parent.width
                                    text: source.modelData.status === "搜索中" ? "搜索中"
                                        : source.modelData.status + " · " + source.modelData.count + " 条"
                                    textFormat: Text.PlainText
                                    elide: Text.ElideRight
                                    color: source.modelData.error ? colors.danger : colors.muted
                                    font.pixelSize: 11
                                }
                            }
                            HoverHandler { id: hover }
                            GlassToolTip {
                                colors: page.colors
                                optics: page.optics
                                visible: hover.hovered
                                delay: 400
                                width: 290
                                text: source.modelData.name
                                    + "\n确认 " + source.modelData.count + " 条"
                                    + (source.modelData.error ? "\n" + source.modelData.error : "")
                                    + (source.modelData.keywords ? "\n名称：" + source.modelData.keywords : "")
                            }
                        }
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                visible: page.backend.subject.platform === "TV" && !page.backend.scheduleAvailable
                text: "Bangumi 正片排期不可用，部分季度或分段只能凭明确的标题标记确认。"
                color: colors.warning
                font.pixelSize: 12
                wrapMode: Text.Wrap
            }

            RowLayout {
                Layout.fillWidth: true
                ResourceFilter {
                    id: category
                    label: "分类"
                    choices: page.categoryOptions
                    selectedValue: page.categoryFilter
                    onPicked: value => page.categoryFilter = value
                }
                ResourceFilter {
                    id: episode
                    label: "集数"
                    choices: page.options("episode", page.episodeFilter)
                    selectedValue: page.episodeFilter
                    onPicked: value => page.episodeFilter = value
                }
                ResourceFilter {
                    id: resolution
                    label: "分辨率"
                    choices: page.options("resolution", page.resolutionFilter)
                    selectedValue: page.resolutionFilter
                    onPicked: value => page.resolutionFilter = value
                }
                ResourceFilter {
                    id: fansub
                    label: "字幕组"
                    choices: page.options("fansub", page.fansubFilter)
                    selectedValue: page.fansubFilter
                    onPicked: value => page.fansubFilter = value
                }
            }
        }

        Rectangle {
            id: resourceDivider
            anchors.top: resourceHeader.bottom
            anchors.topMargin: 7
            anchors.left: parent.left
            anchors.right: parent.right
            height: 1
            color: colors.softLine
        }

        ListView {
            id: list
            objectName: "resourceList"
            anchors.top: resourceDivider.bottom
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.topMargin: 7
            anchors.bottomMargin: 5
            spacing: 6
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: page.filtered
            ScrollBar.vertical: ScrollBar {
                objectName: "resourceScrollBar"
                policy: ScrollBar.AsNeeded
            }
            delegate: Item {
                id: entry
                transform: Translate { y: page.filterOffset }
                required property var modelData
                readonly property var spans: modelData.titleSpans || []
                readonly property bool inViewport: y + height > list.contentY && y < list.contentY + list.height
                readonly property bool needsAssistant: page.highlightTitles && page.assistant.ready
                    && inViewport && modelData.titleAmbiguous === true
                function requestAnnotation() {
                    if (needsAssistant)
                        page.assistant.request(modelData.title, modelData.titleSpans || [])
                }
                onNeedsAssistantChanged: requestAnnotation()
                onModelDataChanged: requestAnnotation()
                Component.onCompleted: requestAnnotation()
                Connections {
                    target: page.assistant
                    function onSettingsChanged() { entry.requestAnnotation() }
                }
                width: list.width - 10
                height: Math.max(body.height, thumbnail.height) + 20
                HoverHandler { id: rowHover }
                GlassSurface {
                    objectName: "resourceCardGlass"
                    anchors.fill: parent
                    optics: page.optics
                    compact: true
                    readingPlate: true
                    renderOptics: entry.inViewport
                    radius: 12
                    tint: page.assistant.background(colors.dark, rowHover.hovered)
                    shine: rowHover.hovered ? 0.55 : 0
                }

                MouseArea {
                    anchors.fill: parent
                    z: 2
                    acceptedButtons: Qt.RightButton
                    onClicked: mouse => {
                        page.menuRow = entry.modelData
                        resourceMenu.popup(page, mapToItem(page, mouse.x, mouse.y))
                    }
                }

                Button {
                    id: thumbnail
                    objectName: "resourceThumbnail"
                    readonly property bool pending: page.actions.pendingKey === entry.modelData.key
                    x: 10
                    y: 10
                    width: 48
                    height: 72
                    padding: 0
                    hoverEnabled: true
                    enabled: !page.actions.busy
                    scale: down ? 0.98 : hovered ? 1.045 : 1
                    Behavior on scale { NumberAnimation { duration: page.motion; easing.type: Easing.OutCubic } }
                    Accessible.name: "复制磁链 · " + entry.modelData.title
                    GlassToolTip {
                        colors: page.colors
                        optics: page.optics
                        text: "左键复制磁链 · 右键更多操作"
                        visible: thumbnail.hovered
                        delay: 650
                    }
                    onClicked: page.actions.copyMagnet(entry.modelData)
                    HoverHandler { enabled: thumbnail.enabled; cursorShape: Qt.PointingHandCursor }
                    background: Rectangle {
                        radius: 8
                        color: colors.imageBase
                    }
                    contentItem: Item {
                        Image {
                            id: miniature
                            anchors.fill: parent
                            anchors.margins: 2
                            source: page.coverSource
                            sourceSize.width: 96
                            fillMode: Image.PreserveAspectCrop
                            clip: true
                            asynchronous: true
                            cache: true
                        }
                        Rectangle {
                            anchors.fill: parent
                            radius: 8
                            opacity: thumbnail.hovered || thumbnail.visualFocus || thumbnail.pending
                                     || miniature.status !== Image.Ready ? 1 : 0
                            color: miniature.status === Image.Ready ? "#a3252e50" : "#00ffffff"
                            Behavior on opacity { NumberAnimation { duration: page.motion } }
                            Glyph {
                                anchors.centerIn: parent
                                visible: !thumbnail.pending || page.motion === 0
                                ink: miniature.status === Image.Ready ? "white" : colors.accent
                                path: "M7 6 V4 H16 V13 H14 M4 7 H13 V16 H4 Z"
                            }
                            BusyIndicator {
                                anchors.centerIn: parent
                                width: 27
                                height: 27
                                visible: thumbnail.pending && page.motion > 0
                                running: visible
                            }
                        }
                        Rectangle {
                            anchors.fill: parent
                            radius: 8
                            color: "transparent"
                            border.color: thumbnail.visualFocus ? colors.accent : colors.frame
                        }
                    }
                }

                Column {
                    id: body
                    width: parent.width - x - 11
                    x: thumbnail.x + thumbnail.width + 11
                    y: Math.max(10, (parent.height - height) / 2)
                    spacing: 7
                    Text {
                        objectName: "resourceTitle"
                        width: parent.width
                        text: page.highlightTitles
                            ? page.assistant.render(entry.modelData.title, entry.spans, colors.dark, page.assistant.revision)
                            : entry.modelData.title
                        textFormat: page.highlightTitles ? Text.RichText : Text.PlainText
                        Accessible.name: entry.modelData.title
                        wrapMode: Text.Wrap
                        lineHeight: 1.14
                        color: colors.ink
                        font.pixelSize: page.width < 720 ? 14 : 15
                        font.weight: Font.Medium
                    }
                    Flow {
                        width: parent.width
                        spacing: 9
                        Repeater {
                            model: [
                                entry.modelData.category === "合集资源" ? "合集" : "",
                                entry.modelData.category === "合集资源" && entry.modelData.works.length > 1
                                    ? "含 " + entry.modelData.works.join("、") : "",
                                "集数 " + entry.modelData.episode,
                                entry.modelData.resolution,
                                "字幕组 " + entry.modelData.fansub,
                                entry.modelData.size,
                                entry.modelData.date,
                                "来源 " + entry.modelData.sources
                            ]
                            Text {
                                required property string modelData
                                visible: modelData.length > 0
                                width: Math.min(implicitWidth, parent.width)
                                text: modelData
                                textFormat: Text.PlainText
                                wrapMode: Text.Wrap
                                color: colors.muted
                                font.pixelSize: 12
                            }
                        }
                    }
                }
            }
            Text {
                anchors.centerIn: parent
                visible: page.backend.rows.length > 0 && list.count === 0
                text: "没有符合当前筛选条件的资源。"
                color: colors.muted
            }
        }
    }
}
