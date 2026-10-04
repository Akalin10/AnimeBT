from dataclasses import dataclass, field, asdict
import json
from pathlib import Path
from animebt.sources import SOURCE_TYPES
from animebt.core.runtime import register_secret

THEMES = {"textual-dark": "深色", "textual-light": "浅色", "dracula": "德古拉", "nord": "北欧", "gruvbox": "复古暖色", "ram-limited": "拉姆(限定)"}


@dataclass
class Settings:
    timeout: float = 15
    cache_ttl: int = 300
    limit: int = 50
    sources: list[str] = field(default_factory=lambda: [s.name for s in SOURCE_TYPES])
    endpoints: dict[str, str] = field(default_factory=dict)
    torrent_directory: str = field(default_factory=lambda: str(Path.home() / "Downloads"))
    theme: str = "textual-dark"


def save_settings(directory: Path, settings: Settings):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "config.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_settings(directory: Path) -> Settings:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "config.json"
    if not path.exists():
        settings = Settings()
        save_settings(directory, settings)
        return settings
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("配置文件必须为 JSON 对象")
    if isinstance(data.get("qbittorrent"), dict):
        register_secret(data["qbittorrent"].get("password"))
    migrated = "qbittorrent" in data
    data.pop("qbittorrent", None)
    if set(data.get("sources", [])) == {"Anime Garden", "Mikan", "ACG.RIP", "萌番组"}:
        data["sources"] = [source.name for source in SOURCE_TYPES]
        migrated = True
    removed = {"Tokyo Toshokan", "MioBT", "AniBT", "Nyaa"}
    if removed.intersection(data.get("sources", [])):
        data["sources"] = [name for name in data["sources"] if name not in removed]
        migrated = True
    if removed.intersection(data.get("endpoints", {})):
        data["endpoints"] = {name: value for name, value in data["endpoints"].items() if name not in removed}
        migrated = True
    settings = Settings(**data)
    if settings.theme not in THEMES:
        settings.theme = "textual-dark"
        migrated = True
    if not isinstance(settings.torrent_directory, str):
        raise ValueError("种子保存目录必须为字符串")
    if not 0 < settings.timeout <= 120 or not 1 <= settings.limit <= 100 or settings.cache_ttl < 0:
        raise ValueError("配置中的 timeout、limit 或 cache_ttl 超出允许范围")
    unknown = set(settings.sources) - {s.name for s in SOURCE_TYPES}
    if unknown:
        raise ValueError(f"未知来源: {unknown}")
    if migrated:
        save_settings(directory, settings)
    return settings
