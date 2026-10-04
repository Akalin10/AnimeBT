import asyncio
from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
import time
import httpx
from animebt.models import Resource
from animebt.sources import SOURCE_TYPES
from .dedupe import deduplicate
from .matching import title_matches
from .runtime import record_error
from animebt.version import __version__


@dataclass
class SearchResult:
    resources: list[Resource] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    cached: list[str] = field(default_factory=list)
    statuses: dict[str, str] = field(default_factory=dict)


class SearchService:
    def __init__(self, settings, directory: Path, client=None, source_types=None):
        self.settings = settings
        self.directory = directory / "cache"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.client = client or httpx.AsyncClient(timeout=settings.timeout, follow_redirects=True,
                                                headers={"User-Agent": f"AnimeBT/{__version__}"})
        self.owns_client = client is None
        self.sources = [s(self.client, settings.endpoints.get(s.name), settings.limit) for s in (source_types or SOURCE_TYPES)
                        if s.name in settings.sources]

    async def close(self):
        if self.owns_client:
            await self.client.aclose()

    async def search(self, keyword, selected=None, refresh=False):
        keyword = keyword.strip()
        result = SearchResult()
        result.statuses = {s.name: "未选择" for s in self.sources}
        if not keyword:
            return result

        async def run(source):
            key = hashlib.sha256(json.dumps([source.name, source.base_url, keyword, self.settings.limit]).encode()).hexdigest()
            path = self.directory / f"{key}.json"
            try:
                if not refresh and self.settings.cache_ttl:
                    try:
                        cached = json.loads(path.read_text(encoding="utf-8"))
                        if time.time() - cached["time"] < self.settings.cache_ttl:
                            items = [Resource(**r) for r in cached["resources"]]
                            items = [r for r in items if title_matches(r.title, keyword)]
                            result.cached.append(source.name)
                            result.counts[source.name] = len(items)
                            result.statuses[source.name] = "缓存"
                            return items
                    except FileNotFoundError:
                        pass
                    except (OSError, ValueError, KeyError, TypeError) as error:
                        record_error(f"缓存读取失败 [{source.name}]，重新搜索", error)
                items = await asyncio.wait_for(source.search(keyword), self.settings.timeout)
                items = [r for r in items if title_matches(r.title, keyword)]
                result.counts[source.name] = len(items)
                result.statuses[source.name] = "成功" if items else "无结果"
                try:
                    temporary = path.with_suffix(".tmp")
                    temporary.write_text(json.dumps({"time": time.time(), "resources": [asdict(r) for r in items]},
                                                    ensure_ascii=False), encoding="utf-8")
                    temporary.replace(path)
                except OSError as error:
                    record_error(f"缓存保存失败 [{source.name}]", error)
                return items
            except Exception as error:
                record_error(f"数据源搜索失败 [{source.name}]", error)
                if isinstance(error, (TimeoutError, httpx.TimeoutException)):
                    message = "搜索超时"
                elif isinstance(error, httpx.HTTPStatusError):
                    message = f"HTTP {error.response.status_code}，来源拒绝访问或暂不可用"
                elif isinstance(error, httpx.RequestError):
                    message = "网络连接失败"
                else:
                    message = "返回数据解析失败，详情见日志"
                result.errors[source.name] = message
                result.statuses[source.name] = "超时" if message == "搜索超时" else "失败"
                return []

        groups = await asyncio.gather(*(run(s) for s in self.sources if selected is None or s.name in selected))
        result.resources = deduplicate([r for group in groups for r in group])
        return result
