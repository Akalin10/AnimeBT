"""Bridge the GUI to the existing asyncio BT search service."""

import asyncio
from collections import Counter, deque
from dataclasses import replace
import re
from threading import Event, Lock

import httpx
from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, Property, QRunnable, QThreadPool, Qt, Signal, Slot

from animebt.config import Settings
from animebt.core.dedupe import deduplicate
from animebt.core.results import publication_date
from animebt.core.runtime import logger, record_error
from animebt.core.search import SearchService
from animebt.sources import SOURCE_TYPES
from animebt.sources.foreign_anime import EXTRA_SOURCE_TYPES

from .resource_match import (
    episode_label, search_names, season_numbers, supplementary_names,
)
from .resource_actions import ResourceActions, valid_magnet
from .resource_list import ResourceFilterModel, ResourceListModel
from .source_settings import DEFAULT_TIMEOUTS
from .series_resources import (
    SeriesMatcher, bundled_seasons, cumulative_range, load_series, merge_attributions, work_kind,
)
from .search_plan import plan_queries
from .resource_rows import resource_rows
from .keyword_search import collect_keyword_resources


SOURCE_BUDGET_SECONDS = 28
CATALOG_WORKERS = 3
DETAIL_UPDATE_INTERVAL = 0.1


class _Confirmed(Exception):
    def __init__(self, rows):
        self.rows = rows


async def fetch_episode_page(client, subject_id, offset, limit=100):
    reason = "invalid response"
    for _ in range(2):
        try:
            response = await client.get(
                "https://api.bgm.tv/v0/episodes",
                params={"subject_id": subject_id, "type": 0, "limit": limit, "offset": offset},
                timeout=6,
            )
            response.raise_for_status()
            data = response.json()
            page, total = data["data"], data["total"]
            if isinstance(total, int) and isinstance(page, list) and all(isinstance(row, dict) for row in page):
                return page, total
            break
        except httpx.HTTPStatusError as error:
            reason = f"HTTP {error.response.status_code}"
            if error.response.status_code < 500:
                break
        except httpx.RequestError as error:
            reason = type(error).__name__
            continue
        except (ValueError, KeyError, TypeError):
            break
    logger.info("Bangumi episodes unavailable subject=%s offset=%s limit=%s reason=%s",
                subject_id, offset, limit, reason)
    return None


async def subject_episodes(client, subject_id, cache=None):
    if subject_id < 0:
        return []
    initial = await fetch_episode_page(client, subject_id, 0)
    if initial is None:
        return []
    first, total = initial
    if not first:
        return []
    page_size = len(first)
    offsets = set(range(page_size, min(total, page_size * 5), page_size))
    # Long-running shows still need real broadcast dates for recent releases.
    last = (total - 1) // page_size * page_size
    if last >= page_size * 5:
        offsets.update((last - page_size, last))
    pages = await asyncio.gather(*(fetch_episode_page(client, subject_id, offset) for offset in sorted(offsets)))
    rows = first + [row for page in pages if page is not None for row in page[0]]
    if cache is not None and all(page is not None for page in pages):
        cache[subject_id] = rows
    return rows


