import QtQuick

ShaderEffectSource {
    visible: false
    live: true
    mipmap: true
    recursive: false
    textureSize: {
        if (!sourceItem)
            return Qt.size(0, 0)
        const w = Math.max(1, sourceRect.width || sourceItem.width)
        const h = Math.max(1, sourceRect.height || sourceItem.height)
        const dpr = Math.max(1, Screen.devicePixelRatio)
        const factor = Math.min(1, 1600 / (w * dpr), 1000 / (h * dpr))
        return Qt.size(Math.round(w * dpr * factor), Math.round(h * dpr * factor))
    }
}
