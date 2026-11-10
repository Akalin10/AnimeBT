"""Bangumi series context and release-title evidence used by the GUI."""

import asyncio
from dataclasses import dataclass, field
import re

import httpx

from animebt.core.matching import _normalize

from .bangumi import SEASON_MARKER, subject_summary
from .resource_match import (
    EDITION_YEAR, EPISODE_LABEL, EXPLICIT_TOTAL, MIXED_PACK, SubjectMatcher,
    episode_label, episode_title_terms, name_parts, numbers, phrase_pattern, recorded_ova_subtitle,
    release_tail, season_numbers, shared_series_names, split_parts,
)


SERIES_RELATIONS = {"前传", "续集", "主线故事", "番外篇", "衍生", "总集篇", "不同演绎"}
PARENT_RELATIONS = {"前传", "主线故事"}
SEASON_RANGE = re.compile(
    r"(?<![a-z0-9])s(?:eason\s*)?(\d{1,2})\s*[-~至]\s*(?:s(?:eason\s*)?)?(\d{1,2})(?![a-z0-9])"
    r"|第\s*(\d{1,2})\s*[-~至]\s*(\d{1,2})\s*[季期]"
)
SEASON_JOIN = re.compile(r"[\s+&、,，~至-]*[+&、,，~至-][\s+&、,，~至-]*")
PACK_WORD = re.compile(r"合集|全集|全季|全系列|\b(?:collection|batch|complete|box\s*set)\b")
OVA_MARKER = re.compile(r"(?<![a-z0-9])(?:ova|oad)(?![a-z])|(?:番外|原创动画)[篇集]")
SP_MARKER = re.compile(r"(?<![a-z0-9])(?:sp|specials?|bonus)(?![a-z])|特典|特别[篇节目]|特別[編番]")
SPECIAL_TITLE = re.compile(r"特别(?:篇|节目|编集版)|特別(?:編|番組|編集版)")
FINAL_SPLIT = re.compile(r"(?:完结[篇编]\s*|kanketsu[- ]hen\s+)(前[篇编]|后[篇编]|zenpen|kouhen)$")
SPLIT_JOIN = re.compile(r"^\s*[+&、]\s*(前[篇编]|后[篇编]|zenpen|kouhen)(?![a-z])")
MOVIE_PREFIX = re.compile(r"^剧场版\s*")
EXTRAS = re.compile(r"剧场版|电影版|总集篇|総集編|\b(?:movie|film|rebuild)\b")
WEB_MARKER = re.compile(r"\bona\b|动画短片")
MINI_MARKER = re.compile(
    r"(?<![a-z0-9])(?:q\s*版|mini[- ]*(?:anime|theat(?:er|re))|chibi[- ]*(?:anime|theat(?:er|re))|break\s*time)"
    r"|迷你动画|小剧场|泡面番|短篇动画|休息时间|休憩時間|ぷちアニメ|ちびアニメ|ミニアニメ|ちみキャラ劇場"
)
MINI_THEATER = re.compile(r"q\s*版剧场|ちみキャラ[剧劇][场場]")
NON_VIDEO = re.compile(r"\bost\b|原声(?:集|带)|漫画|\b(?:manga|soundtrack)\b")
MUSIC_RELEASE = re.compile(r"(?:op|ed)\s*(?:主題歌|主题歌|テーマ)|插入歌|挿入歌"
                           r"|\bmp3\b|(?<!\d)320\s*k(?:bps)?\b")
VIDEO_RELEASE = re.compile(r"\b(?:web[- ]?(?:rip|dl)|bd(?:rip|mv)?|bluray|mkv|mp4|hevc|avc)\b")
BONUS_ONLY = re.compile(r"片[头尾]彩蛋|(?:片[头尾]|映后)特典|(?:无字|无字幕)片[头尾]|\bnc(?:op|ed)\b")
MEMBER_JOIN = re.compile(r"^\s*[-–—]?\s*[\])}]*\s*[+&、]")
MEMBER_SEPARATOR = re.compile(r"[+&、]")
TV_MARKER = re.compile(r"\btv\b")
EXTRA_MARKERS = {"ova": OVA_MARKER, "sp": SP_MARKER, "movie": EXTRAS,
                 "web": WEB_MARKER, "mini": MINI_MARKER}


