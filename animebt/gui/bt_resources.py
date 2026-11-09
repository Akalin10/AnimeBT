"""Bridge the GUI to the existing asyncio BT search service."""

import asyncio
from collections import Counter
from dataclasses import replace
from hashlib import sha256
import re
from threading import Event

import httpx
from PySide6.QtCore import QObject, Property, QRunnable, QThreadPool, Qt, Signal, Slot

from animebt.config import Settings
from animebt.core.dedupe import deduplicate
from animebt.core.results import display_date, filter_sort
from animebt.core.runtime import record_error
from animebt.core.search import SearchService
from animebt.sources import SOURCE_TYPES
from animebt.sources.foreign_anime import EXTRA_SOURCE_TYPES

from .resource_match import episode_label, search_names, season_numbers, supplementary_names
from .resource_actions import ResourceActions, valid_magnet
from .source_settings import DEFAULT_TIMEOUTS
from .series_resources import (
    SeriesMatcher, bundled_seasons, cumulative_range, distinguishing_suffixes, load_series, merge_attributions, work_kind,
)
from .title_spans import parse_display_title


SOURCE_BUDGET_SECONDS = 28
CATALOG_WORKERS = 2


class _Confirmed(Exception):
    def __init__(self, rows):
        self.rows = rows


def subtitle_queries(subject, kind):
    if kind not in {"movie", "ova", "mini", "sp"}:
        return []
    names = [subject["title"], subject["original"]]
    queries = []
    for name in names:
        parts = re.split(r"[!！~～〜]", name)
        if len(parts) > 1:
            suffix = next((part.strip() for part in reversed(parts[1:]) if part.strip()), "")
            if len(re.sub(r"[\W_]", "", suffix)) >= 4:
                queries.append(suffix)
    return list(dict.fromkeys(queries))


async def subject_episodes(client, subject_id):
    rows = []
    try:
        for _ in range(5):
            response = await client.get(
                "https://api.bgm.tv/v0/episodes",
                params={"subject_id": subject_id, "type": 0, "limit": 100, "offset": len(rows)},
                timeout=8,
            )
            response.raise_for_status()
            data = response.json()
            page = data["data"]
            if not isinstance(page, list) or not all(isinstance(row, dict) for row in page):
                break
            rows.extend(page)
            if not page or len(rows) >= data["total"]:
                break
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        pass
    return rows


def resource_rows(resources, matcher=None):
    by_hash = {}
    if matcher:
        for resource in resources:
            if resource.info_hash:
                by_hash.setdefault(resource.info_hash, []).append((resource, matcher.classify(resource)))
    rows = []
    for resource in filter_sort(deduplicate(resources)):
        if matcher and resource.info_hash:
            mirrors = by_hash[resource.info_hash]
            attribution = merge_attributions(evidence for _, evidence in mirrors)
            if attribution.category(matcher.subject["id"]):
                # Keep merged links and sources, but show a title that actually proved the match.
                proof = next(item for item, evidence in mirrors if evidence == attribution)
                resource = replace(resource, title=proof.title)
        else:
            attribution = matcher.classify(resource) if matcher else None
        category = attribution.category(matcher.subject["id"]) if attribution else "独立资源"
        if not category:
            continue
        work_ids = sorted(attribution.work_ids) if attribution else []
        names = ()
        if matcher:
            relevant = {*work_ids, matcher.subject["id"], matcher.root["id"]}
            names = tuple(sorted({
                name for entry_id in relevant for work in (matcher.works[entry_id],)
                for name in (work["title"], work["original"], *work.get("aliases", []))
                if len(name) >= (2 if name in (work["title"], work["original"]) else 4)
            }))
        spans, ambiguous = parse_display_title(resource.title, names)
        rows.append({
            "key": resource.info_hash or sha256(
                repr((resource.title, resource.torrent_url, resource.magnet, resource.size, resource.source)).encode("utf-8")
            ).hexdigest(),
            "title": resource.title,
            "titleSpans": [span.as_dict() for span in spans],
            "titleAmbiguous": ambiguous,
            "episode": episode_label(resource),
            "resolution": resource.metadata.resolution or "未知",
            "fansub": resource.metadata.fansub or "未知",
            "size": resource.display_size,
            "date": display_date(resource.publish_time),
            "sources": " / ".join(resource.sources),
            "magnet": resource.magnet or "",
            "torrent_url": resource.torrent_url or "",
            "info_hash": resource.info_hash or "",
            "category": category,
            "work_ids": work_ids,
            "works": [matcher.works[entry_id]["title"] for entry_id in work_ids],
        })
    return rows


