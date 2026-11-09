from pathlib import Path
import sys


def main():
    try:
        from PySide6.QtCore import QStandardPaths, QUrl
        from PySide6.QtGui import QGuiApplication, QIcon
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtQuickControls2 import QQuickStyle
    except ModuleNotFoundError as error:
        if error.name != "PySide6":
            raise
        print('请先安装 GUI 依赖：python -m pip install ".[gui]"', file=sys.stderr)
        return 1

    from .bangumi import BangumiSearch
    from .bt_resources import BTResources
    from .cover_cache import CoverCacheFactory
    from .source_settings import load_extra_sources
    from .title_assistant import TitleAssistant
    from .typography import apply_system_typography

    app = QGuiApplication(sys.argv)
    app.setApplicationName("AnimeBT")
    app.setApplicationDisplayName("AnimeBT")
    app.setWindowIcon(QIcon(str(Path(__file__).with_name("assets") / "icon.png")))
    typography = apply_system_typography(app)
    QQuickStyle.setStyle("Basic")
    cache_factory = CoverCacheFactory()
    engine = QQmlApplicationEngine()
    engine.setNetworkAccessManagerFactory(cache_factory)
    search = BangumiSearch(engine)
    cache = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
    config = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    resources = BTResources(Path(cache) / "bt", engine,
                            extra_timeouts=load_extra_sources(Path(config) / "bt-sources.json"))
    title_assistant = TitleAssistant(Path(config) / "title-assistant.json", Path(cache) / "title-spans.sqlite3", engine)
    engine.setInitialProperties({
        "catalog": search,
        "resourceSearch": resources,
        "titleAssistant": title_assistant,
        "typography": typography,
        "appearanceLocation": QUrl.fromLocalFile(str(Path(config) / "appearance.ini")),
    })
    qml_path = Path(__file__).with_name("qml") / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        return 1
    try:
        return app.exec()
    finally:
        title_assistant.shutdown()
        resources.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