async def bangumi_json(client, path, cache, refresh):
    if not refresh and path in cache:
        return cache[path]
    try:
        response = await client.get("https://api.bgm.tv/v0/" + path, timeout=4)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    if isinstance(data, (dict, list)):
        cache[path] = data
        return data
    return None


async def load_series(client, subject, catalog, cache, refresh=False):
    """Visit the selected entry and at most two main-story/predecessor links."""
    selected_id = subject["id"]
    available = {entry["id"]: entry for entry in catalog if entry}
    known = {selected_id: subject}
    related = {}
    parents = {}
    visited = set()
    current = selected_id

    async def read_edges(entry_id):
        rows = await bangumi_json(client, f"subjects/{entry_id}/subjects", cache, refresh)
        edges = [row for row in rows or [] if isinstance(row, dict)
                 and row.get("type") == 2 and type(row.get("id")) is int
                 and row.get("relation") in SERIES_RELATIONS]
        edges.sort(key=lambda row: row["relation"] != "主线故事")
        for row in edges:
            related.setdefault(row["id"], row)
            if row["relation"] == "主线故事":
                parents[entry_id] = row["id"]
            elif row["relation"] == "番外篇":
                parents.setdefault(row["id"], entry_id)
        return edges

    try:
        async with asyncio.timeout(7):
            for _ in range(3):
                visited.add(current)
                edges = await read_edges(current)
                parent = next((row["id"] for row in edges if row["id"] not in visited
                               and row["relation"] in PARENT_RELATIONS), None)
                if parent is None:
                    break
                current = parent

            semaphore = asyncio.Semaphore(5)
            next_ids = [entry_id for entry_id, row in related.items()
                        if entry_id not in visited and row["relation"] == "续集"
                        and (work_kind(available.get(entry_id)) == "tv"
                             or season_numbers((row.get("name") or "") + " " + (row.get("name_cn") or "")))]

            async def hydrate(entry_id, row):
                entry = known.get(entry_id) or available.get(entry_id)
                if not entry or not entry.get("platform") or entry_id == selected_id and not entry.get("aliases"):
                    async with semaphore:
                        detail = await bangumi_json(client, f"subjects/{entry_id}", cache, refresh)
                    if isinstance(detail, dict):
                        entry = subject_summary(detail) or entry
                known[entry_id] = entry or subject_summary(row)

            async with asyncio.TaskGroup() as tasks:
                async def hydrate_related():
                    if next_ids:
                        await asyncio.gather(*(read_edges(entry_id) for entry_id in next_ids[:2]))
                    async with asyncio.TaskGroup() as extra:
                        for entry_id, row in list(related.items())[:16]:
                            if entry_id not in initial and entry_id != selected_id:
                                extra.create_task(hydrate(entry_id, row))

                initial = dict(list(related.items())[:16])
                if not subject.get("aliases"):
                    tasks.create_task(hydrate(selected_id, {}))
                for entry_id, row in initial.items():
                    if entry_id != selected_id:
                        tasks.create_task(hydrate(entry_id, row))
                tasks.create_task(hydrate_related())
    except TimeoutError:
        pass
    # Name-only rows are still useful for explicit mentions when metadata is unavailable.
    for entry_id, row in related.items():
        known.setdefault(entry_id, available.get(entry_id) or subject_summary(row))
    works = {entry_id: entry for entry_id, entry in known.items() if entry}
    root = works.get(parents.get(selected_id)) or works.get(current) or subject
    if work_kind(subject) == "tv" and root["id"] != selected_id and not shared_series_names(subject, [root]):
        predecessor = next((works[entry_id] for entry_id in related if entry_id in visited
                            and entry_id in works and work_kind(works[entry_id]) in {"", "tv"}
                            and shared_series_names(subject, [works[entry_id]])), None)
        if predecessor:
            root = predecessor
    return works, root, parents


def strong_names(work):
    canonical = official_names(work)
    aliases = [name for name in work.get("aliases", [])
               if len(re.sub(r"[\W_]", "", name)) >= 8]
    return {_normalize(name).strip() for name in canonical + aliases if name}


