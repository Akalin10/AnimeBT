from pathlib import Path
import sys


def system_animations_enabled():
    if sys.platform != "win32":
        return True

    from ctypes import byref, windll
    from ctypes.wintypes import BOOL

    enabled = BOOL()
    get_client_area_animation = 0x1042
    return bool(windll.user32.SystemParametersInfoW(get_client_area_animation, 0, byref(enabled), 0)
                and enabled.value)


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

    from animebt.core.runtime import initialize_runtime
    from .bangumi import BangumiSearch
    from .bt_resources import BTResources
    from .cover_cache import CoverCacheFactory
    from .source_settings import load_extra_sources
    from .title_assistant import TitleAssistant
    from .typography import apply_system_typography

    app = QGuiApplication(sys.argv)
    app.setApplicationName("AnimeBT")
    app.setApplicationDisplayName("AnimeBT")
    app_dir = Path(__file__).parent
    app.setWindowIcon(QIcon(str(app_dir / "assets" / "icon.png")))
    QQuickStyle.setStyle("Basic")
    cache = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
    config = initialize_runtime(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
    cache_factory = CoverCacheFactory()
    engine = QQmlApplicationEngine()
    engine.setNetworkAccessManagerFactory(cache_factory)

    resources = BTResources(Path(cache) / "bt", engine,
                            extra_timeouts=load_extra_sources(config / "bt-sources.json"))
    title_assistant = TitleAssistant(config / "title-assistant.json", Path(cache) / "title-spans.sqlite3", engine)
    engine.setInitialProperties({
        "catalog": BangumiSearch(engine),
        "resourceSearch": resources,
        "titleAssistant": title_assistant,
        "typography": apply_system_typography(app),
        "appearanceLocation": QUrl.fromLocalFile(str(config / "appearance.ini")),
        "startupMotionAllowed": system_animations_enabled(),
    })
    try:
        engine.load(QUrl.fromLocalFile(str(app_dir / "qml" / "Main.qml")))
        return app.exec() if engine.rootObjects() else 1
    finally:
        title_assistant.shutdown()
        resources.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
