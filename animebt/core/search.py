import asyncio
from dataclasses import asdict, dataclass, field, replace
from contextlib import aclosing
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
import time
import httpx
from animebt.models import Resource
from animebt.sources import SOURCE_TYPES
from animebt.sources.adapters import MAX_SEARCH_PAGES, QueryAudit, query_audit
from .dedupe import deduplicate
from .matching import title_matches
from .runtime import logger, record_error
from animebt.version import __version__


CACHE_VERSION = 3


@dataclass
class SearchResult:
    resources: list[Resource] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    cached: list[str] = field(default_factory=list)
    statuses: dict[str, str] = field(default_factory=dict)
    raw_counts: dict[str, int] = field(default_factory=dict)
    eligible_counts: dict[str, int] = field(default_factory=dict)
    candidates: list[Resource] = field(default_factory=list)
    incomplete: dict[str, str] = field(default_factory=dict)


class SearchService:
    def __init__(self, settings, directory: Path, client=None, source_types=None, source_timeouts=None):
        self.settings = settings
        self.directory = directory / "cache"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.client = client or httpx.AsyncClient(timeout=settings.timeout, follow_redirects=True,
                                                headers={"User-Agent": f"AnimeBT/{__version__}"})
        self.owns_client = client is None
        self.source_timeouts = source_timeouts or {}
        self.request_slots = asyncio.Semaphore(12)
        self.sources = [s(self.client, settings.endpoints.get(s.name), settings.limit) for s in (source_types or SOURCE_TYPES)
                        if s.name in settings.sources]

    async def close(self):
        if self.owns_client:
            await self.client.aclose()

    async def search(self, keyword, selected=None, refresh=False, *, on_page=None, collect=False,
                     page_budget=MAX_SEARCH_PAGES):
        keyword = keyword.strip()
        result = SearchResult()
        result.statuses = {s.name: "未选择" for s in self.sources}
        if not keyword:
            return result

        async def run(source):
            cache_key = [CACHE_VERSION, source.name, source.base_url, keyword, self.settings.limit, collect, page_budget]
            if namespace := getattr(source, "cache_namespace", ""):
                cache_key.append(namespace)
            key = hashlib.sha256(json.dumps(cache_key).encode()).hexdigest()
            path = self.directory / f"{key}.json"
            items = []
            raw_count = 0
            eligible_count = 0
            pages = 0
            audit = QueryAudit(collect, page_budget, self.request_slots)
            token = query_audit.set(audit)
            try:
                if not refresh and self.settings.cache_ttl:
                    try:
                        cached = json.loads(path.read_text(encoding="utf-8"))
                        ttl = self.settings.cache_ttl
                        if collect and (not cached["resources"] or cached.get("incomplete")):
                            ttl = min(ttl, 45)
                        if 0 <= time.time() - cached["time"] < ttl:
                            cached_items = (Resource(**r) for r in cached["resources"])
                            items = [r for r in cached_items if collect or title_matches(r.title, keyword)]
                            pages = cached.get("pages", 0)
                            if cached.get("incomplete"):
                                result.incomplete[source.name] = cached["incomplete"]
                            result.cached.append(source.name)
                            result.counts[source.name] = len(items)
                            if "raw_count" in cached:
                                result.raw_counts[source.name] = cached["raw_count"]
                            if "eligible_count" in cached:
                                result.eligible_counts[source.name] = cached["eligible_count"]
                            result.statuses[source.name] = "缓存"
                            if on_page is not None and items:
                                on_page(items)
                            return items
                    except FileNotFoundError:
                        pass
                    except (OSError, ValueError, KeyError, TypeError) as error:
                        record_error(f"缓存读取失败 [{source.name}]，重新搜索", error)
                async with asyncio.timeout(self.source_timeouts.get(source.name, self.settings.timeout)):
                    async with aclosing(source.search_pages(keyword)) as stream:
                        async for page in stream:
                            pages += 1
                            raw_count += getattr(page, "raw_count", len(page))
                            eligible_count += len(page)
                            if reason := getattr(page, "incomplete", ""):
                                result.incomplete[source.name] = reason
                            matched = ([replace(r, query=keyword,
                                                origins=[[source.name, keyword, str(r.source_id or "")]]) for r in page] if collect
                                       else [r for r in page if title_matches(r.title, keyword)])
                            items.extend(matched)
                            if on_page is not None and matched:
                                on_page(matched)
                result.raw_counts[source.name] = raw_count
                result.eligible_counts[source.name] = eligible_count
                result.counts[source.name] = len(items)
                result.statuses[source.name] = "成功" if items else "无结果"
                if self.settings.cache_ttl:
                    self._save_cache(path, {
                        "time": time.time(), "raw_count": raw_count, "eligible_count": eligible_count, "pages": pages,
                        "incomplete": result.incomplete.get(source.name), "resources": [asdict(r) for r in items],
                    })
                return items
            except asyncio.CancelledError:
                result.statuses[source.name] = "已取消"
                raise
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
                if raw_count:
                    result.raw_counts[source.name] = raw_count
                    result.eligible_counts[source.name] = eligible_count
                result.counts[source.name] = len(items)
                if items:
                    result.counts[source.name] = len(items)
                    result.statuses[source.name] = "部分结果"
                else:
                    result.statuses[source.name] = "超时" if message == "搜索超时" else "失败"
                return items
            finally:
                query_audit.reset(token)
                if collect:
                    logger.info("BT request source=%s keyword=%r scope=%s requests=%s pages=%s raw=%s normalized=%s "
                                "candidates=%s status=%s incomplete=%r error=%r trace=%r",
                                source.name, keyword, source.coverage, len(audit.requests), pages,
                                result.raw_counts.get(source.name, raw_count if pages else None),
                                result.eligible_counts.get(source.name, eligible_count if pages else None), len(items),
                                result.statuses.get(source.name, "已取消"),
                                result.incomplete.get(source.name), result.errors.get(source.name), audit.requests)

        groups = await asyncio.gather(*(run(s) for s in self.sources if selected is None or s.name in selected))
        result.candidates = [r for group in groups for r in group]
        result.resources = result.candidates if collect else deduplicate(result.candidates)
        return result

    @staticmethod
    def _save_cache(path, payload):
        temporary = None
        try:
            with NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False, mode="w", encoding="utf-8") as file:
                temporary = Path(file.name)
                json.dump(payload, file, ensure_ascii=False)
            temporary.replace(path)
        except OSError as error:
            record_error("搜索缓存保存失败", error)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as error:
                    record_error("搜索缓存临时文件清理失败", error)