async def collect_resources(service, subject, siblings, update, refresh=False, episode_cache=None,
                            series_cache=None, *, first_match=False):
    terms = search_names(subject)
    kind = work_kind(subject)
    supplemental = kind in {"ova", "sp", "mini", "web"} or bool(
        subject.get("platform") and kind not in {"tv", "movie"}
    )
    candidates_by_source = {}
    status_by_source = {}
    final_counts = Counter()
    final_states = {}
    preview_pages = asyncio.Queue()
    detail_dirty = asyncio.Event()
    episode_rows = []

    async def load_episodes():
        subject_id = subject["id"]
        if not refresh and episode_cache is not None and subject_id in episode_cache:
            rows = episode_cache[subject_id]
        else:
            rows = await subject_episodes(service.client, subject_id, episode_cache)
        return rows

    async def load_matcher():
        works, root, _ = await load_series(
            service.client, subject, siblings, series_cache if series_cache is not None else {}, refresh,
        )
        matcher = SeriesMatcher(works[subject["id"]], works, root, [], siblings)
        if tv := matcher.tv_matchers.get(subject["id"]):
            tv.schedule_pending = True
        return matcher

    matching = asyncio.create_task(load_matcher())
    schedule_jobs = {}
    targeted_jobs = {}

    async def load_schedule():
        rows = await load_episodes()
        matcher = await asyncio.shield(matching)
        episode_rows.extend(rows)
        matcher.add_subject_episodes(rows)
        if tv := matcher.tv_matchers.get(subject["id"]):
            tv.schedule_pending = False
        matcher.cache.clear()
        request_publish(matcher)

    def add_targeted_episodes(matcher, candidates):
        subject_id = subject["id"]
        if subject.get("provider") == "anilist":
            return
        tv = matcher.tv_matchers.get(subject_id)
        if tv is None or tv.seasons:
            return
        offsets = set()
        for item in candidates:
            number = episode_label(item)
            if (number.isdecimal() and 500 < int(number) <= 9999 and not tv.by_local.get(int(number))
                    and publication_date(item.publish_time)):
                offsets.add((int(number) - 1) // 20 * 20)

        async def fill(offset):
            page = await fetch_episode_page(service.client, subject_id, offset, limit=20)
            if page:
                tv.add_episode_dates(page[0])
                matcher.add_schedule(subject_id, page[0])
                preview_pages.put_nowait((None, ()))

        for offset in sorted(offsets, reverse=True):
            if offset not in targeted_jobs and len(targeted_jobs) < 2:
                targeted_jobs[offset] = asyncio.create_task(fill(offset))

    def add_ranges(matcher, candidates):
        seasons = set()
        for item in candidates:
            if len(cumulative_range(item.title)) > 1:
                seasons.update(bundled_seasons(item.title) or season_numbers(item.title))
        if not seasons:
            return
        needed = sorted(matcher.season_works(seasons) - matcher.schedules.keys())[:4]

        async def add_schedule(entry_id):
            rows = episode_cache.get(entry_id) if not refresh and episode_cache is not None else None
            if rows is None:
                try:
                    async with asyncio.timeout(5):
                        rows = await subject_episodes(service.client, entry_id, episode_cache)
                except TimeoutError:
                    return
            matcher.add_schedule(entry_id, rows)
            preview_pages.put_nowait((None, ()))

        for entry_id in needed:
            if entry_id not in schedule_jobs and len(schedule_jobs) < 4:
                schedule_jobs[entry_id] = asyncio.create_task(add_schedule(entry_id))

    def remember(name, items, matcher):
        stored = candidates_by_source.setdefault(name, {})
        previous_count = len(stored)
        for item in items:
            key = (item.info_hash, item.title, item.size, item.publish_time, item.magnet, item.torrent_url)
            if previous := stored.get(key):
                origins = [list(origin) for origin in dict.fromkeys(map(tuple, previous.origins + item.origins))]
                if origins != previous.origins:
                    stored[key] = replace(previous, origins=origins)
            else:
                stored[key] = item
        if len(stored) != previous_count:
            request_publish(matcher)
            add_targeted_episodes(matcher, items)
            add_ranges(matcher, items)

    async def run_source(source):
        name = source.name
        tried = []
        attempts = []
        errors = []
        limited = []
        status, error = "无结果", ""

        async def query(keyword):
            tried.append(keyword)
            try:
                result = await service.search(keyword, selected=[name], refresh=refresh,
                                              collect=True, page_budget=12 if refresh else 4 if first_match else 6,
                                              on_page=lambda page: preview_pages.put_nowait((name, page)))
            except asyncio.CancelledError:
                logger.info("BT query interrupted subject=%s source=%s keyword=%r", subject["id"], name, keyword)
                raise
            items = result.candidates or result.resources
            attempts.append((keyword, result, items))
            if reason := result.errors.get(name):
                errors.append(reason)
            if reason := result.incomplete.get(name):
                limited.append(reason)
            matcher = await asyncio.shield(matching)
            remember(name, items, matcher)
            return result.statuses.get(name, "无结果"), result.errors.get(name, "")

        query_tasks = []
        try:
            async with asyncio.timeout(60 if refresh else SOURCE_BUDGET_SECONDS):
                initial = subject["title"] or next(iter(terms), "")
                if initial:
                    query_tasks.append(asyncio.create_task(query(initial)))
                matcher = await asyncio.shield(matching)
                budget = 11 if refresh else 6
                planned = plan_queries(source, matcher, episode_rows, kind, initial=initial, budget=budget + 1)
                if len(planned) > budget:
                    limited.append("达到别名预算")
                aliases = iter(planned[:budget])

                def blocked():
                    return any(reason.startswith(("HTTP 401,", "HTTP 429,")) for reason in errors)

                async def run_aliases():
                    nonlocal status, error
                    for keyword in aliases:
                        if blocked():
                            break
                        status, error = await query(keyword)

                # The preferred query starts with metadata loading. A second lane can
                # make progress while that query pages or waits on a slow connection.
                query_tasks.append(asyncio.create_task(run_aliases()))
                if initial:
                    status, error = await query_tasks[0]
                query_tasks.append(asyncio.create_task(run_aliases()))
                await asyncio.gather(*query_tasks)
                if supplemental and len(tried) <= budget and not blocked():
                    await asyncio.shield(schedule)
                    written = supplementary_names(matcher.subject, ())
                    chapter = next((name for name in supplementary_names(matcher.subject, episode_rows)
                                    if name not in written and name.casefold() not in {word.casefold() for word in tried}), None)
                    if chapter:
                        status, error = await query(chapter)
        except _Confirmed:
            raise
        except TimeoutError:
            status, error = "超时", "名称补查超过时间上限"
            errors.append(error)
        except Exception as exc:
            record_error(f"GUI 来源搜索失败 [{name}]", exc)
            status, error = "失败", "来源返回的资源无法处理"
            errors.append(error)
        finally:
            for task in query_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*query_tasks, return_exceptions=True)
            matcher = matching.result() if matching.done() and not matching.cancelled() and not matching.exception() else None
            for keyword, result, items in attempts:
                accepted = [item for item in items if matcher and matcher.classify(item).category(subject["id"])]
                logger.info(
                    "BT query subject=%s source=%s keyword=%r raw=%s candidates=%s matched=%s dedup=%s eligible=%s status=%s error=%r",
                    subject["id"], name, keyword, result.raw_counts.get(name, "unknown"), result.counts.get(name, 0),
                    len(accepted) if matcher else "unknown", len(deduplicate(accepted)) if matcher else "unknown",
                    result.eligible_counts.get(name, "unknown"), result.statuses.get(name), result.errors.get(name, ""),
                )
            if errors:
                logger.info("BT source errors subject=%s source=%s status=%s reasons=%r",
                            subject["id"], name, status, list(dict.fromkeys(errors)))
        matcher = await asyncio.shield(matching)
        status_by_source[name] = {
            "name": name,
            "status": status,
            "error": "；".join(dict.fromkeys(errors)),
            "keywords": " / ".join(tried),
            "limited": "；".join(dict.fromkeys(limited)),
            "raw": sum(result.raw_counts.get(name, 0) for _, result, _ in attempts),
        }
        if first_match:
            update([], {name: dict(status_by_source[name], error=status_by_source[name]["error"] or
                                   status_by_source[name]["limited"])}, bool(episode_rows))
            return
        request_publish(matcher)

    def request_publish(matcher):
        if first_match:
            publish(matcher)
        else:
            detail_dirty.set()

    async def publish_details():
        matcher = await asyncio.shield(matching)
        while True:
            await detail_dirty.wait()
            detail_dirty.clear()
            publish(matcher)
            await asyncio.sleep(DETAIL_UPDATE_INTERVAL)

    def publish(matcher):
        candidates = [item for group in candidates_by_source.values() for item in group.values()]
        if first_match:
            check_first(candidates, matcher)
            return
        rows = resource_rows(candidates, matcher)
        counts = Counter(source for row in rows for source in row["sources"].split(" / "))
        final_counts.clear()
        final_counts.update(counts)
        statuses = {}
        for source in candidates_by_source.keys() | status_by_source.keys():
            state = status_by_source.get(source)
            count = counts[source]
            if state is None:
                statuses[source] = {"name": source, "count": count, "status": "搜索中", "error": "", "keywords": ""}
                continue
            if state["error"]:
                status = ("部分结果" if count else "搜索未完成"
                          if state["status"] == "超时" or candidates_by_source.get(source) else "来源失败")
            elif state["limited"]:
                status = "部分结果" if count else "检索范围有限"
            elif count:
                status = "成功"
            else:
                status = ("归属未确认" if candidates_by_source.get(source)
                          else "已查范围无确认资源" if state["raw"] else "来源返回零条")
            statuses[source] = dict(state, count=count, status=status)
            final_states[source] = status
        update(rows, statuses, bool(episode_rows))

    def check_first(candidates, matcher):
        if first_match and any(matcher.classify(item).category(subject["id"]) for item in candidates):
            rows = [row for row in resource_rows(candidates, matcher)
                    if valid_magnet(row["magnet"], row["info_hash"])
                    or row["torrent_url"].startswith(("https://", "http://"))]
            if rows:
                raise _Confirmed(rows)

    async def check_pages():
        matcher = await asyncio.shield(matching)
        while True:
            name, page = await preview_pages.get()
            if name is None:
                request_publish(matcher)
            else:
                remember(name, page, matcher)

    async def run_sources(preview, detail_updates):
        async with asyncio.TaskGroup() as tasks:
            for source in service.sources:
                tasks.create_task(run_source(source))
        preview.cancel()
        await schedule
        await asyncio.gather(*schedule_jobs.values(), *targeted_jobs.values())
        if detail_updates is not None:
            detail_updates.cancel()
        publish(await asyncio.shield(matching))

    proof = []
    try:
        async with asyncio.TaskGroup() as tasks:
            schedule = tasks.create_task(load_schedule())
            preview = tasks.create_task(check_pages())
            detail_updates = None if first_match else tasks.create_task(publish_details())
            tasks.create_task(run_sources(preview, detail_updates))
    except* _Confirmed as confirmed:
        signal = confirmed
        while isinstance(signal, BaseExceptionGroup):
            signal = signal.exceptions[0]
        proof = signal.rows
    finally:
        if not matching.done():
            matching.cancel()
        metadata_jobs = (*schedule_jobs.values(), *targeted_jobs.values())
        for job in metadata_jobs:
            if not job.done():
                job.cancel()
        await asyncio.gather(matching, *metadata_jobs, return_exceptions=True)
    if first_match:
        for source in service.sources:
            state = status_by_source.get(source.name)
            logger.info("BT catalog final subject=%s source=%s status=%s limits=%r error=%r",
                        subject["id"], source.name, state["status"] if state else "确认存在后结束其余核验",
                        state["limited"] if state else None, state["error"] if state else None)
    else:
        matcher = matching.result()
        all_hits = [item for group in candidates_by_source.values() for item in group.values()]
        hashes = {}
        for item in all_hits:
            if item.info_hash:
                hashes.setdefault(item.info_hash, []).append(matcher.classify(item))
        conflicts = {key for key, evidence in hashes.items()
                     if any(item.work_ids for item in evidence) and not merge_attributions(evidence).work_ids}
        for name, state in status_by_source.items():
            accepted = 0
            rejected = Counter()
            for item in candidates_by_source.get(name, {}).values():
                evidence = matcher.classify(item)
                if item.info_hash in conflicts:
                    rejected["同一 Info Hash 的镜像归属冲突"] += 1
                elif subject["id"] in evidence.work_ids:
                    accepted += 1
                else:
                    rejected["已证实属于其他作品" if evidence.work_ids else evidence.rejection] += 1
            logger.info("BT source final subject=%s source=%s keywords=%r accepted=%s rejected=%r dedup=%s "
                        "status=%s limits=%r error=%r", subject["id"], name, state["keywords"],
                        accepted, dict(rejected), final_counts[name], final_states[name], state["limited"], state["error"])
    return proof


