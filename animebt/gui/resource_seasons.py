"""Display/filter season evidence. Never used to accept or reject BT resources."""
from functools import lru_cache
import re
import unicodedata

from .resource_match import season_numbers
from .series_resources import bundled_seasons


UNKNOWN = "未知"
NUMBER = r"[零〇一二三四五六七八九十\d]+"
CHINESE_RANGE = re.compile(r"第?\s*(" + NUMBER + r")\s*[-~～至到]\s*第?\s*(" + NUMBER + r")\s*[季期]")
ENGLISH_RANGE = re.compile(r"(?<![a-z0-9])s(?:easons?\s*)?(\d{1,2})\s*[-~～–至到]\s*(?:s(?:easons?\s*)?)?(\d{1,2})(?![a-z0-9])", re.I)
CHINESE_LIST = re.compile(r"第?\s*(" + NUMBER + r"(?:\s*[、,+&/]\s*(?:第\s*)?" + NUMBER + r")+)\s*[季期]")
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}
WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
         "ファースト": 1, "セカンド": 2, "サード": 3}


def needs_season_help(title):
    return bool(re.search(r"season|シーズン|[篇編章季期]|\barc\b", title, re.I))


GROUP_PREFIX = re.compile(r"\s*[\[【]([^\]】]+)[\]】]\s*")
GROUP_WORD = re.compile(r"字幕[组組]|raws|fansub|encod(?:e|ers?)|vcb[- ]studio|lolihouse", re.I)
EPISODE_SEASON_RANGE = re.compile(r"(?<![a-z0-9])s(\d+)e\d+\s*[-~～–至到]\s*s(\d+)e\d+", re.I)
ENGLISH_LIST = re.compile(r"\bseasons?\s+(\d+(?:\s*(?:,|、|/|&|\+|and)\s*\d+)+)(?![a-z0-9])", re.I)
NUMERIC_RANGE = re.compile(r"(?<![a-z0-9])s(?:easons?\s*)?(\d+)\s*[-~～–至到]\s*(?:s(?:easons?\s*)?)?(\d+)(?![a-z0-9])", re.I)


def group_prefix_end(title, fansub=""):
    end = 0
    while match := GROUP_PREFIX.match(title, end):
        if not (GROUP_WORD.search(match[1]) or fansub and match[1].casefold() == fansub.casefold()):
            break
        end = match.end()
    return end


def season_text(title, fansub=""):
    text = unicodedata.normalize("NFKC", title)
    return text[group_prefix_end(text, fansub):]


def invalid_season_evidence(title, fansub=""):
    text = season_text(title, fansub)
    for pattern in (NUMERIC_RANGE, EPISODE_SEASON_RANGE):
        for match in pattern.finditer(text):
            if not 1 <= int(match[1]) <= int(match[2]) <= 30:
                return True
    for match in CHINESE_RANGE.finditer(text):
        first = season_numbers("第" + match[1] + "季")
        last = season_numbers("第" + match[2] + "季")
        if len(first) != 1 or len(last) != 1 or not 1 <= next(iter(first)) <= next(iter(last)) <= 30:
            return True
    if any(not 1 <= n <= 30 for n in season_numbers(text)):
        return True
    for match in ENGLISH_LIST.finditer(text):
        if any(not 1 <= int(n) <= 30 for n in re.findall(r"\d+", match[1])):
            return True
    for match in re.finditer(r"全\s*(" + NUMBER + r")\s*季", text):
        if not all(1 <= n <= 30 for n in season_numbers("第" + match[1] + "季")):
            return True
    return False


def marker_values(text):
    values = season_numbers(text)
    for match in re.finditer(r"\bseason\s+(viii|vii|iii|vi|iv|ii|ix|i|v|x)\b", text, re.I):
        values.add(ROMAN[match[1].casefold()])
    for word, number in WORDS.items():
        if re.search(r"(?<![a-z])" + re.escape(word) + r"\s*(?:season\b|シーズン)", text, re.I):
            values.add(number)
    return values


@lru_cache(maxsize=4096)
def local_seasons(title, fansub=""):
    text = season_text(title, fansub)
    if invalid_season_evidence(title, fansub):
        return ()
    bundles = bundled_seasons(text)
    values = marker_values(text) | bundles
    for pattern in (NUMERIC_RANGE, EPISODE_SEASON_RANGE):
        for match in pattern.finditer(text):
            bundles.update(range(int(match[1]), int(match[2]) + 1))
    for match in CHINESE_RANGE.finditer(text):
        first = next(iter(season_numbers("第" + match[1] + "季")))
        last = next(iter(season_numbers("第" + match[2] + "季")))
        bundles.update(range(first, last + 1))
    for match in CHINESE_LIST.finditer(text):
        for label in re.findall(NUMBER, match[1]):
            bundles.update(season_numbers("第" + label + "季"))
    for match in ENGLISH_LIST.finditer(text):
        bundles.update(int(n) for n in re.findall(r"\d+", match[1]))
    for match in re.finditer(r"全\s*(" + NUMBER + r")\s*季", text):
        total = season_numbers("第" + match[1] + "季")
        if len(total) == 1:
            bundles.update(range(1, next(iter(total)) + 1))
    values.update(bundles)
    if len(values) > 1 and not values <= bundles:
        return ()  # Contradictory single-season labels do not prove a bundle.
    return tuple(sorted(number for number in values if 1 <= number <= 30))


