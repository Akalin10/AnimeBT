"""Configuration for GUI-only BT sources."""

import json
from pathlib import Path

from animebt.core.runtime import record_error
from animebt.sources.foreign_anime import EXTRA_SOURCE_TYPES


DEFAULT_TIMEOUTS = {source.name: 9.0 for source in EXTRA_SOURCE_TYPES}


def load_extra_sources(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or set(data) - DEFAULT_TIMEOUTS.keys():
            raise ValueError("无效的 GUI BT 来源配置")
        timeouts = {}
        for name, default in DEFAULT_TIMEOUTS.items():
            options = data.get(name, {})
            if not isinstance(options, dict):
                raise ValueError(f"{name} 配置必须为对象")
            enabled = options.get("enabled", True)
            timeout = options.get("timeout", default)
            if type(enabled) is not bool or type(timeout) not in (int, float) or not 1 <= timeout <= 15:
                raise ValueError(f"{name} 需要布尔型 enabled 及 1–15 秒的 timeout")
            if enabled:
                timeouts[name] = timeout
        return timeouts
    except FileNotFoundError:
        return DEFAULT_TIMEOUTS.copy()
    except (OSError, ValueError) as error:
        record_error("GUI BT 扩展来源配置读取失败，本次仅使用原有来源", error)
        return {}
