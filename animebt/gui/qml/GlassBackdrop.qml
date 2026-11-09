import QtQuick

ShaderEffectSource {
    visible: false
    live: true
    recursive: false
    textureSize: {
        if (!sourceItem)
            return Qt.size(0, 0)
        const w = Math.max(1, sourceRect.width || sourceItem.width)
        const h = Math.max(1, sourceRect.height || sourceItem.height)
        const factor = Math.min(1, 1400 / w, 1000 / h)
        return Qt.size(Math.round(w * factor), Math.round(h * factor))
    }
}
