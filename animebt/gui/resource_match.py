"""Conservative attribution of BT release titles to a selected Bangumi subject."""

from datetime import date, timedelta
import re
import unicodedata
from opencc import OpenCC

from animebt.core.matching import _normalize
from animebt.core.results import publication_date

from .bangumi import SEASON_MARKER


EXPLICIT_TOTAL = re.compile(r"总\s*第?\s*(\d{1,4})(?:\s*[-~～]\s*(\d{1,4}))?(?![a-z0-9])")
SEASON_EPISODE = re.compile(r"\bs\d+e(\d{1,4})(?:\s*[-~]\s*e?(\d{1,4}))?", re.IGNORECASE)
EPISODE_LABEL = re.compile(r"(\d{1,4})(?:\s*[-~～]\s*(\d{1,4}))?\Z")
COMPLETE_COUNT = re.compile(r"全\s*(\d{1,3})\s*[集话話]")
BARE_RANGE = re.compile(r"(?<!\w)(0?1)\s*[-~～]\s*(\d{1,3})(?=\s|[\])}]|全集|$)")
LONG_EPISODE = re.compile(r"(?:第\s*(\d{1,4})(?:\s*[-~]\s*(\d{1,4}))?\s*[集话]|"
                          r"\s[-–—]\s+(1\d{3})(?=\s*[\[(]|\s*$))")
RELEASE_TAIL = re.compile(
    r"^(?:$|[-–—~]\s*\d|第\s*\d{1,4}(?:\s*[-~]\s*\d{1,4})?\s*[集话]|(?:第\s*)?\d{1,3}(?![a-z\d])"
    r"|(?:e|ep)\s*\d|总\s*第?\s*\d|全\s*\d"
    r"|web[- ]?(?:rip|dl)|bd(?:rip|mv)?\b|blu[- ]?ray|tv\b|\d{3,4}[pi]\b|[248]k\b"
    r"|(?:hevc|avc|x26[45]|h\.?26[45]|av1|aac|flac|mkv|mp4|chs|cht)\b"
    r"|(?:简繁|简体|繁体|简日|繁日|双语|内封|内嵌|中日)|合集|全集|初版"
    r"|(?:complete|collection|batch|box\s*set)\b|\(?(?:19|20)\d{2}\)?)"
)
EDITIONS = re.compile(r"\b(?:ova|oad|break\s*time)\b|新编集版|特别篇|小剧场|休息时间|休憩時間|剧场版|劇場版")
MIXED_PACK = re.compile(
    r"\b(?:movies?\d*|film|ona|ost|rebuild)\b|剧场版|劇場版|特别放映|特別興行|动画短片"
)
EDITION_YEAR = re.compile(r"\((19\d{2}|20\d{2})\)")
FIRST_PART = re.compile(r"前半|上半|前编|第\s*[一1]\s*(?:部分|クール)|\b(?:part|cour)\s*1\b")
SECOND_PART = re.compile(r"后半|下半|后编|第\s*[二2]\s*(?:部分|クール)|\b(?:part|cour)\s*2\b")
CHINESE_DIGITS = dict(zip("零一二三四五六七八九", range(10)))
CHINESE_DIGITS["〇"] = 0
_to_traditional = OpenCC("s2t")


def season_numbers(title):
    numbers = set()
    for match in SEASON_MARKER.finditer(_normalize(title)):
        label = next(group for group in match.groups() if group)
        if label.isdecimal():
            numbers.add(int(label))
        elif "十" in label:
            tens, units = label.split("十", 1)
            numbers.add(10 * CHINESE_DIGITS.get(tens, 1) + CHINESE_DIGITS.get(units, 0))
        elif label in CHINESE_DIGITS:
            numbers.add(CHINESE_DIGITS[label])
    return numbers


def name_parts(title):
    text = _normalize(title)
    season = SEASON_MARKER.search(text)
    if season:
        return text[:season.start()].strip(" -:（(["), text[season.end():].strip(" -:）)]")
    return re.sub(r"\s*\(\d{4}\)\s*$", "", text).strip(), ""


def split_parts(title):
    return {number for number, pattern in enumerate((FIRST_PART, SECOND_PART), 1) if pattern.search(title)}


def search_names(subject):
    # Use the displayed Chinese and original names first, plus one existing Latin alias.
    primary = _normalize(subject["title"]).strip()
    names = [primary]
    if season := SEASON_MARKER.search(primary):
        names.append(primary[:season.end()])
    names.extend(name_parts(name)[0] for name in (primary, subject["original"]))
    english = [alias for alias in subject.get("aliases", [])
               if re.search(r"[a-z]{3}", alias, re.I) and _normalize(alias).isascii()]
    if english:
        names.append(max((name_parts(alias)[0] for alias in english), key=len))
    return list(dict.fromkeys(filter(None, names)))


def episode_title_terms(episodes):
    names = []
    for row in episodes:
        for name in (row.get("name_cn"), row.get("name")):
            if isinstance(name, str):
                title = re.split(r"[―—]", re.sub(r"^#\S+\s*", "", name))[0].strip()
                if len(re.sub(r"[\W_]", "", title)) >= 6:
                    names.append(title)
    return list(dict.fromkeys(names))


