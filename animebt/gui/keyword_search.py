"""Keyword retrieval without subject lookup or ownership inference."""

import asyncio
from collections import Counter
from dataclasses import replace

from animebt.core.matching import _normalize, title_matches
from animebt.core.runtime import logger

from .resource_match import traditional_name
from .resource_rows import resource_rows
from .search_plan import _key, _variants


def keyword_queries(keyword):
    names = [keyword.strip()]
    names.extend(_variants(keyword, minimum_cjk=2))
    for name in list(names):
        if not any("ぁ" <= char <= "ヿ" for char in name):
            names.extend((traditional_name(name), _normalize(name)))
    seen = set()
    queries = []
    for name in names:
        key = _key(name)
        if key and key not in seen:
            queries.append(name)
            seen.add(key)
    return queries[:6]


async def collect_keyword_resources(service, keyword, update, refresh=False):
    queries = keyword_queries(keyword)
    candidates = {}
    states = {source.name: {"name": source.name, "status": "搜索中", "error": "",
                           "count": 0, "keywords": "", "raw": 0} for source in service.sources}
    dirty = asyncio.Event()

    def remember(name, query, items):
        for item in items:
            if not title_matches(item.title, query):
                continue
            key = (name, item.info_hash, item.title, item.size, item.publish_time,
                   item.magnet, item.torrent_url, item.source_id)
            previous = candidates.get(key)
            if previous:
                origins = [list(origin) for origin in dict.fromkeys(map(tuple, previous.origins + item.origins))]
                item = replace(item, origins=origins)
            candidates[key] = item
        dirty.set()

    def publish():
        rows = resource_rows(list(candidates.values()))
        counts = Counter(source for row in rows for source in row["sources"].split(" / "))
        update(rows, {name: dict(state, count=counts[name]) for name, state in states.items()}, False)
        return rows

    async def stream_updates():
        while True:
            await dirty.wait()
            dirty.clear()
            publish()
            await asyncio.sleep(0.1)

    async def run_source(source):
        name = source.name
        errors, limits, tried = [], [], []
        raw = 0
        timed_out = False
        try:
            async with asyncio.timeout(60 if refresh else 28):
                for query in queries:
                    tried.append(query)
                    result = await service.search(
                        query, selected=[name], refresh=refresh, collect=True,
                        page_budget=12 if refresh else 6,
                        on_page=lambda page, query=query: remember(name, query, page),
                    )
                    items = result.candidates or result.resources
                    remember(name, query, items)
                    raw += result.raw_counts.get(name, 0)
                    if reason := result.errors.get(name):
                        errors.append(reason)
                        timed_out |= result.statuses.get(name) == "超时"
                    if reason := result.incomplete.get(name):
                        limits.append(reason)
                    logger.info(
                        "BT keyword source=%s query=%r raw=%s candidates=%s matched=%s status=%s limits=%r error=%r",
                        name, query, result.raw_counts.get(name), len(items),
                        sum(title_matches(item.title, query) for item in items),
                        result.statuses.get(name), result.incomplete.get(name), result.errors.get(name),
                    )
                    if any(reason.startswith(("HTTP 401", "HTTP 403", "HTTP 429")) for reason in errors):
                        break
        except TimeoutError:
            errors.append("关键词补查超过时间上限")
            timed_out = True
        count = sum(key[0] == name for key in candidates)
        if errors:
            status = "部分结果" if count else "超时" if timed_out else "来源失败"
        elif limits:
            status = "部分结果" if count else "检索范围有限"
        else:
            status = "成功" if count else "关键词无匹配" if raw else "来源返回零条"
        states[name] = {"name": name, "status": status, "error": "；".join(dict.fromkeys(errors)),
                        "limited": "；".join(dict.fromkeys(limits)), "keywords": " / ".join(tried),
                        "raw": raw, "count": count}
        logger.info("BT keyword final source=%s queries=%r raw=%s matched=%s status=%s limits=%r errors=%r",
                    name, tried, raw, count, status, limits, errors)
        dirty.set()

    async with asyncio.TaskGroup() as tasks:
        publisher = tasks.create_task(stream_updates())

        async def run_sources():
            async with asyncio.TaskGroup() as sources:
                for source in service.sources:
                    sources.create_task(run_source(source))
            publisher.cancel()

        tasks.create_task(run_sources())
    return publish()