def official_names(work):
    names = [_normalize(name).strip() for name in (work["title"], work["original"]) if name]
    variants = []
    for name in names:
        if work.get("episodes") == 1 and FINAL_SPLIT.search(name):
            hybrid = re.sub(r"最终季", "the final season", name)
            for ending in ("篇", "编"):
                variants.append(re.sub(r"(?<=完结)[篇编]|(?<=[前后])[篇编]$", ending, hybrid))
        if MOVIE_PREFIX.match(name) and re.search(r"[~〜][^~〜]{4,}", name):
            short = MOVIE_PREFIX.sub("", name)
            if len(re.sub(r"[\W_]", "", short)) >= 8:
                variants.append(short)
                variants.append(re.sub(r"([前后])[篇编]", r"\1编", short))
    return names + variants


def work_kind(work):
    if not work:
        return ""
    platform = _normalize(work.get("platform", ""))
    name = _normalize(work["title"] + " " + work["original"])
    if platform in {"tv", "web", "ona", ""} and MINI_MARKER.search(name):
        return "mini"
    if platform in {"tv", "web", ""} and (SPECIAL_TITLE.search(name) or (
        work.get("episodes") == 1 and any(FINAL_SPLIT.search(_normalize(title)) for title in
                                          (work["title"], work["original"]))
    )):
        return "sp"
    if platform in {"tv", "ova", "oad", "sp", "special", "movie", "film", "剧场版", "web", "ona"}:
        return {"oad": "ova", "special": "sp", "film": "movie", "剧场版": "movie",
                "ona": "web"}.get(platform, platform)
    if OVA_MARKER.search(name):
        return "ova"
    if SP_MARKER.search(name):
        return "sp"
    if EXTRAS.search(name):
        return "movie"
    if WEB_MARKER.search(name):
        return "web"
    return ""


def distinguishing_suffixes(work, root):
    if work["id"] == root["id"]:
        return []
    suffixes = []
    for title in (work["title"], work["original"]):
        title = _normalize(title).strip()
        for base in sorted(strong_names(root), key=lambda name: (-len(name), name)):
            if title.startswith(base) and not re.match(r"[a-z0-9]", title[len(base):]):
                suffix = title[len(base):].strip(" -:()[]")
                specific = suffix
                for marker in EXTRA_MARKERS.values():
                    specific = marker.sub("", specific)
                if len(re.sub(r"[\W_]", "", specific)) >= 4 and not season_numbers(suffix):
                    suffixes.append(suffix)
                    break
    return sorted(dict.fromkeys(suffixes), key=lambda name: not name.isascii())


def bundled_seasons(title):
    title = _normalize(title)
    seasons = set()
    for match in SEASON_RANGE.finditer(title):
        first, last = (int(value) for value in match.groups() if value)
        if 0 < first < last <= 30:
            seasons.update(range(first, last + 1))
    markers = list(SEASON_MARKER.finditer(title))
    for left, right in zip(markers, markers[1:]):
        if SEASON_JOIN.fullmatch(title[left.end():right.start()]):
            seasons.update(season_numbers(title[left.start():right.end()]))
    for block in re.findall(r"\[([^\]]*\+[^\]]*)\]", title):
        for label in block.split("+"):
            if SEASON_MARKER.match(label.lstrip()) and not re.search(r"new edit|新编集版", label):
                seasons.update(season_numbers(label))
    return seasons if len(seasons) > 1 else set()


def adjacent_seasons(tail):
    clause = tail.lstrip(" \t])}[(")
    if match := SEASON_RANGE.match(clause):
        return bundled_seasons(match[0])
    first = SEASON_MARKER.match(clause)
    if not first:
        return set()
    end = first.end()
    while join := SEASON_JOIN.match(clause, end):
        following = SEASON_MARKER.match(clause, join.end())
        if not following:
            break
        end = following.end()
    return bundled_seasons(clause[:end])


def cumulative_range(title):
    return numbers(EXPLICIT_TOTAL.search(_normalize(title))) if "总" in title or "總" in title else range(0)


@dataclass(frozen=True)
class Attribution:
    work_ids: frozenset[int]
    bundle: bool = False
    rejection: str = field(default="", compare=False)

    def category(self, subject_id):
        if subject_id in self.work_ids:
            return "合集资源" if self.bundle else "独立资源"
        return ""


