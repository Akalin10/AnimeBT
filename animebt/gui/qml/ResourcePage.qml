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
    readonly property url coverSource: backend.listMode ? "" : String(coverOverride) ? coverOverride : backend.subject.cover || ""
    property bool hidePoster: false
    readonly property alias posterAnchor: detailPoster
    signal backRequested()
    property bool highlightTitles: true
    property int motion: 160
    property bool loadingMotionAllowed: true
    readonly property int loadingMotion: loadingMotionAllowed ? motion : 0
    property real loadingOpacity: backend.loading ? 1 : 0
    property real loadingHeight: backend.loading || loadingOpacity > 0 ? 68 : 0
    Behavior on loadingOpacity {
        id: loadingFadeBehavior
        enabled: page.loadingMotion > 0
        NumberAnimation {
            id: loadingFade
            duration: page.loadingMotion
            easing.type: Easing.InOutQuad
        }
    }
    Behavior on loadingHeight {
        id: loadingCollapseBehavior
        enabled: page.loadingMotion > 0
        NumberAnimation {
            id: loadingCollapse
            duration: Math.round(page.loadingMotion * 1.5)
            easing.type: Easing.InOutCubic
        }
    }
    onLoadingMotionChanged: {
        loadingFadeBehavior.enabled = loadingMotion > 0
        loadingCollapseBehavior.enabled = loadingMotion > 0
        if (loadingMotion === 0) {
            loadingFade.stop()
            loadingCollapse.stop()
            loadingOpacity = Qt.binding(() => backend.loading ? 1 : 0)
            loadingHeight = Qt.binding(() => backend.loading || loadingOpacity > 0 ? 68 : 0)
        }
    }
    property real filterOffset: 0
    property bool showSources: false
    readonly property int subjectId: backend.subject.id || 0
    readonly property bool compactHeader: height < 470
    onSubjectIdChanged: showSources = false
    readonly property string queryToken: backend.listMode ? backend.keyword : String(subjectId)
    onQueryTokenChanged: {
        episodeFilter = ""
        resolutionFilter = ""
        fansubFilter = ""
        categoryFilter = ""
        showSources = false
        menuRow = null
        copiedKey = ""
        if (copyFeedbackTimer)
            copyFeedbackTimer.stop()
        if (resourceMenu)
            resourceMenu.close()
        if (list)
            list.positionViewAtBeginning()
    }
    property string episodeFilter: ""
    property string resolutionFilter: ""
    property string fansubFilter: ""
    property string categoryFilter: ""
    property string sortOrder: "time_desc"
    readonly property bool searching: backend.loading
    onSearchingChanged: if (searching) showSources = false
    property var menuRow: null
    property string copiedKey: ""
    readonly property QtObject actions: backend.actions
    readonly property bool actionPopupOpen: resourceMenu.opened || saveDialog.visible
        || category.popupOpen || episode.popupOpen || resolution.popupOpen || fansub.popupOpen

    Connections {
        target: page.actions
        function onMagnetCopied(key) {
            page.copiedKey = key
            copyFeedbackTimer.restart()
        }
    }
    Timer {
        id: copyFeedbackTimer
        interval: 2000
        onTriggered: page.copiedKey = ""
    }

    readonly property var facets: backend.facets
    readonly property var categoryOptions: [{label: "全部 · " + facets.total, value: ""}]
        .concat(["独立资源", "合集资源"].map(key =>
            ({label: key + " · " + (facets.categories[key] || 0), value: key})))

    function applyFilters() {
        backend.resourceModel.setFilters(categoryFilter, episodeFilter, resolutionFilter, fansubFilter)
    }
    function changeFilter() {
        applyFilters()
        if (motion > 0) {
            filterOffset = 4
            filterMotion.restart()
        }
    }
    onCategoryFilterChanged: changeFilter()
    onEpisodeFilterChanged: changeFilter()
    onResolutionFilterChanged: changeFilter()
    onFansubFilterChanged: changeFilter()
    onSortOrderChanged: backend.resourceModel.setSortOrder(sortOrder)
    Component.onCompleted: {
        applyFilters()
        backend.resourceModel.setSortOrder(sortOrder)
    }
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
        const values = facets[key].slice()
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
            onTriggered: {
                page.copiedKey = ""
                page.actions.copyMagnet(page.menuRow)
            }
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
            font.pixelSize: colors.detailTextSize
        }
        GlassComboBox {
            id: combo
            colors: page.colors
            optics: page.optics
            objectName: field.label + "Filter"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.preferredHeight: 36
            textRole: "label"
            valueRole: "value"
            currentIndex: Math.max(0, (model || []).findIndex(option => option.value === field.selectedValue))
            onActivated: field.picked(currentValue)
            Accessible.name: field.label
            Binding {
                target: combo
                property: "model"
                value: field.choices
                when: !field.popupOpen
                restoreMode: Binding.RestoreNone
            }
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
            spacing: 0

            Item {
                id: workInfoPanel
                Layout.fillWidth: true
                implicitHeight: page.backend.listMode ? page.loadingHeight : workInfo.implicitHeight + 20
                Layout.bottomMargin: page.backend.listMode ? 7 * page.loadingHeight / 68 : 7

                GlassSurface {
                    visible: !page.backend.listMode
                    anchors.fill: parent
                    optics: page.optics
                    compact: true
                    readingPlate: true
                    tint: colors.controlBase
                }

                RowLayout {
                    id: workInfo
                    visible: !page.backend.listMode
                    anchors.fill: parent
                    anchors.margins: page.backend.listMode ? 0 : 10
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
                                visible: !page.backend.listMode
                                colors: page.colors
                                optics: page.optics
                                text: "返回"
                                onClicked: page.backRequested()
                            }
                            Item { Layout.fillWidth: true }
                            GlassButton {
                                colors: page.colors
                                optics: page.optics
                                objectName: "sourceDetailsToggle"
                                text: page.showSources ? "收起来源" : "来源详情"
                                visible: !page.backend.listMode && page.backend.sources.length > 0 && !page.backend.loading
                                checkable: true
                                checked: page.showSources
                                onToggled: page.showSources = checked
                            }
                            GlassButton {
                                colors: page.colors
                                optics: page.optics
                                visible: !page.backend.listMode
                                text: "重新搜索"
                                enabled: !page.backend.loading
                                onClicked: page.backend.refresh()
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: !page.backend.listMode
                            text: page.backend.subject.title || ""
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            color: colors.ink
                            font.pixelSize: page.width < 720 ? 26 : 30
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
                                font: colors.originalFont(text, 14)
                            }
                            Text {
                                id: airtime
                                anchors.verticalCenter: parent.verticalCenter
                                x: original.visible ? original.width + 8 : 0
                                text: page.backend.subject.season || ""
                                visible: text.length > 0
                                color: colors.accentText
                                font.pixelSize: colors.detailTextSize
                            }
                        }


                    }
                }
            }

            Item {
                id: loadingSlot
                Layout.fillWidth: true
                implicitHeight: 68
                Layout.bottomMargin: 7
                visible: page.backend.loading && !page.backend.listMode
                SearchLoadingBox {
                    objectName: "resourceLoadingBox"
                    parent: page.backend.listMode ? workInfoPanel : loadingSlot
                    anchors.centerIn: parent
                    opacity: page.backend.listMode ? page.loadingOpacity * Math.max(0, Math.min(1, (page.loadingHeight - 56) / 12))
                                                 : page.loadingOpacity
                    visible: opacity > 0
                    colors: page.colors
                    optics: page.optics
                    animate: page.loadingMotion > 0 && page.optics.enabled
                }
            }

            Item {
                objectName: "sourceDetails"
                Layout.fillWidth: true
                Layout.bottomMargin: 7
                implicitHeight: Math.min(sourceGrid.implicitHeight + (page.compactHeader ? 10 : 16),
                                         page.compactHeader ? 56 : 160)
                visible: page.showSources && page.backend.sources.length > 0

                GlassSurface {
                    anchors.fill: parent
                    optics: page.optics
                    compact: true
                    readingPlate: true
                    tint: colors.controlBase
                }

                ScrollView {
                    id: sourceScroll
                    anchors.fill: parent
                    anchors.margins: page.compactHeader ? 5 : 8
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    contentWidth: availableWidth
                    clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    GridLayout {
                        id: sourceGrid
                        width: sourceScroll.availableWidth
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
                                implicitHeight: sourceSummary.implicitHeight + 6
                                Column {
                                    id: sourceSummary
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
                                        font.pixelSize: colors.detailTextSize
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        width: parent.width
                                        text: source.modelData.status === "搜索中" ? "搜索中"
                                            : source.modelData.status + " · " + source.modelData.count + " 条"
                                        textFormat: Text.PlainText
                                        elide: Text.ElideRight
                                        color: source.modelData.error ? colors.danger : colors.muted
                                        font.pixelSize: colors.smallTextSize
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
            }

            Text {
                Layout.fillWidth: true
                Layout.bottomMargin: 7
                visible: !page.backend.loading && page.backend.subject.platform === "TV" && !page.backend.scheduleAvailable
                text: "Bangumi 正片排期不可用，部分季度或分段只能凭明确的标题标记确认。"
                color: colors.warning
                font.pixelSize: colors.detailTextSize
                wrapMode: Text.Wrap
            }

            GridLayout {
                Layout.fillWidth: true
                columns: page.backend.listMode ? (page.width < 900 ? 3 : 5) : 4
                columnSpacing: 6
                rowSpacing: 6
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
                ResourceFilter {
                    id: sorting
                    visible: page.backend.listMode
                    label: "排序"
                    choices: [
                        {label: "发布时间 · 从新到旧", value: "time_desc"},
                        {label: "发布时间 · 从旧到新", value: "time_asc"},
                        {label: "大小 · 从大到小", value: "size_desc"},
                        {label: "大小 · 从小到大", value: "size_asc"},
                        {label: "标题 · 升序", value: "name_asc"},
                        {label: "标题 · 降序", value: "name_desc"}
                    ]
                    selectedValue: page.sortOrder
                    onPicked: value => page.sortOrder = value
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
            model: page.backend.resourceModel
            reuseItems: true
            ScrollBar.vertical: ScrollBar {
                objectName: "resourceScrollBar"
                policy: ScrollBar.AsNeeded
            }
            delegate: Item {
                id: entry
                transform: Translate { y: page.filterOffset }
                required property var resource
                readonly property var modelData: resource
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
                    readonly property bool copied: page.copiedKey === entry.modelData.key
                    x: 10
                    y: 10
                    width: 52
                    height: 68
                    padding: 0
                    hoverEnabled: true
                    enabled: !page.actions.busy
                    scale: page.motion > 0 ? down ? 0.96 : hovered ? 1.035 : 1 : 1
                    Behavior on scale { NumberAnimation { duration: page.motion; easing.type: Easing.OutCubic } }
                    Accessible.name: (pending ? "正在获取磁链 · " : copied ? "磁链已复制 · " : "复制磁链 · ") + entry.modelData.title
                    GlassToolTip {
                        colors: page.colors
                        optics: page.optics
                        text: thumbnail.pending ? "正在获取磁链…" : thumbnail.copied ? "磁链已复制"
                              : "左键复制磁链 · 右键更多操作"
                        visible: thumbnail.hovered
                        delay: 650
                    }
                    onClicked: {
                        page.copiedKey = ""
                        page.actions.copyMagnet(entry.modelData)
                    }
                    HoverHandler { enabled: thumbnail.enabled; cursorShape: Qt.PointingHandCursor }
                    background: GlassSurface {
                        optics: page.optics
                        radius: 11
                        compact: true
                        renderOptics: entry.inViewport
                        tint: thumbnail.copied ? colors.successFill : thumbnail.down ? colors.controlPressed
                            : thumbnail.hovered ? colors.controlHover : colors.controlBase
                        focused: thumbnail.visualFocus || thumbnail.hovered
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
                            color: thumbnail.copied ? colors.successFill
                                 : miniature.status === Image.Ready ? "#cf1c263b" : "transparent"
                            Behavior on opacity { NumberAnimation { duration: page.motion } }
                            Glyph {
                                anchors.centerIn: parent
                                visible: !thumbnail.pending || page.motion === 0
                                objectName: "magnetGlyph"
                                ink: thumbnail.copied ? colors.success : miniature.status === Image.Ready ? "white" : colors.accent
                                path: thumbnail.copied ? "M4 10 L8 14 L16 6"
                                    : thumbnail.pending ? "M5 4 H15 M5 16 H15 M6 4 C6 8 14 12 14 16 M14 4 C14 8 6 12 6 16"
                                    : "M3 3 V10 A7 7 0 0 0 17 10 V3 H12 V10 A2 2 0 0 1 8 10 V3 Z M3 7 H8 M12 7 H17"
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
                        lineHeight: 1.22
                        color: colors.ink
                        font.pixelSize: page.width < 720 ? 16 : 17
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
                                font.pixelSize: colors.detailTextSize
                            }
                        }
                    }
                }
            }
            Text {
                anchors.centerIn: parent
                visible: !page.backend.loading && list.count === 0
                text: page.facets.total > 0 ? "没有符合当前筛选条件的资源。" : page.backend.emptyMessage
                width: Math.min(parent.width - 32, implicitWidth)
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                color: colors.muted
            }
        }
    }
}