async def collect_resources(service, subject, siblings, update, refresh=False, episode_cache=None,
                            series_cache=None, *, first_match=False):
    terms = search_names(subject)
    kind = work_kind(subject)
    supplemental = kind in {"ova", "sp", "mini", "web"} or bool(
        subject.get("platform") and kind not in {"tv", "movie"}
    )
    written_names = supplementary_names(subject, ())
    subtitle_terms = subtitle_queries(subject, kind)
    candidates_by_source = {}
    status_by_source = {}

    async def load_episodes():
        subject_id = subject["id"]
        if not refresh and episode_cache is not None and subject_id in episode_cache:
            rows = episode_cache[subject_id]
        else:
            rows = await subject_episodes(service.client, subject_id)
            if rows and episode_cache is not None:
                episode_cache[subject_id] = rows
        return rows

    async def load_matcher():
        (works, root, _), rows = await asyncio.gather(
            load_series(service.client, subject, siblings, series_cache if series_cache is not None else {}, refresh),
            load_episodes(),
        )
        return SeriesMatcher(subject, works, root, rows, siblings), rows

    matching = asyncio.create_task(load_matcher())
    schedule_jobs = {}

    async def add_ranges(matcher, candidates):
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
                async with asyncio.timeout(5):
                    rows = await subject_episodes(service.client, entry_id)
                if rows and episode_cache is not None:
                    episode_cache[entry_id] = rows
            matcher.add_schedule(entry_id, rows)

        for entry_id in needed:
            if entry_id not in schedule_jobs and len(schedule_jobs) < 4:
                schedule_jobs[entry_id] = asyncio.create_task(add_schedule(entry_id))
        if needed:
            await asyncio.shield(asyncio.gather(
                *(schedule_jobs[entry_id] for entry_id in needed if entry_id in schedule_jobs),
                return_exceptions=True,
            ))

    async def run_source(name):
        extended_source = name in DEFAULT_TIMEOUTS
        tried = []
        candidates = []
        status, error = "无结果", ""
        try:
            async with asyncio.timeout(SOURCE_BUDGET_SECONDS):
                use_written = kind == "movie" or (extended_source and supplemental)
                initial = written_names if use_written and written_names else terms
                for keyword in initial[:1]:
                    tried.append(keyword)
                    result = await service.search(keyword, selected=[name], refresh=refresh)
                    candidates.extend(result.resources)
                    status = result.statuses.get(name, "无结果")
                    error = result.errors.get(name, "")
                matcher, episodes = await asyncio.shield(matching)
                await add_ranges(matcher, candidates)
                check_first(candidates, matcher)
                root_terms = search_names(matcher.root)
                root_keyword = root_terms[0] if root_terms else ""
                if supplemental:
                    chapter_terms = [name for name in supplementary_names(subject, episodes) if name not in written_names]
                    suffixes = distinguishing_suffixes(subject, matcher.root)
                    fallback = [*written_names[:2], *subtitle_terms, *suffixes[:1], *chapter_terms[:1],
                                *written_names[2:3], root_keyword, *suffixes[1:], *written_names[3:], *root_terms[1:]]
                elif kind == "movie":
                    fallback = [*subtitle_terms, *written_names, *terms, root_keyword, *root_terms[1:]]
                else:
                    fallback = [root_keyword, *terms[1:], *root_terms[1:]]
                unique = dict.fromkeys(word for word in fallback if word and word not in tried)
                fallback = list(unique)
                for keyword in fallback[:5 if supplemental else 3]:
                    if error:
                        break
                    if not supplemental and keyword != root_keyword and resource_rows(candidates, matcher):
                        break
                    tried.append(keyword)
                    result = await service.search(keyword, selected=[name], refresh=refresh)
                    candidates.extend(result.resources)
                    await add_ranges(matcher, result.resources)
                    check_first(candidates, matcher)
                    status = result.statuses.get(name, "无结果")
                    error = result.errors.get(name, "")
        except _Confirmed:
            raise
        except TimeoutError:
            status, error = "超时", "名称补查超过时间上限"
        except Exception as exc:
            record_error(f"GUI 来源搜索失败 [{name}]", exc)
            status, error = "失败", "来源返回的资源无法处理"
        matcher, schedule = await asyncio.shield(matching)
        candidates_by_source[name] = candidates
        status_by_source[name] = {
            "name": name,
            "status": status,
            "error": error,
            "keywords": " / ".join(tried),
        }
        rows = resource_rows([item for group in candidates_by_source.values() for item in group], matcher)
        counts = Counter(source for row in rows for source in row["sources"].split(" / "))
        statuses = {}
        for source, state in status_by_source.items():
            count = counts[source]
            if state["error"]:
                status = "部分结果" if count else "超时" if state["status"] == "超时" else "失败"
            else:
                status = "成功" if count else "无结果"
            statuses[source] = dict(state, count=count, status=status)
        update(rows, statuses, bool(schedule))

    def check_first(candidates, matcher):
        if first_match:
            rows = [row for row in resource_rows(candidates, matcher)
                    if valid_magnet(row["magnet"], row["info_hash"])
                    or row["torrent_url"].startswith(("https://", "http://"))]
            if rows:
                raise _Confirmed(rows)

    proof = []
    try:
        async with asyncio.TaskGroup() as tasks:
            for source in service.sources:
                tasks.create_task(run_source(source.name))
    except* _Confirmed as confirmed:
        proof = confirmed.exceptions[0].rows
    finally:
        if not matching.done():
            matching.cancel()
        for job in schedule_jobs.values():
            if not job.done():
                job.cancel()
        await asyncio.gather(matching, *schedule_jobs.values(), return_exceptions=True)
    return proof


