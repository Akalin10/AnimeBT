import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Shapes
import QtCore

Window {
    id: window
    objectName: "animebtWindow"
    title: "AnimeBT"
    width: 1100
    height: 740
    minimumWidth: 680
    minimumHeight: 520
    visible: true
    color: "transparent"
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint | Qt.WindowMinMaxButtonsHint

    readonly property bool maximized: visibility === Window.Maximized
    readonly property int frameInset: maximized ? 0 : 20
    readonly property int frameRadius: maximized ? 0 : 26
    readonly property int contentInset: surface.width >= 1100 ? 22 : 16
    required property url appearanceLocation
    property QtObject typography: null
    readonly property color ink: themeColors.ink
    readonly property color muted: themeColors.muted
    readonly property color accent: themeColors.accent
    readonly property bool animate: appearance.animations
    readonly property int motion: animate ? 160 : 0
    readonly property int navigationDuration: animate ? 330 : 0
    required property QtObject catalog
    required property QtObject resourceSearch
    required property QtObject titleAssistant
    property bool showSearchHome: false
    readonly property bool hasSearched: !showSearchHome && catalog.status !== "idle"
    readonly property bool scrollCatalogHeader: hasSearched && !resourceSearch.active
    readonly property var posterWidths: [120, 160, 200, 240]
    readonly property int posterStep: Math.max(0, Math.min(posterWidths.length - 1, appearance.posterSizeStep))
    property Item posterOrigin: null
    property int movingSubject: -1
    property url flightSource: ""
    property rect flightFrom
    property rect flightTo
    property real flightProgress: 0
    property bool flightRunning: false
    property bool flightWaiting: false
    property int navigationSerial: 0

    Settings {
        id: appearance
        location: window.appearanceLocation
        property bool darkMode: false
        property bool animations: true
        property int posterSizeStep: 2
    }
    Component.onCompleted: posterGrid.preferredWidth = posterWidths[posterStep]
    GlassThemeManager {
        id: glassOptics
        objectName: "glassThemeManager"
        colors: themeColors
        enabled: backdropLayer.hardware
        level: themeColors.dark ? 0.24 : 0.30
        viewport: Qt.size(window.width, window.height)
        motion: window.motion
        ambientBackdrop: backdropTexture
        sceneBackdrop: sceneTexture
        dialogBackdrop: dialogTexture
        dialogRect: {
            const panel = window.dialogVisual
            return panel ? Qt.rect(panel.x / window.width, panel.y / window.height,
                                  panel.width / window.width, panel.height / window.height) : Qt.rect(0, 0, 0, 0)
        }
    }
    readonly property Item dialogVisual: assistantSettings.visible ? assistantSettings.background.parent : null
    GlassTheme {
        id: themeColors
        dark: appearance.darkMode
        typography: window.typography
    }
    palette.window: themeColors.popup
    palette.windowText: themeColors.ink
    palette.text: themeColors.ink
    palette.buttonText: themeColors.ink
    palette.base: themeColors.popup
    palette.button: themeColors.panel
    palette.mid: themeColors.line
    palette.highlight: themeColors.accentFill
    palette.highlightedText: themeColors.accentInk
    palette.placeholderText: themeColors.muted

    function submitSearch() {
        const query = searchField.text.trim()
        if (!query || (catalog.keyword === query
                && (catalog.status === "loading" || resourceSearch.catalogChecking)))
            return
        cancelPosterFlight()
        settlePosterReflow()
        posterOrigin = null
        page.contentY = 0
        resourceSearch.verifyCatalog([])
        showSearchHome = false
        catalog.search(searchField.text)
    }

    function returnToSearch() {
        cancelPosterFlight()
        settlePosterReflow()
        posterOrigin = null
        showSearchHome = true
        catalog.cancel()
        resourceSearch.verifyCatalog([])
        page.cancelFlick()
        page.contentY = 0
        resourceSearch.closePage()
        searchField.clear()
        searchField.forceActiveFocus()
    }

    function cancelSearch() {
        catalog.cancel()
        resourceSearch.cancelCatalog()
    }

    function applyPosterWidth() {
        const target = posterWidths[posterStep]
        if (posterGrid.preferredWidth === target)
            return
        const oldPitch = posterGrid.rowPitch
        const oldY = page.contentY
        const gridY = Math.max(0, oldY - posterGrid.y)
        const oldRow = Math.floor(gridY / oldPitch)
        const anchor = Math.max(0, Math.min(oldRow * posterGrid.columnCount, resourceSearch.catalogResults.length - 1))
        const offset = gridY / oldPitch - oldRow
        page.cancelFlick()
        posterGrid.preferredWidth = target
        const nextY = oldY <= posterGrid.y ? oldY : posterGrid.y
            + (Math.floor(anchor / posterGrid.columnCount) + offset) * posterGrid.rowPitch
        page.contentY = Math.max(0, Math.min(nextY, page.contentHeight - page.height))
    }

    function settlePosterReflow() {
        shrinkPosters.stop()
        growPosters.stop()
        applyPosterWidth()
        posterGrid.opacity = 1
        posterGrid.reflowScale = 1
    }

    function changePosterStep(step) {
        if (step === posterStep)
            return
        appearance.posterSizeStep = step
        appearance.setValue("posterSizeStep", step)
        appearance.sync()
        if (!animate || resourceSearch.catalogResults.length === 0) {
            settlePosterReflow()
        } else if (!shrinkPosters.running) {
            growPosters.stop()
            shrinkPosters.start()
        }
    }

    ParallelAnimation {
        id: shrinkPosters
        NumberAnimation { target: posterGrid; property: "opacity"; to: 0.30; duration: 85; easing.type: Easing.InCubic }
        NumberAnimation {
            target: posterGrid
            property: "reflowScale"
            to: Math.min(1, posterGrid.widthFor(window.posterWidths[window.posterStep]) / Math.max(1, posterGrid.cardWidth))
            duration: 85
            easing.type: Easing.InCubic
        }
        onFinished: {
            const previousWidth = posterGrid.cardWidth * posterGrid.reflowScale
            window.applyPosterWidth()
            posterGrid.reflowScale = Math.min(1, previousWidth / Math.max(1, posterGrid.cardWidth))
            growPosters.start()
        }
    }

    ParallelAnimation {
        id: growPosters
        NumberAnimation { target: posterGrid; property: "opacity"; to: 1; duration: 175; easing.type: Easing.OutCubic }
        NumberAnimation { target: posterGrid; property: "reflowScale"; to: 1; duration: 175; easing.type: Easing.OutCubic }
    }

    function posterRect(item) {
        if (!item)
            return Qt.rect(0, 0, 0, 0)
        const from = item.mapToItem(surface, 0, 0)
        const to = item.mapToItem(surface, item.width, item.height)
        return Qt.rect(from.x, from.y, to.x - from.x, to.y - from.y)
    }

    function startPosterFlight(from, to) {
        flightMotion.stop()
        flightWaiting = false
        flightRunning = animate && String(flightSource).length > 0 && from.width > 0 && to.width > 0
        if (!flightRunning)
            return
        flightFrom = from
        flightTo = to
        flightProgress = 0
        flightMotion.start()
    }

    function cancelPosterFlight() {
        ++navigationSerial
        flightMotion.stop()
        flightRunning = false
        flightWaiting = false
    }

    function openPoster(id, item, cover) {
        if (shrinkPosters.running || growPosters.running)
            settlePosterReflow()
        cancelPosterFlight()
        posterOrigin = item
        movingSubject = id
        flightSource = cover
        flightFrom = posterRect(item)
        flightWaiting = animate && String(cover).length > 0
        catalog.select(id)
        if (!resourceSearch.active)
            flightWaiting = false
    }

    function returnToCatalog() {
        ++navigationSerial
        const source = flightRunning ? Qt.rect(flyingPoster.x, flyingPoster.y, flyingPoster.width, flyingPoster.height)
                                     : posterRect(resourceLoader.item ? resourceLoader.item.posterAnchor : null)
        startPosterFlight(source, posterRect(posterOrigin))
        resourceSearch.closePage()
    }

    NumberAnimation {
        id: flightMotion
        target: window
        property: "flightProgress"
        from: 0
        to: 1
        duration: window.navigationDuration
        easing.type: Easing.InOutCubic
        onFinished: window.flightRunning = false
    }
    onAnimateChanged: if (!animate) {
        if (flightRunning || flightWaiting)
            cancelPosterFlight()
        if (shrinkPosters.running || growPosters.running)
            settlePosterReflow()
    }
    onWidthChanged: if (flightRunning || flightWaiting) cancelPosterFlight()
    onHeightChanged: if (flightRunning || flightWaiting) cancelPosterFlight()

    Connections {
        target: window.catalog
        function onChanged() {
            if (!window.showSearchHome && window.catalog.status === "ready")
                window.resourceSearch.verifyCatalog(window.catalog.results)
        }
        function onSelectionChanged() {
            const selected = window.catalog.selected
            if (selected.id !== undefined) {
                window.resourceSearch.openSubject(selected, window.catalog.results)
                if (window.flightWaiting) {
                    const serial = window.navigationSerial
                    Qt.callLater(function() {
                        if (serial === window.navigationSerial && window.resourceSearch.active)
                            window.startPosterFlight(window.flightFrom,
                                window.posterRect(resourceLoader.item ? resourceLoader.item.posterAnchor : null))
                    })
                }
            }
        }
    }

    function toggleMaximized() {
        if (maximized)
            showNormal()
        else
            showMaximized()
    }

    component ChromeButton: Button {
        id: control
        property string glyphPath
        property bool destructive: false
        property bool floating: false
        width: 44
        height: 44
        hoverEnabled: true
        focusPolicy: Qt.TabFocus
        Accessible.name: text
        GlassToolTip {
            colors: themeColors
            optics: glassOptics
            text: control.text
            visible: control.hovered
            delay: 650
        }
        scale: window.animate && down ? 0.95 : 1
        Behavior on scale { NumberAnimation { duration: window.motion; easing.type: Easing.OutCubic } }

        contentItem: Item {
            Glyph {
                anchors.centerIn: parent
                path: control.glyphPath
                ink: control.destructive && control.hovered ? themeColors.danger : window.muted
            }
        }

        background: GlassSurface {
            optics: glassOptics
            radius: 12
            visible: control.floating || control.hovered || control.visualFocus
            shine: control.down ? 1.4 : control.hovered ? 0.8 : 0
            focused: control.visualFocus
            tint: control.destructive && control.hovered ? themeColors.dangerFill : glassOptics.tint
        }
    }

    component LightPool: Shape {
        id: pool
        property color glow
        Behavior on glow { ColorAnimation { duration: window.motion; easing.type: Easing.InOutSine } }
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeWidth: -1
            fillGradient: RadialGradient {
                centerX: pool.width / 2
                centerY: pool.height / 2
                focalX: centerX
                focalY: centerY
                centerRadius: pool.width / 2
                GradientStop { position: 0; color: pool.glow }
                GradientStop { position: 1; color: "transparent" }
            }
            PathLine { x: pool.width; y: 0 }
            PathLine { x: pool.width; y: pool.height }
            PathLine { x: 0; y: pool.height }
            PathLine { x: 0; y: 0 }
        }
    }

    Item {
        id: sceneContent
        objectName: "glassSceneContent"
        anchors.fill: parent
    }

    Rectangle {
        id: silhouette
        parent: sceneContent
        anchors.fill: parent
        anchors.margins: window.frameInset
        radius: window.frameRadius
        visible: false
        color: themeColors.silhouette
    }

    MultiEffect {
        parent: sceneContent
        z: -3
        anchors.fill: silhouette
        visible: !window.maximized
        source: silhouette
        shadowEnabled: true
        shadowBlur: 0.85
        blurMax: 24
        shadowVerticalOffset: 5
        shadowColor: themeColors.shadow
    }

    Item {
        id: backdropLayer
        objectName: "glassBackdropLayer"
        parent: sceneContent
        z: -2
        anchors.fill: parent
        readonly property bool hardware: GraphicsInfo.api !== GraphicsInfo.Software

        Rectangle {
            anchors.fill: parent
            anchors.margins: window.frameInset
            radius: window.frameRadius
            gradient: Gradient {
                GradientStop { position: 0; color: themeColors.backgroundTop }
                GradientStop { position: 0.58; color: themeColors.backgroundMiddle }
                GradientStop { position: 1; color: themeColors.backgroundBottom }
            }

            LightPool {
                width: Math.min(600, surface.width - 60)
                height: width
                x: surface.width - width - 30
                y: Math.max(20, (surface.height - height) * 0.28)
                scale: Math.min(1, (surface.height - 40) / height)
                glow: themeColors.blueGlow
            }
            LightPool {
                width: Math.min(440, surface.width * 0.64)
                height: width
                x: 24
                y: Math.max(20, surface.height - height - 24)
                glow: themeColors.tealGlow
            }
        }

    }

    // Captures are ordered from ambient to page to the lower modal panel.
    // A consumer is never rendered into the texture it reads.
    GlassBackdrop {
        id: backdropTexture
        objectName: "ambientGlassCapture"
        sourceItem: glassOptics.enabled ? backdropLayer : null
    }
    GlassBackdrop {
        id: sceneTexture
        objectName: "pageGlassCapture"
        sourceItem: glassOptics.enabled && glassOptics.sceneUsers > 0 ? sceneContent : null
    }
    GlassBackdrop {
        id: dialogTexture
        objectName: "dialogGlassCapture"
        sourceItem: glassOptics.enabled && glassOptics.dialogUsers > 0 ? window.dialogVisual : null
        // Preserve window-space UVs for glass surfaces inside the captured dialog.
        sourceRect: sourceItem ? Qt.rect(-sourceItem.x, -sourceItem.y, window.width, window.height)
                               : Qt.rect(0, 0, 0, 0)
    }

    Rectangle {
        id: surface
        parent: sceneContent
        anchors.fill: parent
        anchors.margins: window.frameInset
        radius: window.frameRadius
        color: "transparent"
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: "transparent"
            border.color: themeColors.frame
        }

        Item {
            id: titleBar
        z: 4
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 14
            height: 48

            GlassSurface {
                objectName: "titleBarGlass"
                anchors.fill: parent
                optics: glassOptics
                radius: 16
            }

            Item {
                anchors.left: parent.left
                anchors.right: actions.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                objectName: "dragRegion"

                DragHandler {
                    target: null
                    onActiveChanged: if (active) window.startSystemMove()
                }
                TapHandler { onDoubleTapped: window.toggleMaximized() }
            }

            Row {
                x: 12
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                Button {
                    id: homeButton
                    objectName: "homeButton"
                    width: 32
                    height: 32
                    padding: 0
                    hoverEnabled: true
                    Accessible.name: "返回 Search 首页"
                    onClicked: window.returnToSearch()
                    background: Rectangle {
                        radius: 11
                        border.color: homeButton.hovered || homeButton.visualFocus
                            ? themeColors.accent : themeColors.frame
                        gradient: Gradient {
                            GradientStop { position: 0; color: themeColors.badgeTop }
                            GradientStop { position: 1; color: themeColors.badgeBottom }
                        }
                    }
                    contentItem: Image {
                        source: "../assets/icon.png"
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "AnimeBT"
                    color: window.ink
                    font.pixelSize: 17
                    font.weight: Font.Bold
                }
            }

            Row {
                id: actions
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 3
                ChromeButton {
                    objectName: "settingsButton"
                    floating: true
                    text: "设置"
                    glyphPath: "M3 5 H17 M3 10 H17 M3 15 H17 M7 3 V7 M13 8 V12 M8 13 V17"
                    onClicked: settingsPopup.open()
                }
                Item { width: 7; height: 1 }
                Rectangle {
                    width: 1
                    height: 20
                    anchors.verticalCenter: parent.verticalCenter
                    color: themeColors.softLine
                }
                Item { width: 7; height: 1 }
                ChromeButton {
                    objectName: "minimizeButton"
                    text: "最小化"
                    glyphPath: "M5 12 H15"
                    onClicked: window.showMinimized()
                }
                ChromeButton {
                    objectName: "maximizeButton"
                    text: window.maximized ? "还原" : "最大化"
                    glyphPath: window.maximized ? "M8 5 H15 V12 M5 8 H12 V15 H5 Z"
                                                : "M5 5 H15 V15 H5 Z"
                    onClicked: window.toggleMaximized()
                }
                ChromeButton {
                    objectName: "closeButton"
                    text: "关闭"
                    destructive: true
                    glyphPath: "M5 5 L15 15 M15 5 L5 15"
                    onClicked: window.close()
                }
            }
        }

        Item {
            id: catalogTop
            parent: window.scrollCatalogHeader ? page.contentItem : surface
            z: 3
            width: surface.width
            height: catalogHeader.y + catalogHeader.height + 24

            Item {
                id: searchArea
                z: 3
                enabled: !window.resourceSearch.active
                visible: opacity > 0
                opacity: window.resourceSearch.active ? 0 : 1
                Behavior on opacity { NumberAnimation { duration: window.motion; easing.type: Easing.OutCubic } }
                y: window.scrollCatalogHeader ? 0 : titleBar.y + titleBar.height
                anchors.left: parent.left
                anchors.right: parent.right
                height: window.hasSearched ? 84 : (surface.height < 580 ? 216 : 276)
                clip: true
                Behavior on height {
                    NumberAnimation { duration: window.navigationDuration; easing.type: Easing.InOutCubic }
                }

                Text {
                    objectName: "searchHomeTitle"
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: surface.height < 580 ? 24 : 36
                    opacity: window.hasSearched ? 0 : 1
                    visible: opacity > 0
                    Behavior on opacity { NumberAnimation { duration: window.motion } }
                    text: "Search"
                    color: window.ink
                    font.pixelSize: surface.height < 580 ? 56 : 72
                    font.weight: Font.Bold
                    font.letterSpacing: -0.8
                }

                GlassTextField {
                    id: searchField
                    objectName: "searchField"
                    colors: themeColors
                    optics: glassOptics
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: searchArea.height - 74
                    width: Math.min(window.hasSearched ? 604 : 648, parent.width - (window.hasSearched ? 84 : 60))
                    Behavior on width {
                        NumberAnimation { duration: window.navigationDuration; easing.type: Easing.InOutCubic }
                    }
                    height: 60
                    font.pixelSize: width < 540 ? 16 : 18
                    color: window.ink
                    leftPadding: 52
                    rightPadding: clearButton.visible ? 144 : 100
                    Accessible.name: "动画名称"
                    onAccepted: window.submitSearch()

                    background: GlassSurface {
                        objectName: "searchGlass"
                        optics: glassOptics
                        radius: 30
                        focused: searchField.activeFocus
                        shine: searchField.hovered || searchField.activeFocus ? 0.85 : 0
                    }

                    Glyph {
                        x: 20
                        anchors.verticalCenter: parent.verticalCenter
                        ink: window.accent
                        path: "M14 8.5 A5.5 5.5 0 1 1 3 8.5 A5.5 5.5 0 0 1 14 8.5 Z M12.5 12.5 L17 17"
                    }
                    ChromeButton {
                        id: clearButton
                        text: "清空输入"
                        glyphPath: "M6 6 L14 14 M14 6 L6 14"
                        visible: searchField.length > 0
                        anchors.right: searchButton.left
                        anchors.verticalCenter: parent.verticalCenter
                        onClicked: {
                            window.cancelSearch()
                            searchField.clear()
                            searchField.forceActiveFocus()
                        }
                    }
                    Button {
                        id: searchButton
                        objectName: "searchButton"
                        readonly property bool canCancel: (window.catalog.status === "loading"
                            || window.resourceSearch.catalogChecking)
                            && window.catalog.keyword === searchField.text.trim()
                        text: canCancel ? "取消" : "搜索"
                        width: 80
                        height: 44
                        anchors.right: parent.right
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        hoverEnabled: true
                        enabled: searchField.text.trim().length > 0
                        scale: window.animate && down ? 0.95 : 1
                        Behavior on scale { NumberAnimation { duration: window.motion; easing.type: Easing.OutCubic } }
                        onClicked: {
                            if (canCancel)
                                window.cancelSearch()
                            else
                                window.submitSearch()
                        }
                        contentItem: Text {
                            text: searchButton.text
                            color: searchButton.enabled ? themeColors.accentText : window.muted
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        background: GlassSurface {
                            objectName: "searchButtonGlass"
                            optics: glassOptics
                            radius: 22
                            tint: !searchButton.enabled ? themeColors.controlBase
                                : searchButton.down ? themeColors.controlPressed
                                : searchButton.hovered ? themeColors.controlHover : themeColors.controlSelected
                            focused: searchButton.visualFocus
                            shine: searchButton.down ? 1.35 : searchButton.hovered ? 0.8 : 0
                        }
                    }
                }
            }

            // The header and its reading background move together with the catalog.
            Rectangle {
                objectName: "searchHeaderBackdrop"
                z: 2
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: parent.height
                topLeftRadius: window.frameRadius
                topRightRadius: window.frameRadius
                color: glassOptics.readingColor(themeColors.controlBase)
                opacity: catalogHeader.opacity
                visible: opacity > 0
            }

            ColumnLayout {
                id: catalogHeader
                objectName: "catalogHeader"
                z: 3
                x: window.contentInset
                anchors.top: searchArea.bottom
                width: surface.width - 2 * x
                opacity: window.hasSearched && !window.resourceSearch.active ? 1 : 0
                visible: opacity > 0
                enabled: !window.resourceSearch.active
                spacing: 6
                Behavior on opacity { NumberAnimation { duration: window.motion } }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: themeColors.softLine
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3
                        Text {
                            text: "Bangumi 搜索"
                            color: window.ink
                            font.pixelSize: window.width < 800 ? 21 : 24
                            font.weight: Font.Bold
                        }
                        Text {
                            objectName: "searchStatus"
                            Layout.fillWidth: true
                            text: {
                                switch (window.catalog.status) {
                                case "loading": return window.catalog.primaryCount > 0
                                    ? "已找到 " + window.catalog.primaryCount + " 部 · 正在处理后续结果…"
                                    : "正在搜索「" + window.catalog.keyword + "」…"
                                case "ready":
                                    const count = window.resourceSearch.catalogResults.length
                                    if (count || window.resourceSearch.catalogChecking)
                                        return ""
                                    if (window.resourceSearch.catalogCancelled)
                                        return "已取消搜索"
                                    if (window.resourceSearch.catalogIncomplete)
                                        return "部分来源未能完成搜索，暂未确认 BT 资源"
                                    return "未找到有确认 BT 资源的动画"
                                case "empty": return "未找到匹配的动画，试试日文原名或更短的关键词。"
                                case "cancelled": return "已取消搜索"
                                case "error": return window.catalog.error
                                default: return ""
                                }
                            }
                            visible: text.length > 0
                            textFormat: Text.PlainText
                            color: window.muted
                            font.pixelSize: 13
                            wrapMode: Text.Wrap
                        }
                    }
                    BusyIndicator {
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        visible: (window.catalog.status === "loading" || window.resourceSearch.catalogChecking)
                            && window.animate
                        running: visible
                    }
                    Slider {
                        id: posterSize
                        objectName: "posterSizeSlider"
                        visible: window.catalog.status === "ready"
                        Layout.preferredWidth: 184
                        Layout.preferredHeight: 38
                        from: 0
                        to: window.posterWidths.length - 1
                        stepSize: 1
                        snapMode: Slider.SnapAlways
                        value: window.posterStep
                        leftPadding: 10
                        rightPadding: 68
                        Accessible.name: "海报尺寸"
                        Accessible.description: window.posterWidths[Math.round(value)] + " 像素"
                        onMoved: window.changePosterStep(Math.round(value))
                        background: GlassSurface {
                            optics: glassOptics
                            radius: 13
                            focused: posterSize.visualFocus
                            shine: posterSize.hovered || posterSize.pressed ? 0.85 : 0
                            Rectangle {
                                x: posterSize.leftPadding + 7
                                y: (parent.height - height) / 2
                                width: posterSize.availableWidth - 14
                                height: 2
                                radius: 1
                                color: themeColors.line
                                Repeater {
                                    model: window.posterWidths.length
                                    Rectangle {
                                        required property int index
                                        x: index * parent.width / (window.posterWidths.length - 1) - width / 2
                                        y: (parent.height - height) / 2
                                        width: 5
                                        height: 5
                                        radius: 2.5
                                        color: themeColors.accent
                                    }
                                }
                            }
                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 11
                                anchors.verticalCenter: parent.verticalCenter
                                text: window.posterWidths[Math.round(posterSize.value)] + " px"
                                color: themeColors.ink
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                            }
                        }
                        handle: Rectangle {
                            x: posterSize.leftPadding + posterSize.visualPosition * (posterSize.availableWidth - width)
                            y: (posterSize.height - height) / 2
                            width: 14
                            height: 14
                            radius: 7
                            color: posterSize.pressed ? themeColors.accentPressed : themeColors.accentFill
                            border.color: themeColors.frame
                            Behavior on x { NumberAnimation { duration: posterSize.pressed ? 0 : window.motion; easing.type: Easing.OutCubic } }
                        }
                        GlassToolTip {
                            colors: themeColors
                            optics: glassOptics
                            text: "海报尺寸 · " + window.posterWidths.join(" / ") + " px"
                            visible: posterSize.hovered && !posterSize.pressed
                            delay: 650
                        }
                    }
                }
            }
        }

        Flickable {
            id: page
            objectName: "catalogPage"
            visible: window.hasSearched && (opacity > 0 || !window.resourceSearch.active)
            enabled: !window.resourceSearch.active
            opacity: window.resourceSearch.active ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: window.navigationDuration; easing.type: Easing.OutCubic } }
            anchors.top: titleBar.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 12
            contentHeight: catalogTop.height + posterGrid.height + 8
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {
                id: catalogScrollBar
                objectName: "catalogScrollBar"
                anchors.right: page.right
                // Leave the window's resize grip available beside the scrollbar.
                anchors.rightMargin: window.maximized ? 0 : 8
                policy: ScrollBar.AsNeeded
            }

            PosterGrid {
                id: posterGrid
                x: window.contentInset
                y: catalogTop.height
                width: page.width - 2 * x
                motion: window.motion
                catalog: window.catalog
                subjects: window.resourceSearch.catalogResults
                colors: themeColors
                optics: glassOptics
                viewportY: page.contentY - y
                viewportHeight: page.height
                viewportMoving: page.moving || catalogScrollBar.pressed
                hiddenSubjectId: window.flightRunning || window.flightWaiting ? window.movingSubject : -1
                onPosterActivated: (id, item, cover) => window.openPoster(id, item, cover)
            }
        }

        Loader {
            id: resourceLoader
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 14
            anchors.topMargin: titleBar.y + titleBar.height + 14
            anchors.leftMargin: window.contentInset
            anchors.rightMargin: window.contentInset
            active: window.resourceSearch.active || window.flightRunning || opacity > 0
            enabled: window.resourceSearch.active
            opacity: window.resourceSearch.active ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: window.navigationDuration; easing.type: Easing.OutCubic } }
            onActiveChanged: if (!active) window.titleAssistant.clearPending()
            sourceComponent: ResourcePage {
                backend: window.resourceSearch
                motion: window.motion
                colors: themeColors
                assistant: window.titleAssistant
                optics: glassOptics
                coverOverride: window.flightSource
                hidePoster: window.flightWaiting || window.flightRunning
                onBackRequested: window.returnToCatalog()
            }
        }

        Image {
            id: flyingPoster
            objectName: "flyingPoster"
            visible: window.flightRunning
            z: 12
            source: window.flightSource
            asynchronous: true
            cache: true
            smooth: true
            mipmap: true
            fillMode: Image.PreserveAspectCrop
            clip: true
            x: window.flightFrom.x + (window.flightTo.x - window.flightFrom.x) * window.flightProgress
            y: window.flightFrom.y + (window.flightTo.y - window.flightFrom.y) * window.flightProgress
            width: window.flightFrom.width + (window.flightTo.width - window.flightFrom.width) * window.flightProgress
            height: window.flightFrom.height + (window.flightTo.height - window.flightFrom.height) * window.flightProgress
        }

        GlassSurface {
            id: actionToast
            objectName: "resourceToast"
            parent: window.contentItem
            backdropTier: GlassSurface.Scene
            readingPlate: true
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.rightMargin: window.frameInset + 24
            anchors.bottomMargin: window.frameInset + 24 - (window.animate ? (1 - opacity) * 12 : 0)
            width: Math.min(surface.width - 48, toastLabel.implicitWidth + 32)
            height: toastLabel.height + 22
            radius: 15
            optics: glassOptics
            z: 20
            opacity: toastTimer.running ? 1 : 0
            visible: opacity > 0
            property bool success: true
            tint: success ? glassOptics.tint : themeColors.dangerFill
            Behavior on opacity { NumberAnimation { duration: window.motion } }
            Text {
                id: toastLabel
                objectName: "resourceToastText"
                anchors.centerIn: parent
                width: actionToast.width - 32
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                color: actionToast.success ? themeColors.accentText : themeColors.danger
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }
            Timer { id: toastTimer; interval: actionToast.success ? 2000 : 4800 }
            Connections {
                target: window.resourceSearch.actions
                function onFeedback(message, success) {
                    actionToast.success = success
                    toastLabel.text = message
                    toastTimer.restart()
                }
            }
        }

        GlassPopup {
            id: settingsPopup
            objectName: "settingsPopup"
            colors: themeColors
            optics: glassOptics
            x: surface.width - width - 22
            y: titleBar.y + titleBar.height + 6
            width: 324
            padding: 18
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            contentItem: Column {
                spacing: 8
                Text {
                    text: "设置"
                    color: window.ink
                    font.pixelSize: 22
                    font.weight: Font.Bold
                }
                Switch {
                    objectName: "darkModeSwitch"
                    text: "深色模式"
                    checked: appearance.darkMode
                    onToggled: {
                        appearance.darkMode = checked
                        appearance.setValue("darkMode", checked)
                        appearance.sync()
                    }
                }
                Switch {
                    objectName: "motionSwitch"
                    text: "界面动画"
                    checked: window.animate
                    onToggled: {
                        appearance.animations = checked
                        appearance.setValue("animations", checked)
                        appearance.sync()
                    }
                }
                GlassButton {
                    objectName: "titleAssistantSettings"
                    colors: themeColors
                    optics: glassOptics
                    backdropTier: GlassSurface.Scene
                    text: "AI 智能整理…"
                    onClicked: {
                        settingsPopup.close()
                        assistantSettings.open()
                    }
                }
            }
        }

        TitleSettings {
            id: assistantSettings
            assistant: window.titleAssistant
            colors: themeColors
            optics: glassOptics
            anchors.centerIn: parent
        }

        Repeater {
            model: [
                [Qt.TopEdge, Qt.SizeVerCursor], [Qt.BottomEdge, Qt.SizeVerCursor],
                [Qt.LeftEdge, Qt.SizeHorCursor], [Qt.RightEdge, Qt.SizeHorCursor],
                [Qt.TopEdge | Qt.LeftEdge, Qt.SizeFDiagCursor],
                [Qt.BottomEdge | Qt.RightEdge, Qt.SizeFDiagCursor],
                [Qt.TopEdge | Qt.RightEdge, Qt.SizeBDiagCursor],
                [Qt.BottomEdge | Qt.LeftEdge, Qt.SizeBDiagCursor]
            ]
            MouseArea {
                required property var modelData
                readonly property int edges: modelData[0]
                readonly property bool verticalEdge: edges & (Qt.TopEdge | Qt.BottomEdge)
                readonly property bool horizontalEdge: edges & (Qt.LeftEdge | Qt.RightEdge)
                readonly property int grip: 8
                x: edges & Qt.LeftEdge ? 0 : edges & Qt.RightEdge ? surface.width - width : 0
                y: edges & Qt.TopEdge ? 0 : edges & Qt.BottomEdge ? surface.height - height : 0
                width: horizontalEdge ? (verticalEdge ? 18 : grip) : surface.width
                height: verticalEdge ? (horizontalEdge ? 18 : grip) : surface.height
                enabled: !window.maximized
                cursorShape: modelData[1]
                onPressed: window.startSystemResize(edges)
            }
        }
    }

    Shortcut {
        sequence: "Ctrl+F"
        enabled: !window.resourceSearch.active
        onActivated: {
            if (window.scrollCatalogHeader) {
                page.cancelFlick()
                page.contentY = 0
            }
            searchField.forceActiveFocus()
        }
    }
    Shortcut {
        sequence: "Esc"
        enabled: !window.resourceSearch.active
                 && (window.catalog.status === "loading" || window.resourceSearch.catalogChecking)
                 && !settingsPopup.opened && !assistantSettings.opened && !searchField.editingMenuOpen
        onActivated: window.cancelSearch()
    }
    Shortcut {
        sequence: "Esc"
        enabled: window.resourceSearch.active && !settingsPopup.opened && !assistantSettings.opened
                 && (!resourceLoader.item || !resourceLoader.item.actionPopupOpen)
        onActivated: window.returnToCatalog()
    }
}