def merge_attributions(evidence):
    """Use the most specific listing for a hash, unless its mirrors disagree."""
    confirmed = [item for item in evidence if item.work_ids]
    if not confirmed:
        return Attribution(frozenset())
    strongest = max(confirmed, key=lambda item: (len(item.work_ids), item.bundle))
    if any(not item.work_ids <= strongest.work_ids for item in confirmed):
        return Attribution(frozenset())
    return strongest


class SeriesMatcher:
    def __init__(self, subject, works, root, episodes, catalog=()):
        self.subject = subject
        self.works = works
        self.root = root
        strict_context = {entry["id"]: entry for entry in catalog}
        strict_context.update(works)
        self.context = strict_context
        owners = {}
        official = {}
        separated_names = {}
        split_parts_by_stem = {}
        mini_subtitles = {}
        self.seasons = {}
        self.kinds = {}
        self.bases = {}
        for entry_id, work in works.items():
            self.kinds[entry_id] = work_kind(work)
            names = work["title"] + " / " + work["original"]
            aliases = work.get("aliases", [])
            self.seasons[entry_id] = season_numbers(names)
            if not self.seasons[entry_id]:
                inferred = season_numbers(" / ".join(aliases))
                if len(inferred) == 1:
                    self.seasons[entry_id] = inferred
            self.bases[entry_id] = {name_parts(name)[0] for name in (work["title"], work["original"]) if name}
            self.bases[entry_id].update(name_parts(alias)[0] for alias in aliases if season_numbers(alias))
        for entry_id, work in strict_context.items():
            for name in strong_names(work):
                owners.setdefault(name, set()).add(entry_id)
            for name in official_names(work):
                official.setdefault(name, set()).add(entry_id)
                if entry_id in works and work.get("episodes") == 1 and (part := FINAL_SPLIT.search(name)):
                    stem = name[:part.start(1)].rstrip()
                    side = 1 if part[1] in {"前篇", "前编", "zenpen"} else 2
                    split_parts_by_stem.setdefault(stem, {}).setdefault(side, set()).add(entry_id)
                if entry_id != root["id"] and (theater := MINI_THEATER.search(name)):
                    subtitle = name[theater.end():].strip()
                    if len(re.sub(r"[\W_]", "", subtitle)) >= 6:
                        mini_subtitles.setdefault(subtitle, set()).add(entry_id)
            kind = self.kinds.get(entry_id)
            if kind in EXTRA_MARKERS:
                root_names = strong_names(root)
                marker = EXTRA_MARKERS[kind]
                for alias in strong_names(work):
                    if marker.search(alias) and marker.sub("", alias).strip(" -:()[]") not in root_names:
                        official.setdefault(alias, set()).add(entry_id)
                for suffix in distinguishing_suffixes(work, root):
                    for base in root_names:
                        name = f"{base} {suffix}"
                        owners.setdefault(name, set()).add(entry_id)
                        official.setdefault(name, set()).add(entry_id)
                        format_labels = {"ova": "ova|oad", "sp": "sp|special|bonus"}.get(kind)
                        if format_labels and (base_pattern := phrase_pattern(base)) and (
                            suffix_pattern := phrase_pattern(suffix)
                        ):
                            # A release may put its type and episode in separate brackets
                            # between a verified series name and the work's unique subtitle.
                            gap = rf"[\W_]+(?:{format_labels})[\W_]+(?:\d{{1,3}}[\W_]+)?"
                            pattern = re.compile(base_pattern.pattern + gap + suffix_pattern.pattern)
                            separated_names.setdefault(pattern, set()).add(entry_id)
        self.names = [(pattern, ids, official.get(name, set())) for name, ids in owners.items()
                      if (pattern := phrase_pattern(name))]
        self.names.extend((pattern, ids, ids) for pattern, ids in separated_names.items())
        self.ova_subtitles = []
        for entry_id, work in works.items():
            if self.kinds[entry_id] != "ova":
                continue
            stem, subtitle = recorded_ova_subtitle(work)
            subtitle = _normalize(subtitle)
            # Both canonical names record the subtitle even when the relation
            # endpoint fails. A bare series name still proves nothing.
            if subtitle and not any(
                subtitle in name for other_id, other in strict_context.items()
                if other_id != entry_id for name in strong_names(other)
            ):
                self.ova_subtitles.append((entry_id, phrase_pattern(_normalize(stem)), phrase_pattern(subtitle)))
        self.mini_subtitles = [(phrase_pattern(name), entry_id) for name, ids in mini_subtitles.items()
                               if len(ids) == 1 for entry_id in ids if entry_id in works]
        self.root_title_patterns = [phrase_pattern(name) for name in strong_names(root)]
        self.split_pairs = []
        for stem, sides in split_parts_by_stem.items():
            if len(sides.get(1, ())) == len(sides.get(2, ())) == 1 and sides[1] != sides[2]:
                self.split_pairs.append((phrase_pattern(stem), sides))
        self.tv_matchers = {
            entry_id: SubjectMatcher(work, strict_context.values(), episodes if entry_id == subject["id"] else [])
            for entry_id, work in works.items() if self.kinds[entry_id] == "tv"
            or (entry_id == subject["id"] and not self.kinds[entry_id] and not work.get("platform")
                and (self.seasons[entry_id] or episodes))
        }
        self.plain_predecessors = {
            entry_id: {
                other_id for other_id, work in works.items()
                if self.kinds[other_id] in {"", "tv"} and not self.seasons[other_id]
                and any(_normalize(name) in self.bases[entry_id] for name in (work["title"], work["original"]) if name)
            }
            for entry_id in self.tv_matchers if self.seasons[entry_id]
        }
        self.cache = {}
        self.schedules = {}
        self.episode_names = []
        self.add_subject_episodes(episodes)

    def add_subject_episodes(self, episodes):
        if not episodes:
            return
        entry_id = self.subject["id"]
        if entry_id in self.tv_matchers:
            self.tv_matchers[entry_id].add_episode_dates(episodes)
        elif not self.kinds[entry_id] and not self.subject.get("platform"):
            self.tv_matchers[entry_id] = SubjectMatcher(self.subject, self.context.values(), episodes)
        self.episode_names = [pattern for name in episode_title_terms(episodes)
                              if (pattern := phrase_pattern(_normalize(name)))]
        self.add_schedule(entry_id, episodes)

    def add_schedule(self, entry_id, episodes):
        if episodes:
            self.schedules.setdefault(entry_id, set()).update(
                row["sort"] for row in episodes if isinstance(row.get("sort"), (int, float))
            )
            self.cache.clear()

    def season_works(self, seasons):
        root_id = self.root["id"]
        return {
            entry_id for entry_id, bases in self.bases.items()
            if self.kinds[entry_id] == "tv" and self.bases[root_id].intersection(bases)
            and (self.seasons[entry_id] or ({1} if entry_id == root_id else set())).intersection(seasons)
        }

    def _cumulative_owners(self, total, seasons):
        if len(total) < 2 or not seasons:
            return set()
        owners = set()
        choices = self.season_works(seasons)
        if not choices or not choices <= self.schedules.keys():
            return set()
        for number in total:
            matches = {entry_id for entry_id in choices if number in self.schedules[entry_id]}
            if len(matches) != 1:
                return set()
            owners.update(matches)
        return owners

    def classify(self, resource):
        key = (resource.title, resource.publish_time)
        if key not in self.cache:
            self.cache[key] = self._classify(resource)
        return self.cache[key]

    def _mentions(self, title):
        hits = [(match.start(), match.end(), ids, official) for pattern, ids, official in self.names
                for match in pattern.finditer(title)]
        hits.sort(key=lambda hit: (hit[0], -hit[1]))
        longest = []
        for start, end, ids, official in hits:
            if longest and start < longest[-1][1]:
                if start == longest[-1][0] and end == longest[-1][1]:
                    longest[-1][2].update(ids)
                    longest[-1][3].update(official)
                continue
            longest.append((start, end, set(ids), set(official)))
        return longest

    def _classify(self, resource):
        title = _normalize(resource.title)
        if (NON_VIDEO.search(title) or MUSIC_RELEASE.search(title)) and not (
            resource.metadata.resolution or VIDEO_RELEASE.search(title)
        ):
            return Attribution(frozenset(), rejection="非视频发布")

        local = numbers(EPISODE_LABEL.fullmatch(episode_label(resource)))
        total = numbers(EXPLICIT_TOTAL.search(title))
        season_markers = season_numbers(title)
        mixed = any(pattern.search(title) for pattern in (
            OVA_MARKER, SP_MARKER, EXTRAS, WEB_MARKER, MINI_MARKER, MIXED_PACK, NON_VIDEO,
        ))
        mentions = self._mentions(title)
        confirmed = set()
        video = bool(resource.metadata.resolution or VIDEO_RELEASE.search(title))
        if video and not BONUS_ONLY.search(title):
            for entry_id, stem, subtitle in self.ova_subtitles:
                count = self.works[entry_id].get("episodes", 0)
                if (season_markers or any(pattern.search(title) for pattern in
                                          (EXTRAS, SP_MARKER, WEB_MARKER, MINI_MARKER, NON_VIDEO))
                        or count and local and local.stop - 1 > count
                        or any(official and entry_id not in ids for _, _, ids, official in mentions)):
                    continue
                if any(stem.search(title[:match.start()]) for match in subtitle.finditer(title)):
                    confirmed.add(entry_id)
            for subtitle, entry_id in self.mini_subtitles:
                for match in subtitle.finditer(title):
                    prefix = title[:match.start()]
                    if (SP_MARKER.search(prefix) and any(pattern and pattern.search(prefix)
                                                        for pattern in self.root_title_patterns)
                            and release_tail(title[match.end():].lstrip(" _"))):
                        confirmed.add(entry_id)
                        break
            for stem, sides in self.split_pairs:
                for match in stem.finditer(title):
                    ending = re.match(r"\s*(前[篇编]|后[篇编]|zenpen|kouhen)", title[match.end():])
                    if not ending or not (joined := SPLIT_JOIN.match(title[match.end() + ending.end():])):
                        continue
                    first = ending[1].startswith(("前", "zen"))
                    second = joined[1].startswith(("前", "zen"))
                    if first != second:
                        confirmed.update(sides[1] | sides[2])
        seen_tv = {}
        for index, (start, end, ids, official) in enumerate(mentions):
            if len(ids) != 1:
                continue
            entry_id, = ids
            if entry_id not in self.works:
                continue
            next_start = mentions[index + 1][0] if index + 1 < len(mentions) else len(title)
            tail = title[end:next_start]
            kind = self.kinds[entry_id]
            episode_named = entry_id == self.subject["id"] and any(
                pattern.search(tail) for pattern in self.episode_names
            )
            bilingual_title = video and re.match(r"^[\s\])}」』~〜]*/", tail)
            video_suffix = video and re.match(
                r"^[\s\[\](){}「」『』~〜-]*(?:sp\d+\b|生肉|无字幕|baha\b|b-global\b|cr\b|nhk\b)", tail
            )
            if not (release_tail(tail.lstrip("~〜")) or MEMBER_JOIN.match(tail) or episode_named
                    or entry_id in official and (bilingual_title or video_suffix)):
                continue
            if entry_id in self.tv_matchers:
                seen_tv.setdefault(entry_id, []).append(tail)
            elif entry_id in official:
                # Exact extra titles stand on their own. A TV season or a different
                # format attached to the same member is contradictory evidence.
                member_tail = re.split(r"\s+[+&]\s+", tail, maxsplit=1)[0]
                work = self.works[entry_id]
                allowed_formats = {kind}
                if MINI_MARKER.search(_normalize(work["title"] + " " + work["original"])):
                    allowed_formats.add("mini")
                other_format = any(label not in allowed_formats and pattern.search(member_tail)
                                   for label, pattern in {**EXTRA_MARKERS, "tv": TV_MARKER}.items())
                if kind == "movie" and BONUS_ONLY.search(member_tail):
                    other_format = True
                episode_count = self.works[entry_id].get("episodes", 0)
                wrong_episode = (type(episode_count) is int and episode_count > 0
                                 and local and local.stop - 1 > episode_count
                                 and not MEMBER_JOIN.match(tail) and len(mentions) == 1)
                neighbors = mentions[max(0, index - 1):index] + mentions[index + 1:index + 2]
                ambiguous_join = any(
                    other_official and entry_id not in other_ids and not MEMBER_SEPARATOR.search(
                        title[other_end:start] if other_end <= start else title[end:other_start]
                    )
                    for other_start, other_end, other_ids, other_official in neighbors
                )
                root_names = self.bases[self.root["id"]]
                generic_ova = kind == "ova" and entry_id != self.root["id"] and any(
                    OVA_MARKER.sub("", _normalize(name)).strip(" -()[]") in root_names
                    for name in (self.works[entry_id]["title"], self.works[entry_id]["original"]) if name
                )
                complete_ova = (type(episode_count) is int and episode_count > 1
                                and local == range(1, episode_count + 1)
                                and not any(other_id != entry_id and self.kinds[other_id] == "ova"
                                            and work.get("episodes") == episode_count
                                            for other_id, work in self.works.items()))
                if not (other_format or wrong_episode or season_numbers(member_tail) or ambiguous_join
                        or generic_ova and not (episode_named or complete_ova)):
                    confirmed.add(entry_id)

        root_id = self.root["id"]
        season_pack = set().union(*(adjacent_seasons(tail) for tail in seen_tv.get(root_id, ())))
        if season_pack and not split_parts(title):
            if total:
                confirmed.update(self._cumulative_owners(total, season_pack))
            elif not local:
                for season in season_pack:
                    owners = self.season_works({season})
                    if len(owners) == 1:
                        confirmed.update(owners)
        elif total and len(season_markers) == 1 and not mixed and root_id in seen_tv:
            # The count still needs episode-to-work schedules, even with a season label.
            if any(season_numbers(tail) == season_markers and EXPLICIT_TOTAL.search(tail)
                   for tail in seen_tv[root_id]):
                confirmed.update(self._cumulative_owners(total, season_markers))

        # Ordinary TV releases keep the established episode and broadcast checks.
        # Unqualified series names and ambiguous aliases cannot identify an extra.
        if not mixed and not season_pack:
            for entry_id, matcher in self.tv_matchers.items():
                generic_predecessors = (self.plain_predecessors.get(entry_id, set())
                                        if season_markers == self.seasons[entry_id] else set())
                if any(entry_id not in ids and official and
                       not (ids == {root_id} and self.bases[entry_id].intersection(self.bases[root_id])
                            or ids <= generic_predecessors)
                       for _, _, ids, official in mentions):
                    continue
                identical = set().union(*(official for _, _, _, official in mentions if entry_id in official))
                if len(identical) > 1:
                    year = self.works[entry_id].get("date", "")[:4]
                    if not year or set(EDITION_YEAR.findall(title)) != {year} or any(
                        other != entry_id and (self.context[other].get("date", "")[:4] in {"", year})
                        for other in identical
                    ):
                        continue
                if matcher.matches(resource):
                    confirmed.add(entry_id)

        # A named extra can accompany a complete TV range. Require an explicit
        # season or an unambiguous TV entry, rather than inferring from pack words.
        if mixed and confirmed and not season_pack:
            for entry_id, tails in seen_tv.items():
                count = self.works[entry_id].get("episodes", 0)
                seasons = self.seasons[entry_id] or ({1} if entry_id == root_id else set())
                related_tv = {other for other in self.kinds if other != entry_id and self.kinds[other] == "tv"
                              and self.bases[entry_id].intersection(self.bases[other])}
                shared = any((self.seasons[other] or ({1} if other == root_id else set())) == seasons
                             for other in related_tv)
                own_seasons = set().union(*(season_numbers(tail) for tail in tails)) | self.seasons[entry_id]
                if (type(count) is int and count > 1 and local == range(1, count + 1) and not shared
                        and not split_parts(title)
                        and (own_seasons == seasons if own_seasons else not related_tv)):
                    confirmed.add(entry_id)

        bundle = bool(PACK_WORD.search(title) or season_pack or len(local) > 1 or len(total) > 1
                      or len(confirmed) > 1)
        rejection = ""
        if not confirmed:
            if not mentions:
                rejection = "标题缺少可验证作品名"
            elif season_markers and self.seasons[self.subject["id"]] and not (
                season_markers & self.seasons[self.subject["id"]]
            ):
                rejection = "季度标记与目标冲突"
            elif total or season_pack:
                rejection = "累计集数或合集成员证据不足"
            elif mixed:
                rejection = "特殊篇、剧场版或混合集合证据不足"
            else:
                rejection = "作品名歧义或缺少分段、集数及日期证据"
        return Attribution(frozenset(confirmed), bundle, rejection)
