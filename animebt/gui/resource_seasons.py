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


@lru_cache(maxsize=4096)
def local_seasons(title):
    text = unicodedata.normalize("NFKC", title)
    # A group named S02-Raws is not evidence for season 2 of the work.
    text = re.sub(r"^\s*[\[【][^\]】]*(?:字幕[组組]|raws)[^\]】]*[\]】]", "", text, flags=re.I)
    values = season_numbers(text) | bundled_seasons(text)
    for match in ENGLISH_RANGE.finditer(text):
        start, end = int(match[1]), int(match[2])
        if 1 <= start <= end <= 30:
            values.update(range(start, end + 1))
    for match in CHINESE_RANGE.finditer(text):
        first = season_numbers("第" + match[1] + "季")
        last = season_numbers("第" + match[2] + "季")
        if len(first) == len(last) == 1:
            start, end = next(iter(first)), next(iter(last))
            if 1 <= start <= end <= 30:
                values.update(range(start, end + 1))
    for match in CHINESE_LIST.finditer(text):
        for label in re.findall(NUMBER, match[1]):
            values.update(season_numbers("第" + label + "季"))
    for match in re.finditer(r"全\s*(" + NUMBER + r")\s*季", text):
        total = season_numbers("第" + match[1] + "季")
        if len(total) == 1 and 1 <= next(iter(total)) <= 30:
            values.update(range(1, next(iter(total)) + 1))
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


def validate_ai_seasons(title, result):
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
    group = re.match(r"^\s*[\[【][^\]】]*(?:字幕[组組]|raws)[^\]】]*[\]】]", title, re.I)
    for item in evidence:
        if not isinstance(item, dict):
            return ()
        start, end, text = (item.get(key) for key in ("start", "end", "text"))
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(title)
                or text != title[start:end]):
            return ()
        if group and start < group.end():
            return ()
        confirmed.update(proof_seasons(text))
    # An arc name alone cannot prove a season number. No title-specific exceptions.
    return tuple(sorted(set(seasons))) if set(seasons) == confirmed else ()


@lru_cache(maxsize=4096)
def season_identity(title, fansub=""):
    """Keep work/arc/season qualifiers; remove only technical/release suffixes."""
    text = unicodedata.normalize("NFKC", title).strip()
    prefix = re.match(r"^[\[【]([^\]】]+)[\]】]\s*", text)
    if prefix and (prefix[1].casefold() == fansub.casefold() or re.search(
            r"字幕[组組]|raws|lolihouse|vcb[- ]studio", prefix[1], re.I)):
        text = text[prefix.end():]
    text = re.split(r"\s+-\s+\d{1,4}(?:v\d+)?\b|[\[【]\s*\d{1,4}(?:[-~]\d{1,4})?\s*[\]】]", text, maxsplit=1)[0]
    text = re.split(r"[\[【(]\s*(?:\d{3,4}[pi]|web[- ]?(?:dl|rip)|bd(?:rip)?|hevc|avc|x26[45]|aac|flac|chs|cht)\b", text, maxsplit=1, flags=re.I)[0]
    # Normalize delimiters only, never remove work/arc names or season numbers.
    return re.sub(r"\s+", " ", re.sub(r"[\[\]【】]", " ", text)).strip().casefold()


def known_seasons(row):
    explicit = local_seasons(row.get("title", ""))
    metadata = tuple(sorted({number for number in row.get("verifiedSeasons", [])
                             if type(number) is int and 1 <= number <= 30}))
    if explicit and metadata and not set(explicit).intersection(metadata):
        return ()  # Conflicting evidence is not grounds to guess.
    return explicit or metadata


def season_conflict(row):
    explicit = set(local_seasons(row.get("title", "")))
    metadata = {number for number in row.get("verifiedSeasons", []) if type(number) is int and 1 <= number <= 30}
    return bool(explicit and metadata and not explicit.intersection(metadata))


def season_labels(numbers):
    return [f"S{number:02}" for number in numbers] if numbers else [UNKNOWN]
