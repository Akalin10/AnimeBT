from dataclasses import dataclass, field
from functools import cached_property
import base64
import re
from urllib.parse import parse_qs, urlsplit
from .title import parse_title


def normalize_hash(value: str | None) -> str | None:
    value = (value or "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{40}", value):
        return value.lower()
    if re.fullmatch(r"[A-Za-z2-7]{32}", value):
        return base64.b32decode(value.upper()).hex()
    return None


def magnet_hash(magnet: str | None) -> str | None:
    for xt in parse_qs(urlsplit(magnet or "").query).get("xt", []):
        if xt.lower().startswith("urn:btih:"):
            return normalize_hash(xt[9:])
    return None


def size_bytes(value) -> int | None:
    if isinstance(value, (int, float)):
        return int(value)
    match = re.fullmatch(r"\s*([\d.]+)\s*([KMGT]?I?B)?\s*", str(value), re.I)
    if not match:
        return None
    unit = (match[2] or "B").upper()
    power = "BKMGT".index(unit[0]) if unit[0] != "B" else 0
    return int(float(match[1]) * (1024 if "I" in unit else 1000) ** power)


@dataclass
class Resource:
    title: str
    size: int | None = None
    publish_time: str | None = None
    magnet: str | None = None
    torrent_url: str | None = None
    info_hash: str | None = None
    source: str = ""
    sources: list[str] = field(default_factory=list)

    @cached_property
    def metadata(self):
        return parse_title(self.title)

    def __post_init__(self):
        self.info_hash = normalize_hash(self.info_hash) or magnet_hash(self.magnet)
        if self.info_hash and not self.magnet:
            self.magnet = f"magnet:?xt=urn:btih:{self.info_hash}"
        self.sources = self.sources or [self.source]

    @property
    def display_size(self):
        if self.size is None:
            return "未知"
        value = float(self.size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1000 or unit == "TB":
                return f"{value:.1f} {unit}"
            value /= 1000