class _CatalogSearchService(SearchService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._queries = {}
        self._waiters = Counter()

    async def search(self, keyword, selected=None, refresh=False):
        key = keyword, tuple(selected or ())
        if key not in self._queries:
            self._queries[key] = asyncio.create_task(super().search(keyword, selected, refresh))
        task = self._queries[key]
        self._waiters[key] += 1
        try:
            return await asyncio.shield(task)
        finally:
            self._waiters[key] -= 1
            if not self._waiters[key]:
                del self._waiters[key]
                del self._queries[key]
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
                 generation, progress, finished):
        super().__init__()
        self.directory = directory
        self.subjects = subjects
        self.episode_cache = episode_cache
        self.series_cache = series_cache
        self.extra_timeouts = extra_timeouts
        self.generation = generation
        self.progress = progress
        self.finished = finished
        self.cancelled = Event()

    async def search(self):
        settings = Settings()
        settings.sources.extend(self.extra_timeouts)
        service = _CatalogSearchService(settings, self.directory, source_types=[*SOURCE_TYPES, *EXTRA_SOURCE_TYPES],
                                        source_timeouts=self.extra_timeouts)
        remaining = iter(self.subjects)

        async def worker():
            for subject in remaining:
                if self.cancelled.is_set():
                    return
                statuses = {}

                def update(_rows, states, _schedule):
                    statuses.update(states)

                try:
                    proof = await collect_resources(
                        service, subject, self.subjects, update, episode_cache=self.episode_cache,
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
                 extra_timeouts):
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
        self.cancelled = Event()

    async def search(self):
        settings = Settings()
        settings.sources.extend(self.extra_timeouts)
        service = SearchService(settings, self.directory, source_types=[*SOURCE_TYPES, *EXTRA_SOURCE_TYPES],
                                source_timeouts=self.extra_timeouts)
        try:
            task = asyncio.create_task(collect_resources(
                service, self.subject, self.siblings,
                lambda *values: self.progress.emit(self.generation, values), self.refresh,
                self.episode_cache, self.series_cache,
            ))
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


class BTResources(QObject):
    changed = Signal()
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
        self._catalog_proofs = {}
        self._catalog_checked = 0
        self._catalog_incomplete = 0
        self._catalog_cancelled = False
        self._job = None
        self._generation = 0
        self._active = False
        self._loading = False
        self._rows = []
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
        return [subject for subject in self._catalog_subjects if subject["id"] in self._catalog_proofs]

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
        self._catalog_subjects = subjects
        self._catalog_proofs = {}
        self._catalog_checked = self._catalog_incomplete = 0
        self._catalog_cancelled = False
        if subjects:
            self._catalog_job = CatalogJob(
                self._directory, subjects, self._episode_cache, self._series_cache, self._extra_timeouts,
                self._catalog_generation, self._catalogProgress, self._catalogFinished,
            )
            self._catalog_pool.start(self._catalog_job)
        self.catalogResultsChanged.emit()
        self.catalogChanged.emit()

    @Slot(int, object)
    def _receive_catalog_progress(self, generation, update):
        if generation != self._catalog_generation:
            return
        subject_id, proof, incomplete = update
        self._catalog_checked += 1
        self._catalog_incomplete += incomplete
        if proof:
            self._catalog_proofs[subject_id] = proof
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

    @Property("QVariantMap", notify=changed)
    def subject(self):
        return self._subject

    @Property("QVariantList", notify=changed)
    def rows(self):
        return self._rows

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
        if not subject.get("id"):
            return
        self._subject = subject
        self._siblings = siblings
        self._start()

    @Slot()
    def refresh(self):
        if self._active:
            self._start(refresh=True)

    def _start(self, refresh=False):
        self._cancel_job()
        self._actions.cancelCopy()
        self._active = True
        self._loading = True
        self._rows = [] if refresh else self._catalog_proofs.get(self._subject["id"], [])
        names = [source.name for source in SOURCE_TYPES] + list(self._extra_timeouts)
        self._sources = [{"name": name, "status": "搜索中", "error": "",
                          "count": 0, "keywords": ""} for name in names]
        self._error = ""
        self._schedule = True
        self._job = SearchJob(self._directory, self._subject, self._siblings, refresh,
                              self._episode_cache, self._series_cache, self._generation, self._progress, self._finished,
                              self._extra_timeouts)
        self.changed.emit()
        self._pool.start(self._job)

    def _cancel_job(self):
        self._generation += 1
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
        self._rows, statuses, self._schedule = update
        self._sources = [statuses.get(source["name"], source) for source in self._sources]
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