class _CatalogSearchService(SearchService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._queries = {}
        self._waiters = Counter()
        self._page_listeners = {}
        self._received_pages = {}

    async def search(self, keyword, selected=None, refresh=False, *, on_page=None, **options):
        key = keyword, tuple(selected or ()), refresh, tuple(sorted(options.items()))

        def publish_page(page):
            self._received_pages[key].append(page)
            for listener in self._page_listeners[key]:
                listener(page)

        if key not in self._queries:
            self._page_listeners[key] = set()
            self._received_pages[key] = []
            self._queries[key] = asyncio.create_task(super().search(keyword, selected, refresh, on_page=publish_page, **options))
        task = self._queries[key]
        self._waiters[key] += 1
        try:
            if on_page is not None:
                self._page_listeners[key].add(on_page)
                for page in self._received_pages[key]:
                    on_page(page)
            return await asyncio.shield(task)
        finally:
            self._page_listeners[key].discard(on_page)
            self._waiters[key] -= 1
            if not self._waiters[key]:
                del self._waiters[key]
                del self._queries[key]
                del self._received_pages[key]
                del self._page_listeners[key]
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

    async def close(self):
        for query in self._queries.values():
            if not query.done():
                query.cancel()
        await asyncio.gather(*self._queries.values(), return_exceptions=True)
        await super().close()


class CatalogJob(QRunnable):
    def __init__(self, directory, subjects, episode_cache, series_cache, extra_timeouts,
                 generation, progress, finished, *, complete=True):
        super().__init__()
        self.directory = directory
        self._subjects = list(subjects)
        self._remaining = deque(subjects)
        self._complete = complete
        self._lock = Lock()
        self.episode_cache = episode_cache
        self.series_cache = series_cache
        self.extra_timeouts = extra_timeouts
        self.generation = generation
        self.progress = progress
        self.finished = finished
        self.cancelled = Event()

    def extend(self, subjects, complete):
        with self._lock:
            self._subjects.extend(subjects)
            self._remaining.extend(subjects)
            self._complete = complete

    async def search(self):
        settings = Settings()
        settings.sources.extend(self.extra_timeouts)
        service = _CatalogSearchService(settings, self.directory, source_types=[*SOURCE_TYPES, *EXTRA_SOURCE_TYPES],
                                        source_timeouts=self.extra_timeouts)
        async def worker():
            while not self.cancelled.is_set():
                with self._lock:
                    subject = self._remaining.popleft() if self._remaining else None
                    complete = self._complete
                    siblings = tuple(self._subjects) if subject else ()
                if subject is None:
                    if complete:
                        return
                    await asyncio.sleep(0.05)
                    continue
                statuses = {}

                def update(_rows, states, _schedule):
                    statuses.update(states)

                try:
                    proof = await collect_resources(
                        service, subject, siblings, update, episode_cache=self.episode_cache,
                        series_cache=self.series_cache, first_match=True,
                    )
                    incomplete = not proof and any(state["error"] for state in statuses.values())
                except Exception as error:
                    record_error("GUI 作品资源核验失败", error)
                    proof, incomplete = [], True
                if not self.cancelled.is_set():
                    self.progress.emit(self.generation, (subject["id"], proof, incomplete))

        workers = [asyncio.create_task(worker()) for _ in range(CATALOG_WORKERS)]
        try:
            while not self.cancelled.is_set() and not all(task.done() for task in workers):
                await asyncio.wait(workers, timeout=0.1)
        finally:
            for task in workers:
                task.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            await service.close()

    def run(self):
        if not self.cancelled.is_set():
            try:
                asyncio.run(self.search())
            except Exception as error:
                record_error("GUI 作品资源核验失败", error)
            if not self.cancelled.is_set():
                self.finished.emit(self.generation)


class SearchJob(QRunnable):
    def __init__(self, directory, subject, siblings, refresh, episode_cache, series_cache, generation, progress, finished,
                 extra_timeouts, keyword=None):
        super().__init__()
        self.directory = directory
        self.subject = subject
        self.siblings = siblings
        self.refresh = refresh
        self.episode_cache = episode_cache
        self.series_cache = series_cache
        self.generation = generation
        self.progress = progress
        self.finished = finished
        self.extra_timeouts = extra_timeouts
        self.keyword = keyword
        self.cancelled = Event()

    async def search(self):
        settings = Settings()
        settings.sources.extend(self.extra_timeouts)
        service = SearchService(settings, self.directory, source_types=[*SOURCE_TYPES, *EXTRA_SOURCE_TYPES],
                                source_timeouts=self.extra_timeouts)
        try:
            update = lambda *values: self.progress.emit(self.generation, values)
            search = (collect_keyword_resources(service, self.keyword, update, self.refresh)
                      if self.keyword is not None else collect_resources(
                          service, self.subject, self.siblings, update, self.refresh,
                          self.episode_cache, self.series_cache))
            task = asyncio.create_task(search)
            while not task.done() and not self.cancelled.is_set():
                await asyncio.wait({task}, timeout=0.1)
            if self.cancelled.is_set():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            else:
                await task
        finally:
            await service.close()

    def run(self):
        if self.cancelled.is_set():
            return
        error = ""
        try:
            asyncio.run(self.search())
        except Exception as exc:
            record_error("GUI BT 搜索失败", exc)
            error = "资源搜索未能完成，请稍后重试。"
        if not self.cancelled.is_set():
            self.finished.emit(self.generation, error)


class CatalogPosterModel(QAbstractListModel):
    countChanged = Signal()
    subject_role = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent):
        super().__init__(parent)
        self.subjects = []

    @Property(int, notify=countChanged)
    def count(self):
        return len(self.subjects)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.subjects)

    def roleNames(self):
        return {self.subject_role: b"subject"}

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == self.subject_role and 0 <= index.row() < len(self.subjects):
            return self.subjects[index.row()]
        return None

    def append(self, subject):
        row = len(self.subjects)
        self.beginInsertRows(QModelIndex(), row, row)
        self.subjects.append(subject)
        self.endInsertRows()
        self.countChanged.emit()

    def clear(self):
        if self.subjects:
            self.beginResetModel()
            self.subjects.clear()
            self.endResetModel()
            self.countChanged.emit()