def supplementary_names(subject, episodes):
    """Search written aliases and chapter titles without normalizing Japanese script on the server."""
    names = [subject["title"], subject["original"], *subject.get("aliases", [])]
    names.extend(episode_title_terms(episodes))
    queries = [re.sub(r"[\W_]+", " ", unicodedata.normalize("NFKC", name)).strip() for name in names]
    return list(dict.fromkeys(query for query in queries if len(query.replace(" ", "")) >= 4))


def shared_series_names(subject, related):
    """Find native-script stems shared by two verified series entries."""
    stems = set()
    for title in (subject["title"], subject["original"]):
        for entry in related:
            for other in (entry["title"], entry["original"]):
                title_words, other_words = title.split(), other.split()
                shared = []
                for left, right in zip(title_words, other_words):
                    if _normalize(left) != _normalize(right):
                        break
                    shared.append(left)
                if shared and len("".join(shared)) >= 4:
                    stems.add(" ".join(shared))
    return sorted(stems, key=lambda name: (not subject["title"].startswith(name), -len(name), name))


def traditional_name(name):
    return _to_traditional.convert(name) if not re.search(r"[ぁ-ヿ]", name) else name


def recorded_ova_subtitle(subject):
    """Read a shared Latin subtitle from the two canonical names of an OVA."""
    title = subject["title"]
    match = re.fullmatch(r"([^\x00-\x7f]+) ([A-Za-z]{3,}(?: [A-Za-z]{3,})+)", title)
    if match and (subtitle := phrase_pattern(_normalize(match[2]))) and subtitle.search(_normalize(subject["original"])):
        return match[1], match[2]
    return "", ""


def phrase_pattern(text):
    words = re.findall(r"[^\W_]+", text)
    if not words:
        return None
    return re.compile(r"(?<![^\W_])" + r"[\W_]*".join(map(re.escape, words)) + r"(?![a-z])")


def release_tail(tail):
    """Recognize a release suffix, without treating every bracket as metadata."""
    tail = tail.lstrip(" \t])}」』")
    tail = re.sub(r"^[-–—]\s*(?=$|[\[(/+])", "", tail)
    tail = tail.lstrip(" \t[({「『")
    return bool(RELEASE_TAIL.match(tail) or SEASON_MARKER.match(tail))


def episode_label(resource):
    title = _normalize(resource.title)
    if match := SEASON_EPISODE.search(title):
        return "-".join(group for group in match.groups() if group)
    if resource.metadata.episode:
        return resource.metadata.episode
    if match := EXPLICIT_TOTAL.search(title):
        return "总第" + "-".join(group for group in match.groups() if group)
    if match := COMPLETE_COUNT.search(title):
        return f"01-{match[1]}"
    if match := LONG_EPISODE.search(title):
        return "-".join(group for group in match.groups() if group)
    if match := BARE_RANGE.search(title):
        return f"{match[1]}-{match[2]}"
    return "未知"


def numbers(match):
    if not match:
        return range(0)
    start, end = match.groups()
    first, last = int(start), int(end or start)
    return range(first, last + 1) if first <= last else range(0)