def proof_seasons(text):
    """Closed vocabulary for checking AI evidence, without trusting model lore."""
    result = set(local_seasons(text))
    normalized = unicodedata.normalize("NFKC", text).casefold()
    for match in re.finditer(r"\bseason\s*[:：-]?\s*(viii|vii|iii|vi|iv|ii|ix|i|v|x)\b", normalized):
        result.add(ROMAN[match[1]])
    for word, number in WORDS.items():
        if re.search(r"(?<![a-z])" + re.escape(word) + r"\s*(?:season\b|シーズン)", normalized):
            result.add(number)
    return result


def validate_ai_seasons(title, result, fansub=""):
    if season_conflict({"title": title, "fansub": fansub}):
        return ()
    if not isinstance(result, dict):
        return ()
    work, arc, seasons, evidence = (result.get(key) for key in ("work", "arc", "seasons", "evidence"))
    if (not isinstance(work, str) or len(work.strip()) < 2 or work not in title
            or not isinstance(arc, str) or arc and arc not in title
            or not isinstance(seasons, list) or not 1 <= len(seasons) <= 30
            or any(type(number) is not int or not 1 <= number <= 30 for number in seasons)
            or not isinstance(evidence, list) or not 1 <= len(evidence) <= 16):
        return ()
    confirmed = set()
    group_end = group_prefix_end(title, fansub)
    for item in evidence:
        if not isinstance(item, dict):
            return ()
        start, end, text = (item.get(key) for key in ("start", "end", "text"))
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(title)
                or text != title[start:end]):
            return ()
        if start < group_end:
            return ()
        # An extracted "Season II" must not be the prefix of "Season III".
        if (end < len(title) and re.match(r"[a-z0-9]", text[-1], re.I)
                and re.match(r"[a-z0-9]", title[end], re.I)):
            return ()
        if (start > 0 and re.match(r"[a-z0-9]", text[0], re.I)
                and re.match(r"[a-z0-9]", title[start-1], re.I)):
            return ()
        confirmed.update(proof_seasons(text))
    # An arc name alone cannot prove a season number. No title-specific exceptions.
    full_title = set(local_seasons(title, fansub))
    return tuple(sorted(set(seasons))) if set(seasons) == confirmed and (not full_title or set(seasons) == full_title) else ()


@lru_cache(maxsize=4096)
def season_identity(title, fansub=""):
    """Remove isolated technical/episode blocks, never truncate the remaining title."""
    text = season_text(title, fansub).strip()
    def block(match):
        content = match[1].strip()
        if needs_season_help(content) or season_numbers(content):
            return match[0]
        atom = r"(?:\d{3,4}[pi]|web[- ]?(?:dl|rip)|bd(?:rip)?|hevc|avc|x26[45]|aac|flac|chs|cht|10[- ]?bit)"
        technical = atom + r"(?:[\s._,/+&-]+" + atom + r")*"
        episode = r"\d{1,4}(?:[-~]\d{1,4})?(?:v\d+)?"
        return " " if re.fullmatch(technical, content, re.I) or re.fullmatch(episode, content, re.I) else match[0]
    text = re.sub(r"[\[【]([^\]】]*)[\]】]", block, text)
    return re.sub(r"\s+", " ", re.sub(r"[\[\]【】]", " ", text)).strip().casefold()


def season_conflict(row):
    title, fansub = row.get("title", ""), row.get("fansub", "")
    if invalid_season_evidence(title, fansub):
        return True
    explicit = set(local_seasons(title, fansub))
    if not explicit and len(marker_values(season_text(title, fansub))) > 1:
        return True
    metadata = {n for n in row.get("verifiedSeasons", []) if type(n) is int and 1 <= n <= 30}
    return bool(explicit and metadata and not metadata <= explicit)


def known_seasons(row):
    if season_conflict(row):
        return ()
    explicit = local_seasons(row.get("title", ""), row.get("fansub", ""))
    metadata = tuple(sorted({n for n in row.get("verifiedSeasons", []) if type(n) is int and 1 <= n <= 30}))
    return explicit or metadata


def cached_seasons(title, data, fansub=""):
    """Re-anchor every cached proof in the current original title, or reject it."""
    if not isinstance(data, dict) or not isinstance(data.get("result"), dict):
        return ()
    result = data["result"]
    if not validate_ai_seasons(data.get("title", ""), result):
        return ()
    relocated = []
    for item in result["evidence"]:
        fragment = item["text"]
        positions = [m.start() for m in re.finditer(re.escape(fragment), title)]
        if len(positions) != 1:
            return ()
        start = positions[0]
        relocated.append({"text": fragment, "start": start, "end": start + len(fragment)})
    return validate_ai_seasons(title, dict(result, evidence=relocated), fansub)


def season_labels(numbers):
    return [f"S{number:02}" for number in numbers] if numbers else [UNKNOWN]