class BTResources(QObject):
    changed = Signal()
    facetsChanged = Signal()
    catalogChanged = Signal()
    catalogResultsChanged = Signal()
    _catalogProgress = Signal(int, object)
    _catalogFinished = Signal(int)
    _progress = Signal(int, object)
    _finished = Signal(int, str)

    def __init__(self, directory, parent=None, *, extra_timeouts=None):
        super().__init__(parent)
        self._directory = directory
        self._extra_timeouts = DEFAULT_TIMEOUTS.copy() if extra_timeouts is None else extra_timeouts.copy()
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._catalog_pool = QThreadPool(self)
        self._catalog_pool.setMaxThreadCount(1)
        self._catalog_job = None
        self._catalog_generation = 0
        self._catalog_subjects = []
        self._catalog_by_id = {}
        self._catalog_model = CatalogPosterModel(self)
        self._catalog_proofs = {}
        self._catalog_checked = 0
        self._catalog_incomplete = 0
        self._catalog_cancelled = False
        self._job = None
        self._generation = 0
        self._active = False
        self._loading = False
        self._list_mode = False
        self._keyword = ""
        self._cancelled = False
        self._resource_list = ResourceListModel(self)
        self._filtered_resources = ResourceFilterModel(self._resource_list, self)
        self._facets = {"total": 0, "categories": {}, "season": [], "episode": [], "resolution": [], "fansub": []}
        self._season_rows = []
        self._season_assistant = None
        self._sources = []
        self._error = ""
        self._schedule = True
        self._subject = {}
        self._siblings = []
        self._episode_cache = {}
        self._series_cache = {}
        self._actions = ResourceActions(self)
        self._progress.connect(self._receive_progress, Qt.ConnectionType.QueuedConnection)
        self._finished.connect(self._receive_finished, Qt.ConnectionType.QueuedConnection)
        self._catalogProgress.connect(self._receive_catalog_progress, Qt.ConnectionType.QueuedConnection)
        self._catalogFinished.connect(self._receive_catalog_finished, Qt.ConnectionType.QueuedConnection)

    @Property("QVariantList", notify=catalogResultsChanged)
    def catalogResults(self):
        return list(self._catalog_model.subjects)

    @Property(QObject, constant=True)
    def catalogModel(self):
        return self._catalog_model

    @Property(bool, notify=catalogChanged)
    def catalogChecking(self):
        return self._catalog_job is not None

    @Property(int, notify=catalogChanged)
    def catalogChecked(self):
        return self._catalog_checked

    @Property(int, notify=catalogChanged)
    def catalogIncomplete(self):
        return self._catalog_incomplete

    @Property(bool, notify=catalogChanged)
    def catalogCancelled(self):
        return self._catalog_cancelled

    @Slot()
    def cancelCatalog(self):
        self._catalog_generation += 1
        if self._catalog_job is not None:
            self._catalog_job.cancelled.set()
            self._catalog_job = None
            self._catalog_cancelled = True
            self.catalogChanged.emit()

    @Slot("QVariantList")
    def verifyCatalog(self, subjects):
        self.cancelCatalog()
        self._catalog_subjects = []
        self._catalog_by_id = {}
        self._catalog_proofs = {}
        self._catalog_model.clear()
        self._catalog_checked = self._catalog_incomplete = 0
        self._catalog_cancelled = False
        self.extendCatalog(subjects, True)
        self.catalogResultsChanged.emit()
        self.catalogChanged.emit()

    @Slot("QVariantList", bool)
    def extendCatalog(self, subjects, complete):
        if self._list_mode:
            return
        added = []
        for subject in subjects:
            if subject["id"] not in self._catalog_by_id:
                self._catalog_by_id[subject["id"]] = subject
                added.append(subject)
        self._catalog_subjects.extend(added)
        if self._catalog_job is not None:
            self._catalog_job.extend(added, complete)
        elif added:
            self._catalog_job = CatalogJob(
                self._directory, added, self._episode_cache, self._series_cache, self._extra_timeouts,
                self._catalog_generation, self._catalogProgress, self._catalogFinished, complete=complete,
            )
            self._catalog_pool.start(self._catalog_job)
            self.catalogChanged.emit()

    @Slot(int, object)
    def _receive_catalog_progress(self, generation, update):
        if generation != self._catalog_generation:
            return
        subject_id, proof, incomplete = update
        self._catalog_checked += 1
        self._catalog_incomplete += incomplete
        if proof and subject_id not in self._catalog_proofs and subject_id in self._catalog_by_id:
            self._catalog_proofs[subject_id] = proof
            self._catalog_model.append(self._catalog_by_id[subject_id])
            self.catalogResultsChanged.emit()
        self.catalogChanged.emit()

    @Slot(int)
    def _receive_catalog_finished(self, generation):
        if generation == self._catalog_generation:
            self._catalog_job = None
            self._catalog_incomplete += len(self._catalog_subjects) - self._catalog_checked
            self.catalogChanged.emit()

    @Property(bool, notify=changed)
    def active(self):
        return self._active

    @Property(QObject, constant=True)
    def actions(self):
        return self._actions

    @Property(bool, notify=changed)
    def loading(self):
        return self._loading

    @Property(bool, notify=changed)
    def listMode(self):
        return self._list_mode

    @Property(str, notify=changed)
    def keyword(self):
        return self._keyword

    @Property(str, notify=changed)
    def emptyMessage(self):
        if self._cancelled:
            return "已取消搜索"
        if self._error:
            return self._error
        errors = [state for state in self._sources if state.get("error")]
        limited = any(state.get("limited") for state in self._sources)
        if errors:
            return ("部分来源搜索超时，暂未找到匹配资源"
                    if any(state["status"] == "超时" for state in errors)
                    else "部分来源访问失败，暂未找到匹配资源")
        if limited:
            return "已查范围内未找到匹配资源，部分来源检索范围受限"
        return "未找到匹配的 BT 资源" if self._list_mode else "未找到该作品的 BT 资源"

    @Property("QVariantMap", notify=changed)
    def subject(self):
        return self._subject

    @Property(QObject, constant=True)
    def resourceModel(self):
        return self._filtered_resources

    @Property("QVariantMap", notify=facetsChanged)
    def facets(self):
        return self._facets

    def _update_rows(self, rows):
        if self._season_rows == rows:
            return
        self._season_rows = list(rows)
        self._refresh_seasons()

    @Slot(QObject)
    def attachTitleAssistant(self, assistant):
        if self._season_assistant is not None:
            return
        from .season_assistant import SeasonAssistant
        self._season_assistant = SeasonAssistant(assistant, self)
        self._season_assistant.resultsChanged.connect(self._refresh_seasons)
        self._refresh_seasons()

    def _refresh_seasons(self):
        from .resource_seasons import known_seasons, season_labels
        rows = [dict(row, seasons=season_labels(self._season_assistant.resolve(row)
                                               if self._season_assistant else known_seasons(row)))
                for row in self._season_rows]
        self._resource_list.update_rows(rows)
        facets = {"total": len(rows), "categories": dict(Counter(row["category"] for row in rows))}
        labels = {label for row in rows for label in row["seasons"]}
        facets["season"] = sorted(labels, key=lambda label: (label == "未知", label))
        for key in ("episode", "resolution", "fansub"):
            facets[key] = sorted({row[key] for row in rows})
        if self._facets != facets:
            self._facets = facets
            self.facetsChanged.emit()

    @Property("QVariantList", notify=changed)
    def sources(self):
        return self._sources

    @Property(str, notify=changed)
    def error(self):
        return self._error

    @Property(bool, notify=changed)
    def scheduleAvailable(self):
        return self._schedule

    @Slot("QVariantMap", "QVariantList")
    def openSubject(self, subject, siblings):
        if self._list_mode or not subject.get("id"):
            return
        self._subject = subject
        self._siblings = siblings
        self._start()

    @Slot(bool)
    def setListMode(self, enabled):
        if self._list_mode == enabled:
            return
        self.closePage()
        self.verifyCatalog([])
        self._list_mode = enabled
        self._keyword = ""
        self._subject = {}
        self._siblings = []
        self._sources = []
        self._error = ""
        self._cancelled = False
        self._update_rows([])
        self._filtered_resources.setFilters("", "", "", "")
        self._filtered_resources.setSeasonFilter("")
        self.changed.emit()

    @Slot(str)
    def searchKeyword(self, keyword):
        keyword = keyword.strip()
        if not self._list_mode or not keyword or (self._loading and keyword == self._keyword):
            return
        self._keyword = keyword
        self._subject = {}
        self._start()

    @Slot()
    def cancelSearch(self):
        if self._loading:
            self._cancel_job()
            self._loading = False
            self._cancelled = True
            self._sources = [dict(source, status="已取消") if source["status"] == "搜索中" else source
                             for source in self._sources]
            self.changed.emit()

    @Slot()
    def refresh(self):
        if self._active:
            self._start(refresh=True)

    def _start(self, refresh=False):
        self._cancel_job()
        self._actions.cancelCopy()
        self._active = True
        self._loading = True
        self._cancelled = False
        self._update_rows([] if self._list_mode or refresh else self._catalog_proofs.get(self._subject["id"], []))
        names = [source.name for source in SOURCE_TYPES] + list(self._extra_timeouts)
        self._sources = [{"name": name, "status": "搜索中", "error": "",
                          "count": 0, "keywords": ""} for name in names]
        self._error = ""
        self._schedule = True
        self._job = SearchJob(self._directory, self._subject, self._siblings, refresh,
                              self._episode_cache, self._series_cache, self._generation, self._progress, self._finished,
                              self._extra_timeouts, self._keyword if self._list_mode else None)
        self.changed.emit()
        self._pool.start(self._job)

    def _cancel_job(self):
        self._generation += 1
        if self._season_assistant:
            self._season_assistant.cancel()
        if self._job is not None:
            self._job.cancelled.set()
            self._job = None

    @Slot()
    def closePage(self):
        self._cancel_job()
        self._actions.cancelCopy()
        if self._active:
            self._active = False
            self._loading = False
            self.changed.emit()

    @Slot(int, object)
    def _receive_progress(self, generation, update):
        if generation != self._generation:
            return
        rows, statuses, schedule = update
        self._update_rows(rows)
        sources = [statuses.get(source["name"], source) for source in self._sources]
        if self._sources != sources or self._schedule != schedule:
            self._sources = sources
            self._schedule = schedule
            self.changed.emit()

    @Slot(int, str)
    def _receive_finished(self, generation, error):
        if generation != self._generation:
            return
        self._job = None
        self._loading = False
        self._error = error
        if error:
            self._sources = [
                dict(source, status="失败", error=error) if source["status"] == "搜索中" else source
                for source in self._sources
            ]
        self.changed.emit()

    def shutdown(self):
        self.cancelCatalog()
        self.closePage()
        self._actions.shutdown()
        self._pool.waitForDone()
        self._catalog_pool.waitForDone()
