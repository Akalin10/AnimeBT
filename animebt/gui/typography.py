"""Configure installed UI fonts without shipping font assets."""

import re

from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QFont, QFontDatabase, QRawFont
from PySide6.QtQuick import QQuickWindow


LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
CHINESE = "动画搜索进击资源播放标题集数"
TRADITIONAL = "動畫搜尋進擊資源播放標題集數"
JAPANESE = "進撃の巨人テスト映画情報峠辻働"
UNIFIED_FAMILIES = ("MaoKenTangYuan (beta)", "猫啃网糖圆体", "猫啃糖圆体")
KANA = re.compile(r"[\u3041-\u3096\u30a1-\u30fa]")


class SystemTypography(QObject):
    def __init__(self, normal, japanese, parent):
        super().__init__(parent)
        self.normal = normal
        self.japanese = japanese

    @Slot(str, int, result=QFont)
    def readableFont(self, title, pixels):
        if self.normal.family() in UNIFIED_FAMILIES:
            return self.originalFont(title, pixels)
        font = QFont(self.normal)
        font.setStyleName("")  # Do not pin the inherited Regular face when QML requests Bold.
        installed = set(QFontDatabase.families())
        preferred = ['Yu Gothic UI', 'Segoe UI', 'Microsoft YaHei UI'] if KANA.search(title) else ['Microsoft YaHei UI', 'Segoe UI', 'Yu Gothic UI']
        font.setFamilies([name for name in preferred if name in installed] + font.families())
        font.setPixelSize(pixels)
        return font

    @Slot(str, int, result=QFont)
    def originalFont(self, title, pixels):
        font = QFont(self.japanese if KANA.search(title) else self.normal)
        font.setPixelSize(pixels)
        return font


def _sample(font):
    probe = QFont(font)
    probe.setPixelSize(16)
    return QRawFont.fromFont(probe)


def _covers(face, sample):
    return face.isValid() and all(face.glyphIndexesForString(sample))


def _preferred(families, names, sample):
    for name in names:
        family = families.get(name.casefold())
        if family and _covers(_sample(QFont(family)), sample):
            return family
    return ""


def _faces(system, sample):
    for family in QFontDatabase.families(system):
        if QFontDatabase.isFixedPitch(family):
            continue
        face = _sample(QFont(family))
        if face.familyName().casefold() != family.casefold() or not _covers(face, sample + LATIN):
            continue
        panose = bytes(face.fontTable("OS/2"))[32:42]
        if len(panose) != 10 or panose[0] != 2 or not 11 <= panose[1] <= 15:
            continue
        yield family, face


def _metrics(face):
    return face.ascent(), face.descent(), face.xHeight(), face.capHeight()


def _companion(faces, base, language):
    candidates = []
    for family, face in faces:
        distance = sum(abs(a - b) for a, b in zip(_metrics(face), _metrics(base)))
        weight = abs(face.weight() - QFont.Weight.Normal.value)
        candidates.append((language not in bytes(face.fontTable("GSUB")), distance, weight, family))
    return min(candidates)[-1] if candidates else ""


def _matched_pair(chinese, japanese):
    """Prefer a coordinated family with real weights and matching vertical metrics."""
    pairs = []
    for name, face in chinese:
        if b"ZHS " not in bytes(face.fontTable("GSUB")) or len(QFontDatabase.styles(name)) < 3:
            continue
        for jp_name, jp_face in japanese:
            if b"JAN " not in bytes(jp_face.fontTable("GSUB")) or _metrics(face) != _metrics(jp_face):
                continue
            # Regional variants generally share a family stem, e.g. Design SC / Design JP.
            if name == jp_name or name.rsplit(" ", 1)[0] != jp_name.rsplit(" ", 1)[0]:
                continue
            pairs.append((name, jp_name, face))
    return min(pairs, key=lambda pair: (pair[0], pair[1])) if pairs else None


def apply_system_typography(app):
    QQuickWindow.setTextRenderType(QQuickWindow.TextRenderType.QtTextRendering)
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    font.setWeight(QFont.Weight.Medium)
    font.setPixelSize(14)
    font.setHintingPreference(QFont.HintingPreference.PreferVerticalHinting)
    font.setStyleHint(QFont.StyleHint.SansSerif, QFont.StyleStrategy.PreferAntialias)
    installed = {family.casefold(): family for family in QFontDatabase.families()}
    unified = _preferred(installed, UNIFIED_FAMILIES, CHINESE + LATIN)
    if unified:
        fallback = [installed.get(name.casefold(), "") for name in ("Microsoft YaHei UI", "Yu Gothic UI", "Segoe UI")]
        font.setFamilies(list(dict.fromkeys(filter(None, (unified, *fallback, font.family())))))
        font.setStyleName("")
        app.setFont(font)
        return SystemTypography(font, QFont(font), app)
    base = _sample(font)
    if not base.isValid():
        app.setFont(font)
        return SystemTypography(font, font, app)

    chinese_faces = list(_faces(QFontDatabase.WritingSystem.SimplifiedChinese, CHINESE))
    japanese_faces = list(_faces(QFontDatabase.WritingSystem.Japanese, JAPANESE))
    pair = _matched_pair(chinese_faces, japanese_faces)
    if pair:
        primary, japanese, reference = pair
        chinese = ""
    else:
        primary, reference = base.familyName(), base
        chinese = "" if _covers(base, CHINESE) else _companion(chinese_faces, base, b"ZHS ")
        japanese = _companion(japanese_faces, base, b"JAN ")
    traditional = _companion(_faces(QFontDatabase.WritingSystem.TraditionalChinese, TRADITIONAL),
                             reference, b"ZHT ")
    installed = {family.casefold(): family for family in QFontDatabase.families()}
    english = _preferred(installed, ("Anthropic Serif Web Text", "Anthropic Serif Web"), LATIN)
    japanese_english = _preferred(installed, ("Anthropic Serif Web", "Anthropic Serif Web Text"), LATIN)
    jiangcheng = _preferred(installed, ("江城圆体", "江城圆体 500W"), CHINESE)
    pingfang = _preferred(installed, ("PingFang SC", "苹方-简", "萍方-简"), CHINESE)
    families = (jiangcheng, pingfang, primary, chinese, traditional, base.familyName())
    font.setFamilies(list(dict.fromkeys(filter(None, (english, *families, japanese)))))
    japanese_font = QFont(font)
    # A distinct installed alias keeps Qt's Japanese fallback cache separate.
    japanese_font.setFamilies(list(dict.fromkeys(filter(None, (japanese_english, japanese, *families)))))
    app.setFont(font)
    return SystemTypography(font, japanese_font, app)