class SubjectMatcher:
    def __init__(self, subject, siblings, episodes):
        canonical = [name for name in (subject["title"], subject["original"]) if name]
        self.seasons = season_numbers(" / ".join(canonical))
        recorded_aliases = subject.get("aliases", [])
        inferred = season_numbers(" / ".join(recorded_aliases))
        if not self.seasons and len(inferred) == 1:
            self.seasons = inferred
        self.numbered_aliases = [
            pattern for alias in recorded_aliases
            if season_numbers(alias) == self.seasons and self.seasons
            and (pattern := phrase_pattern(name_parts(alias)[0]))
        ]
        self.editions = set(EDITIONS.findall(_normalize(" ".join(canonical))))
        self.years = set(EDITION_YEAR.findall(_normalize(" ".join(canonical))))
        bases, parts = zip(*(name_parts(name) for name in canonical))
        self.parts = {part for part in parts if part}
        self.split_parts = split_parts(" ".join(self.parts))
        self.other_parts = set()
        self.shared_season = False
        self.same_base = False
        earlier_counts = []
        related_editions = set()
        for sibling in siblings:
            if sibling["id"] == subject["id"]:
                continue
            names = [sibling["title"], sibling["original"]]
            other_bases, other_parts = zip(*(name_parts(name) for name in names))
            if any(EDITIONS.search(name) and any(base in name for base in bases) for name in other_bases):
                related_editions.update(name_parts(alias)[0] for alias in sibling.get("aliases", []))
            if set(bases).intersection(other_bases):
                self.same_base = True
            if set(bases).intersection(other_bases) and self.seasons and season_numbers(" / ".join(names)) == self.seasons:
                self.shared_season = True
                self.other_parts.update(part for part in other_parts if part and part not in self.parts)
                count = sibling.get("episodes", 0)
                if (not any(other_parts) and sibling.get("date", "")
                        and sibling["date"] < subject.get("date", "") and isinstance(count, int) and count > 0):
                    earlier_counts.append(count)

        aliases = {*bases, *(name_parts(alias)[0] for alias in subject.get("aliases", []))}
        self.aliases = [pattern for alias in aliases if alias and (pattern := phrase_pattern(alias))]
        # A short nickname alone is too weak to identify an archive of the TV series.
        self.archive_names = [
            pattern for alias in aliases
            if (alias in bases or len(re.sub(r"[\W_]", "", alias)) >= 8)
            and (pattern := phrase_pattern(alias))
        ]
        self.related_editions = [
            pattern for alias in related_editions - aliases
            if len(re.sub(r"[\W_]", "", alias)) >= 8
            and not any(alias in name for name in aliases)
            and (pattern := phrase_pattern(alias))
        ]
        count = subject.get("episodes", 0)
        self.episode_count = count if type(count) is int and count > 1 else 0
        self.schedule_pending = False
        self.premiere_year = subject.get("date", "")[:4]
        self.by_local = {}
        self.by_total = {}
        self.season_offset = earlier_counts[0] if self.parts and len(earlier_counts) == 1 else None
        self.add_episode_dates(episodes)

    def add_episode_dates(self, episodes):
        for row in episodes:
            total, local = row.get("sort"), row.get("ep")
            aired = row.get("airdate")
            try:
                aired = date.fromisoformat(aired)
            except (TypeError, ValueError):
                aired = None
            if isinstance(total, (int, float)):
                self.by_total[total] = aired
            if isinstance(local, (int, float)):
                self.by_local[local] = aired
        self.by_season = ({number + self.season_offset: aired for number, aired in self.by_local.items()}
                          if self.season_offset is not None else {})

    def matches(self, resource):
        title = _normalize(resource.title)
        if set(EDITIONS.findall(title)) - self.editions:
            return False
        years = set(EDITION_YEAR.findall(title))
        if self.years and years and years != self.years:
            return False
        marked = season_numbers(title)
        if marked and marked != (self.seasons or {1}):
            return False
        if len(self.seasons) > 1 or any(part in title for part in self.other_parts):
            return False
        split = split_parts(title)
        if split and self.split_parts and split != self.split_parts:
            return False
        if split and not self.parts and any(split.intersection(split_parts(part)) for part in self.other_parts):
            return False
        numbered_name = bool(marked and self._numbered_name_in_title(title))
        if not numbered_name and not any(self._name_in_title(pattern, title) for pattern in self.aliases):
            return False

        explicit_part = any(part in title for part in self.parts) or bool(split and split == self.split_parts)
        totals = numbers(EXPLICIT_TOTAL.search(title))
        if totals:
            return bool(self.by_total) and all(number in self.by_total for number in totals)
        if explicit_part:
            return bool(marked)

        local = numbers(EPISODE_LABEL.fullmatch(episode_label(resource)))
        has_split_evidence = self.parts or self.shared_season or split
        if marked and not has_split_evidence and (not self.years or years == self.years):
            if self.by_local:
                return all(number in self.by_local for number in local) or (
                    numbered_name and bool(local) and not any(number in self.by_local for number in local)
                    and all(number in self.by_total for number in local)
                )
            if self.episode_count:
                return all(1 <= number <= self.episode_count for number in local)
            return not local or not self.schedule_pending
        # Split seasons and unnumbered releases need an episode/date check.
        # An unmarked number above the local range may be cumulative.
        if local and not marked and self.by_local and local.start > max(self.by_local):
            return self._near_airdate(resource, local, self.by_total)
        if self.seasons and not marked:
            return False
        if not (marked or has_split_evidence) and self._complete_archive(title, local):
            return True
        return self._near_airdate(resource, local, self.by_local) or (
            bool(marked) and self._near_airdate(resource, local, self.by_season)
        )

    def _complete_archive(self, title, episodes):
        if not self.episode_count or episodes != range(1, self.episode_count + 1):
            return False
        if self.same_base and (not self.premiere_year or self.premiere_year not in title):
            return False
        return not MIXED_PACK.search(title) and not any(pattern.search(title) for pattern in self.related_editions) and any(
            self._name_in_title(pattern, title) for pattern in self.archive_names
        )

    @staticmethod
    def _name_in_title(pattern, title):
        for match in pattern.finditer(title):
            tail = title[match.end():]
            if release_tail(tail):
                return True
        return False

    def _numbered_name_in_title(self, title):
        for pattern in self.numbered_aliases:
            for match in pattern.finditer(title):
                tail = title[match.end():].lstrip(" \t[({「『-")
                if season := SEASON_MARKER.match(tail):
                    suffix = tail[season.end():]
                    if release_tail(suffix) or re.match(r"^\s*[\])}]*\s*/", suffix):
                        return True
        return False

    @staticmethod
    def _near_airdate(resource, episodes, schedule):
        published = publication_date(resource.publish_time)
        if not episodes or not published:
            return False
        dates = [schedule.get(number) for number in episodes]
        if not all(dates):
            return False
        airdate = max(dates)
        return airdate - timedelta(days=1) <= published.date() <= airdate + timedelta(days=10)
