import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import QtQuick.Layouts
import QtCore
import QtQuick.Dialogs

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
    readonly property int frameInset: maximized ? 0 : 12
    readonly property int frameRadius: maximized ? 0 : 28
    readonly property int contentInset: surface.width >= 1100 ? 18 : 14
    required property url appearanceLocation
    property QtObject typography: null
    readonly property color ink: themeColors.ink
    readonly property color muted: themeColors.muted
    readonly property color accent: themeColors.accent
    readonly property bool animate: appearance.animations
    readonly property int motion: animate ? 160 : 0
    readonly property int navigationDuration: animate ? 330 : 0
    property bool startupMotionAllowed: false
    property bool startupActive: false
    required property QtObject catalog
    required property QtObject resourceSearch
    required property QtObject titleAssistant
    property bool showSearchHome: false
    readonly property bool listMode: appearance.searchMode === "list"
    readonly property bool hasSearched: !showSearchHome && (listMode ? resourceSearch.keyword.length > 0 : catalog.status !== "idle")
    readonly property bool scrollCatalogHeader: hasSearched && !listMode
    readonly property bool catalogLoading: !listMode && hasSearched && (catalog.status === "loading" || resourceSearch.catalogChecking)
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
        property bool liquidGlass: true
        property bool animations: true
        property bool startupAnimation: true
        property int posterSizeStep: 2
        property string searchMode: "poster"
        property real glassFrostLight: 0
        property real glassFrostDark: 0
        property url wallpaperSource: ""
        property bool wallpaperEnabled: false
        property string wallpaperFit: "fill"
        property real wallpaperBrightness: 100
    }
    readonly property url wallpaperSource: appearance.wallpaperSource
    readonly property bool wallpaperEnabled: appearance.wallpaperEnabled
    readonly property string wallpaperFit: appearance.wallpaperFit
    readonly property real wallpaperBrightness: Math.max(0, Math.min(100, appearance.wallpaperBrightness))
    function setWallpaperBrightness(value) {
        const amount = Math.max(0, Math.min(100, Number(value)))
        if (!isFinite(amount)) return
        appearance.wallpaperBrightness = amount
        wallpaperSaveTimer.restart()
    }
    Timer {
        id: wallpaperSaveTimer
        interval: 250
        onTriggered: window.saveWallpaper()
    }
    property string wallpaperError: ""
    function selectWallpaper(file) {
        const url = String(file)
        if (!url.toLowerCase().startsWith("file:") || !/\.(jpe?g|png|webp)$/i.test(url)) {
            wallpaperError = "请选择本地 JPG、PNG 或 WebP 图片"
            return false
        }
        wallpaperError = ""
        appearance.wallpaperSource = url
        appearance.wallpaperEnabled = true
        saveWallpaper()
        return true
    }
    function setWallpaperEnabled(value) {
        appearance.wallpaperEnabled = value && String(appearance.wallpaperSource).length > 0
        wallpaperError = ""
        saveWallpaper()
    }
    function setWallpaperFit(index) {
        appearance.wallpaperFit = Number(index) === 1 ? "fit" : "fill"
        saveWallpaper()
    }
    function saveWallpaper() {
        wallpaperSaveTimer.stop()
        appearance.setValue("wallpaperSource", appearance.wallpaperSource)
        appearance.setValue("wallpaperEnabled", appearance.wallpaperEnabled)
        appearance.setValue("wallpaperFit", appearance.wallpaperFit)
        appearance.setValue("wallpaperBrightness", window.wallpaperBrightness)
        appearance.sync()
    }
    FileDialog {
        id: wallpaperPicker
        objectName: "wallpaperPicker"
        title: "选择背景图片"
        fileMode: FileDialog.OpenFile
        nameFilters: ["图片 (*.jpg *.jpeg *.png *.webp)"]
        onAccepted: window.selectWallpaper(selectedFile)
    }
    Component.onCompleted: {
        resourceSearch.attachTitleAssistant(titleAssistant)
        posterGrid.preferredWidth = posterWidths[posterStep]
        startupActive = startupMotionAllowed && appearance.startupAnimation && appearance.animations
        resourceSearch.setListMode(listMode)
    }
    GlassThemeManager {
        id: glassOptics
        objectName: "glassThemeManager"
        colors: themeColors
        liquidGlass: appearance.liquidGlass
        enabled: appearance.liquidGlass && backdropLayer.hardware
        level: window.glassFrost / 100
        viewport: Qt.size(window.width, window.height)
        motion: window.motion
        sharedBlur: true
        ambientBackdrop: sharedBlur.texture
        sceneBackdrop: sceneTexture
        dialogBackdrop: dialogTexture
        dialogRect: {
            const panel = window.dialogVisual
            if (!panel)
                return Qt.rect(0, 0, 0, 0)
            const origin = window.dialogOrigin
            return Qt.rect(origin.x / window.width, origin.y / window.height,
                           panel.width / window.width, panel.height / window.height)
        }
    }
    // Capture the lower material plane, never the controls/text which sample it.
    readonly property Item dialogVisual: assistantSettings.visible ? assistantSettings.background : null
    readonly property real glassFrost: Math.max(0, Math.min(100,
        themeColors.dark ? appearance.glassFrostDark : appearance.glassFrostLight))
    function changeGlassFrost(value) {
        const amount = Math.max(0, Math.min(100, Number(value)))
        if (!isFinite(amount))
            return
        if (themeColors.dark)
            appearance.glassFrostDark = amount
        else
            appearance.glassFrostLight = amount
        materialSaveTimer.restart()
    }
    function saveGlassFrost() {
        materialSaveTimer.stop()
        appearance.setValue("glassFrostLight", appearance.glassFrostLight)
        appearance.setValue("glassFrostDark", appearance.glassFrostDark)
        appearance.sync()
    }
    Timer {
        id: materialSaveTimer
        interval: 250
        onTriggered: window.saveGlassFrost()
    }
    onClosing: {
        if (materialSaveTimer.running) saveGlassFrost()
        if (wallpaperSaveTimer.running) saveWallpaper()
    }
    readonly property point dialogOrigin: {
        const panel = dialogVisual
        const visual = panel ? panel.parent : null
        // Track the popup item's x/y explicitly; mapToItem alone does not create
        // geometry dependencies when a status message changes popup height.
        return visual && visual.parent
            ? visual.parent.mapToItem(window.contentItem, visual.x + panel.x, visual.y + panel.y)
            : Qt.point(0, 0)
    }
    GlassTheme {
        id: themeColors
        wallpaperTextShadow: wallpaperLayer.active
        liquidGlass: appearance.liquidGlass
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
        if (listMode) {
            if (query) {
                showSearchHome = false
                resourceSearch.searchKeyword(query)
            }
            return
        }
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
        if (listMode) {
            resourceSearch.cancelSearch()
            return
        }
        catalog.cancel()
        resourceSearch.cancelCatalog()
    }

    function changeSearchMode(mode) {
        if (appearance.searchMode === mode)
            return
        showSearchHome = true
        cancelPosterFlight()
        settlePosterReflow()
        posterOrigin = null
        flightSource = ""
        resourceSearch.setListMode(mode === "list")
        catalog.reset()
        page.cancelFlick()
        page.contentY = 0
        appearance.searchMode = mode
        appearance.setValue("searchMode", mode)
        appearance.sync()
    }

    function applyPosterWidth() {
        const target = posterWidths[posterStep]
        if (posterGrid.preferredWidth === target)
            return
        const oldPitch = posterGrid.rowPitch
        const oldY = page.contentY
        const gridY = Math.max(0, oldY - posterGrid.y)
        const oldRow = Math.floor(gridY / oldPitch)
        const anchor = Math.max(0, Math.min(oldRow * posterGrid.columnCount, posterGrid.subjectCount - 1))
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
        if (!animate || posterGrid.subjectCount === 0) {
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
        if (listMode) {
            showSearchHome = true
            resourceSearch.closePage()
            return
        }
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
            if (!window.listMode && !window.showSearchHome)
                window.resourceSearch.extendCatalog(window.catalog.candidates, window.catalog.status !== "loading")
        }
        function onSelectionChanged() {
            const selected = window.catalog.selected
            if (selected.id !== undefined) {
                window.resourceSearch.openSubject(selected, window.catalog.candidates)
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
        property bool chromeCompact: false
        width: chromeCompact ? 36 : 44
        height: chromeCompact ? 36 : 44
        padding: 0
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
            radius: control.chromeCompact ? 10 : 12
            visible: control.floating || control.hovered || control.visualFocus
            focused: control.visualFocus || control.hovered
            tint: control.destructive && control.hovered ? themeColors.dangerFill
                : control.down ? themeColors.controlPressed
                : control.hovered ? themeColors.controlHover : glassOptics.tint
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

    Loader {
        parent: sceneContent
        z: -3
        anchors.fill: silhouette
        active: themeColors.liquidGlass && !window.maximized
        sourceComponent: MultiEffect {
            anchors.fill: parent
            source: silhouette
            shadowEnabled: true
            shadowBlur: 0.85
            blurMax: 24
            shadowVerticalOffset: 5
            shadowColor: themeColors.shadow
        }
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
            visible: wallpaperLayer.active
            color: themeColors.backgroundTop
        }
        AmbientBackground {
            anchors.fill: parent
            anchors.margins: window.frameInset
            colors: themeColors
            radius: window.frameRadius
            visible: !wallpaperLayer.active
        }
        WallpaperBackground {
            id: wallpaperLayer
            anchors.fill: parent
            anchors.margins: window.frameInset
            source: appearance.wallpaperSource
            enabledWallpaper: appearance.liquidGlass && appearance.wallpaperEnabled
            fit: appearance.wallpaperFit === "fit"
            brightness: window.wallpaperBrightness
            radius: window.frameRadius
            onFailed: window.wallpaperError = "图片不可用，已恢复默认背景"
            onReady: window.wallpaperError = ""
        }
    }

    // Captures are ordered from ambient to page to the lower modal panel.
    // A consumer is never rendered into the texture it reads.
    GlassBackdrop {
        id: backdropTexture
        objectName: "ambientGlassCapture"
        sourceItem: glassOptics.enabled ? backdropLayer : null
    }
    BackdropBlur {
        id: sharedBlur
        sourceTexture: backdropTexture
        enabledBlur: glassOptics.enabled
        radius: glassOptics.blurRadius
        viewport: glassOptics.viewport
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
        sourceRect: {
            if (!sourceItem)
                return Qt.rect(0, 0, 0, 0)
            const origin = window.dialogOrigin
            return Qt.rect(-origin.x, -origin.y, window.width, window.height)
        }
    }

    Rectangle {
        id: surface
        parent: sceneContent
        anchors.fill: parent
        anchors.margins: window.frameInset
        radius: window.frameRadius
        color: "transparent"
        visible: !window.startupActive || (startupLayer.item && startupLayer.item.revealing)
        enabled: !window.startupActive
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: "transparent"
            border.color: themeColors.frame
        }

        Item {
            id: chromeLayer
            objectName: "fixedWindowChrome"
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: titleBar.y + titleBar.height + 10
            z: 20
        }

        Item {
            id: titleBar
            objectName: "windowTitleBar"
            parent: chromeLayer
            z: 1
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: window.contentInset
            anchors.rightMargin: window.contentInset
            anchors.topMargin: 8
            height: 48

            GlassSurface {
                objectName: "titleBarGlass"
                material: GlassSurface.Chrome
                anchors.fill: parent
                optics: glassOptics
                radius: 20
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
                        color: "transparent"
                    }
                    contentItem: Image {
                        source: "../assets/icon.png"
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                    }
                }
                ShadowText { theme: themeColors;
                    anchors.verticalCenter: parent.verticalCenter
                    text: "AnimeBT"
                    color: window.ink
                    font.pixelSize: 19
                    font.weight: Font.DemiBold
                }
            }

            Row {
                id: actions
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                spacing: 3
                ChromeButton {
                    objectName: "settingsButton"
                    chromeCompact: true
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
                    chromeCompact: true
                    text: "最小化"
                    glyphPath: "M5 12 H15"
                    onClicked: window.showMinimized()
                }
                ChromeButton {
                    objectName: "maximizeButton"
                    chromeCompact: true
                    text: window.maximized ? "还原" : "最大化"
                    glyphPath: window.maximized ? "M8 5 H15 V12 M5 8 H12 V15 H5 Z"
                                                : "M5 5 H15 V15 H5 Z"
                    onClicked: window.toggleMaximized()
                }
                ChromeButton {
                    objectName: "closeButton"
                    chromeCompact: true
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
            height: searchArea.y + searchArea.height + (searchStatus.visible ? searchStatus.height + 8 : 0)

            Item {
                id: searchArea
                z: 3
                enabled: window.listMode || !window.resourceSearch.active
                visible: opacity > 0
                opacity: window.resourceSearch.active && !window.listMode ? 0 : 1
                Behavior on opacity { NumberAnimation { duration: window.motion; easing.type: Easing.OutCubic } }
                y: window.scrollCatalogHeader ? 0 : chromeLayer.height
                anchors.left: parent.left
                anchors.right: parent.right
                height: window.hasSearched ? 84 : (surface.height < 580 ? 216 : 276)
                clip: true
                Behavior on height {
                    NumberAnimation { duration: window.navigationDuration; easing.type: Easing.InOutCubic }
                }

                ShadowText { theme: themeColors;
                    objectName: "searchHomeTitle"
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: surface.height < 580 ? 24 : 36
                    opacity: window.hasSearched ? 0 : 1
                    visible: opacity > 0
                    Behavior on opacity { NumberAnimation { duration: window.motion } }
                    text: "Search"
                    color: window.ink
                    font.pixelSize: surface.height < 580 ? 56 : 72
                    font.weight: Font.DemiBold
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
                    font.pixelSize: width < 540 ? 18 : 20
                    color: window.ink
                    leftPadding: 52
                    rightPadding: clearButton.visible ? 144 : 100
                    Accessible.name: window.listMode ? "资源关键词" : "动画名称"
                    onAccepted: window.submitSearch()
                    showExtraActions: window.listMode
                    extraActions: [
                        Action {
                            objectName: "searchSourceDetails"
                            text: "来源详情"
                            enabled: window.listMode && window.resourceSearch.active
                                && window.resourceSearch.sources.length > 0 && resourceLoader.item !== null
                            checkable: true
                            checked: resourceLoader.item ? resourceLoader.item.showSources : false
                            onTriggered: {
                                if (resourceLoader.item)
                                    resourceLoader.item.showSources = checked
                            }
                        },
                        Action {
                            objectName: "searchDeepSearch"
                            text: "深入搜索"
                            enabled: window.listMode && window.resourceSearch.active && !window.resourceSearch.loading
                                && window.resourceSearch.keyword.length > 0
                                && window.resourceSearch.keyword === searchField.text.trim()
                            onTriggered: window.resourceSearch.refresh()
                        }
                    ]

                    background: GlassSurface {
                        objectName: "searchGlass"
                        optics: glassOptics
                        radius: 30
                        focused: searchField.activeFocus
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
                        readonly property bool canCancel: window.listMode
                            ? window.resourceSearch.loading && window.resourceSearch.keyword === searchField.text.trim()
                            : (window.catalog.status === "loading" || window.resourceSearch.catalogChecking)
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
                        contentItem: ShadowText { theme: themeColors;
                            text: searchButton.text
                            color: themeColors.plainDark && searchButton.enabled ? themeColors.accentInk
                                 : searchButton.enabled ? themeColors.accentText : window.muted
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.pixelSize: themeColors.textSize
                            font.weight: Font.DemiBold
                        }
                        background: GlassSurface {
                            objectName: "searchButtonGlass"
                            optics: glassOptics
                            radius: 22
                            tint: themeColors.plainDark && searchButton.enabled
                                ? (searchButton.down ? themeColors.accentPressed : searchButton.hovered ? themeColors.accentHover : themeColors.accent)
                                : !searchButton.enabled ? themeColors.controlBase
                                : searchButton.down ? themeColors.controlPressed
                                : searchButton.hovered ? themeColors.controlHover : themeColors.controlSelected
                            focused: searchButton.visualFocus
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
                color: "transparent"
                opacity: window.hasSearched && (window.listMode || !window.resourceSearch.active) ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: window.motion } }
                visible: opacity > 0
            }

            ShadowText { theme: themeColors;
                id: searchStatus
                objectName: "searchStatus"
                z: 3
                x: window.contentInset
                anchors.top: searchArea.bottom
                width: surface.width - 2 * x
                text: {
                    switch (window.catalog.status) {
                    case "loading": return ""
                    case "ready":
                        const count = posterGrid.subjectCount
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
                visible: !window.listMode && window.hasSearched && text.length > 0 && !window.resourceSearch.active
                textFormat: Text.PlainText
                color: window.muted
                font.pixelSize: themeColors.detailTextSize
                wrapMode: Text.Wrap
            }
        }

        Flickable {
            id: page
            objectName: "catalogPage"
            visible: !window.listMode && window.hasSearched && (opacity > 0 || !window.resourceSearch.active)
            enabled: !window.resourceSearch.active
            opacity: window.resourceSearch.active ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: window.navigationDuration; easing.type: Easing.OutCubic } }
            anchors.top: chromeLayer.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 12
            contentHeight: posterGrid.y + posterGrid.height + 8
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: GlassScrollBar {
                colors: themeColors
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
                y: catalogTop.height + 12
                width: page.width - 2 * x
                motion: window.motion
                catalog: window.catalog
                subjects: window.resourceSearch.catalogModel
                loading: window.catalogLoading
                animateLoading: window.animate && backdropLayer.hardware
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
            anchors.topMargin: window.listMode ? catalogTop.height + 6 : chromeLayer.height + 14
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
                loadingMotionAllowed: window.startupMotionAllowed
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
            backdropTier: GlassSurface.Ambient
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
            ShadowText { theme: themeColors;
                id: toastLabel
                objectName: "resourceToastText"
                anchors.centerIn: parent
                width: actionToast.width - 32
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                color: actionToast.success ? themeColors.accentText : themeColors.danger
                font.pixelSize: themeColors.detailTextSize
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
            y: chromeLayer.height + 6
            width: 324
            height: Math.min(implicitHeight, surface.height - y - 12)
            padding: 18
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            contentItem: ScrollView {
                id: settingsScroll
                implicitHeight: settingsContent.implicitHeight
                contentWidth: availableWidth
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ScrollBar.vertical: GlassScrollBar { colors: themeColors }
                Column {
                    id: settingsContent
                    width: settingsScroll.availableWidth
                    spacing: 8
                    ShadowText { theme: themeColors;
                        text: "设置"
                        color: window.ink
                        font.pixelSize: 24
                        font.weight: Font.DemiBold
                    }
                    ShadowText { theme: themeColors;
                        text: "搜索模式"
                        color: window.muted
                        font.pixelSize: themeColors.detailTextSize
                    }
                    ButtonGroup { id: searchModes }
                    Row {
                        spacing: 6
                        GlassRadioButton {
                            objectName: "posterModeOption"
                            colors: themeColors
                            optics: glassOptics
                            text: "图鉴检索"
                            checked: !window.listMode
                            ButtonGroup.group: searchModes
                            onClicked: window.changeSearchMode("poster")
                        }
                        GlassRadioButton {
                            objectName: "listModeOption"
                            colors: themeColors
                            optics: glassOptics
                            text: "列表检索"
                            checked: window.listMode
                            ButtonGroup.group: searchModes
                            onClicked: window.changeSearchMode("list")
                        }
                    }
                    GlassSwitch {
                        objectName: "liquidGlassSwitch"
                        width: parent.width
                        colors: themeColors
                        optics: glassOptics
                        text: "Liquid Glass"
                        checked: appearance.liquidGlass
                        onToggled: {
                            appearance.liquidGlass = checked
                            appearance.setValue("liquidGlass", checked)
                            appearance.sync()
                        }
                    }
                    GlassSwitch {
                        colors: themeColors
                        optics: glassOptics
                        objectName: "darkModeSwitch"
                        text: "深色模式"
                        checked: appearance.darkMode
                        onToggled: {
                            appearance.darkMode = checked
                            appearance.setValue("darkMode", checked)
                            appearance.sync()
                        }
                    }
                    GlassSwitch {
                        colors: themeColors
                        optics: glassOptics
                        objectName: "motionSwitch"
                        text: "界面动画"
                        checked: window.animate
                        onToggled: {
                            appearance.animations = checked
                            appearance.setValue("animations", checked)
                            appearance.sync()
                        }
                    }
                    GlassSwitch {
                        colors: themeColors
                        optics: glassOptics
                        objectName: "startupAnimationSwitch"
                        text: "启动动画"
                        checked: appearance.startupAnimation
                        onToggled: {
                            appearance.startupAnimation = checked
                            appearance.setValue("startupAnimation", checked)
                            appearance.sync()
                        }
                    }
                    Column {
                        enabled: appearance.liquidGlass
                        width: parent.width
                        spacing: 5
                        RowLayout {
                            width: parent.width
                            ShadowText { theme: themeColors;
                                Layout.fillWidth: true
                                text: "Clear ↔ Tinted"
                                color: window.ink
                                font.pixelSize: themeColors.detailTextSize
                            }
                            ShadowText { theme: themeColors;
                                text: Math.round(window.glassFrost) + "%"
                                color: window.muted
                                font.pixelSize: themeColors.smallTextSize
                            }
                        }
                        GlassSlider {
                            objectName: "glassFrostSlider"
                            from: 0
                            to: 100
                            stepSize: 0.1
                            width: parent.width
                            colors: themeColors
                            optics: glassOptics
                            value: window.glassFrost
                            Accessible.name: "Clear 到 Tinted 背景磨砂强度"
                            onMoved: window.changeGlassFrost(value)
                            onPressedChanged: if (!pressed) window.saveGlassFrost()
                        }
                        RowLayout {
                            width: parent.width
                            ShadowText { theme: themeColors; text: "Clear 清透"; color: window.muted; font.pixelSize: themeColors.smallTextSize }
                            Item { Layout.fillWidth: true }
                            ShadowText { theme: themeColors; text: "Tinted 磨砂"; color: window.muted; font.pixelSize: themeColors.smallTextSize }
                        }
                    }
                    RowLayout {
                        width: parent.width
                        spacing: 12
                        ShadowText { theme: themeColors;
                            Layout.fillWidth: true
                            text: "海报尺寸"
                            color: window.ink
                            font.pixelSize: themeColors.detailTextSize
                        }
                        Slider {
                            id: posterSize
                            objectName: "posterSizeSlider"
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
                                ShadowText { theme: themeColors;
                                    anchors.right: parent.right
                                    anchors.rightMargin: 11
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: window.posterWidths[Math.round(posterSize.value)] + " px"
                                    color: themeColors.ink
                                    font.pixelSize: themeColors.detailTextSize
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
                    Column {
                        width: parent.width
                        spacing: 8
                        enabled: appearance.liquidGlass
                        ShadowText { theme: themeColors; text: "自定义背景"; color: window.ink; font.pixelSize: themeColors.detailTextSize }
                        GlassSwitch {
                            objectName: "wallpaperEnabledSwitch"
                            width: parent.width
                            colors: themeColors
                            optics: glassOptics
                            text: "使用自定义背景"
                            enabled: String(appearance.wallpaperSource).length > 0
                            checked: appearance.wallpaperEnabled
                            onToggled: window.setWallpaperEnabled(checked)
                        }
                        RowLayout {
                            width: parent.width
                            GlassButton {
                                objectName: "chooseWallpaperButton"
                                colors: themeColors; optics: glassOptics
                                text: "选择图片"
                                onClicked: wallpaperPicker.open()
                            }
                            GlassButton {
                                objectName: "resetWallpaperButton"
                                colors: themeColors; optics: glassOptics
                                text: "恢复默认"
                                onClicked: window.setWallpaperEnabled(false)
                            }
                        }
                        Image {
                            objectName: "wallpaperPreview"
                            width: parent.width
                            height: String(appearance.wallpaperSource).length ? 104 : 0
                            visible: height > 0
                            source: settingsPopup.visible ? appearance.wallpaperSource : ""
                            sourceSize: Qt.size(320, 180)
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true; cache: true; smooth: true; autoTransform: true
                        }
                        GlassComboBox {
                            objectName: "wallpaperFitCombo"
                            width: parent.width
                            colors: themeColors; optics: glassOptics
                            model: ["填充（裁剪）", "适应"]
                            currentIndex: appearance.wallpaperFit === "fit" ? 1 : 0
                            onActivated: window.setWallpaperFit(currentIndex)
                        }
                        Column {
                            width: parent.width
                            spacing: 5
                            enabled: wallpaperLayer.active
                            RowLayout {
                                width: parent.width
                                ShadowText { theme: themeColors; Layout.fillWidth: true; text: "背景亮度"; color: window.ink; font.pixelSize: themeColors.detailTextSize }
                                ShadowText { theme: themeColors; text: Math.round(window.wallpaperBrightness) + "%"; color: window.muted; font.pixelSize: themeColors.smallTextSize }
                            }
                            GlassSlider {
                                objectName: "wallpaperBrightnessSlider"
                                width: parent.width
                                colors: themeColors; optics: glassOptics
                                from: 0; to: 100; stepSize: 0.1
                                value: window.wallpaperBrightness
                                Accessible.name: "背景亮度"
                                onMoved: window.setWallpaperBrightness(value)
                                onPressedChanged: if (!pressed) window.saveWallpaper()
                            }
                            RowLayout {
                                width: parent.width
                                ShadowText { theme: themeColors; text: "较暗"; color: window.muted; font.pixelSize: themeColors.smallTextSize }
                                Item { Layout.fillWidth: true }
                                ShadowText { theme: themeColors; text: "原图"; color: window.muted; font.pixelSize: themeColors.smallTextSize }
                            }
                        }
                        ShadowText { theme: themeColors;
                            width: parent.width
                            visible: text.length > 0
                            text: window.wallpaperError || (appearance.wallpaperEnabled && !backdropLayer.hardware ? "软件渲染暂使用默认背景" : "")
                            wrapMode: Text.Wrap
                            color: themeColors.warning
                            font.pixelSize: themeColors.smallTextSize
                        }
                    }
                    GlassButton {
                        objectName: "titleAssistantSettings"
                        colors: themeColors
                        optics: glassOptics
                        backdropTier: GlassSurface.Ambient
                        text: "AI 智能整理…"
                        onClicked: {
                            settingsPopup.close()
                            assistantSettings.open()
                        }
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

    Loader {
        id: startupLayer
        parent: sceneContent
        anchors.fill: surface
        z: 1
        active: window.startupActive
        sourceComponent: Splash {
            colors: themeColors
            radius: window.frameRadius
            onFinished: window.startupActive = false
        }
    }

    Connections {
        target: window
        enabled: window.startupActive
        function onFrameSwapped() {
            if (startupLayer.item)
                startupLayer.item.start()
        }
    }

    Shortcut {
        sequence: "Ctrl+F"
        enabled: !window.startupActive && (window.listMode || !window.resourceSearch.active)
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
        enabled: (window.listMode ? window.resourceSearch.loading
                 : !window.resourceSearch.active && (window.catalog.status === "loading" || window.resourceSearch.catalogChecking))
                 && !settingsPopup.opened && !assistantSettings.opened && !searchField.editingMenuOpen
        onActivated: window.cancelSearch()
    }
    Shortcut {
        sequence: "Esc"
        enabled: window.resourceSearch.active && !(window.listMode && window.resourceSearch.loading)
                 && !settingsPopup.opened && !assistantSettings.opened
                 && (!resourceLoader.item || !resourceLoader.item.actionPopupOpen)
        onActivated: window.returnToCatalog()
    }
}
