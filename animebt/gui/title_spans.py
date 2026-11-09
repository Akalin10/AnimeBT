"""Parse release-title display spans without changing the title or its ownership."""

from dataclasses import dataclass
from functools import lru_cache
from html import escape
import re
import unicodedata

from opencc import OpenCC


RULES = {
    "resolution": r"(?<![a-z0-9])(?:\d{3,4}\s*[x×]\s*\d{3,4}|(?:2160|1080|720|480)\s*[pi]|4k|uhd)(?![a-z0-9])",
    "codec": r"(?<![a-z0-9])(?:hevc|avc|av1|vp9|[hx][ ._-]?26[45])(?![a-z0-9])",
    "language": r"简繁(?:日)?(?:内封|外挂|内嵌|字幕)?|(?:简日|繁日|中日|英日)(?:双语|内封|外挂|内嵌|字幕)?|(?:简体|繁体|简中|繁中|英字|中字|国语|国粤双语)(?:字幕|内封|外挂|内嵌)?|(?<![a-z0-9])(?:chs|cht|gb_cn|big5|dual[ -]audio|multi[ -]subs?|eng[ -]subs?)(?![a-z0-9])",
    "season": r"第\s*[一二三四五六七八九十\d]+(?:\s*[-~至]\s*[一二三四五六七八九十\d]+)?\s*[季期]|(?<![a-z0-9])(?:s(?:eason\s*)?\d{1,2}\s*[-~]\s*s?\d{1,2}|season\s*\d+|\d+(?:st|nd|rd|th)\s+season|s\d{1,2})(?=e\d|[^a-z0-9]|$)",
    "extra": r"(?<![a-z0-9])(?:ova|oad|sp)(?:\s*\d{1,3})?(?![a-z0-9])|特别篇|小剧场|特典",
    "arc": r"(?:前半|后半|上半|下半)(?:部分|クール)?|(?:丧失|夺还|夺回|袭击|反击)[篇编]|第\s*[一二12]\s*部分|(?<![a-z0-9])(?:part|cour)\s*[1-9](?!\d)",
    "episode": r"(?:总\s*)?第\s*\d{1,3}(?:[.\-~～]\d{1,3})?\s*[集话話]|(?<=\bs\d)e\d{1,3}(?:[-~]e?\d{1,3})?(?!\d)|(?<=\bs\d\d)e\d{1,3}(?:[-~]e?\d{1,3})?(?!\d)|(?<![a-z0-9])(?:ep(?:isode)?|e)\s*\d{1,3}(?:[.\-~]\d{1,3})?(?![a-z0-9])|(?<![a-z0-9.])\d{1,3}\s*[-~～]\s*\d{1,3}(?![a-z0-9.])|(?<=\[)\s*\d{1,3}(?:v\d+)?\s*(?=\])|(?<= - )\d{1,3}(?:v\d+)?(?![a-z0-9.])",
    "collection": r"全\s*\d{1,3}\s*[集话話]|全集|合集|全季|全系列|修正合集|(?<![a-z0-9])(?:batch|collection|complete|bd[ -]?box)(?![a-z0-9])",
    "group": r"(?<![\w-])(?:loli\s*house|ani|vcb[ -]studio|prejudice[ -]studio|nix[ -]raws|reinforce)(?![\w-])|[^\s\[\](){}|/+:]{1,32}(?:字幕组|压制组|搬运组|汉化组|工作室)|(?<![\w-])[a-z0-9][a-z0-9._&-]{0,28}[- ]raws(?![\w-])",
}
PATTERNS = {kind: re.compile(pattern) for kind, pattern in RULES.items()}
DELIMITERS = str.maketrans(dict(zip("【】「」『』〔〕–—−", "[][][][]---")))
BARE_EPISODE = re.compile(r"(?<![\w.])\d{1,3}(?:v\d+)?(?![\w.]|\s*[x×]\s*\d)")
GAP = re.compile(r"[\s\[\](){}【】「」《》|/·•:：\-–—]*")
GROUP_TOKEN = re.compile(r"[\w][\w ._&-]{1,30}")
_simplifier = OpenCC("t2s")

# Tint colors for the normal and hovered resource row backgrounds.
BACKGROUNDS = (("#f8f9fe", "#edf1fa"), ("#202a3e", "#29364d"))
INKS = (
    {"default": "#202843", "anime": "#17488a", "season": "#61308e", "arc": "#61308e",
     "episode": "#00615a", "extra": "#00615a", "resolution": "#744700", "codec": "#91234b",
     "language": "#285d32", "group": "#4a5265", "collection": "#675027"},
    {"default": "#eef1ff", "anime": "#a6cbff", "season": "#dec4ff", "arc": "#dec4ff",
     "episode": "#98e6dc", "extra": "#98e6dc", "resolution": "#ffdb97", "codec": "#ffb7d1",
     "language": "#b8e3b6", "group": "#c9d2e8", "collection": "#f4d5a7"},
)


@dataclass(frozen=True, order=True)
class Span:
    start: int
    end: int
    kind: str

    def as_dict(self):
        return {"start": self.start, "end": self.end, "kind": self.kind}


@lru_cache(maxsize=4096)
def _fold_char(character):
    return _simplifier.convert(unicodedata.normalize("NFKC", character).translate(DELIMITERS)).casefold()


def folded(text):
    return "".join(map(_fold_char, text))


def overlaps(span, spans):
    return any(span.start < other.end and other.start < span.end for other in spans)


def _name_pattern(name):
    words = re.findall(r"[^\W_]+", folded(name))
    if words:
        return re.compile(r"(?<![a-z0-9])" + r"[\W_]*".join(map(re.escape, words)) + r"(?![a-z0-9])")
    return None


@lru_cache(maxsize=512)
def _name_patterns(names):
    return tuple(pattern for name in names if (pattern := _name_pattern(name)))


@lru_cache(maxsize=4096)
def parse_display_title(title, names=()):
    # Map normalized matches back to Python Unicode code-point positions.
    pieces = [_fold_char(character) for character in title]
    text = "".join(pieces)
    positions = [index for index, piece in enumerate(pieces) for _ in piece]
    spans = []

    def original(match, kind, group=0):
        return Span(positions[match.start(group)], positions[match.end(group) - 1] + 1, kind)

    for kind, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            span = original(match, kind)
            if not overlaps(span, spans):
                spans.append(span)

    hits = [original(match, "anime") for pattern in _name_patterns(names) for match in pattern.finditer(text)]
    for span in sorted(hits, key=lambda item: (item.start, -(item.end - item.start))):
        if not overlaps(span, spans):
            spans.append(span)

    # With a known title, an adjacent leading bracket can identify a release
    # group. A bracket around the title itself never proves it is a group.
    leading = re.match(r"^\s*\[([^\[\]]{2,35})\]\s*(?:\[\s*)?", text)
    if leading and any(span.kind == "anime" and span.start == positions[leading.end()]
                       for span in spans if leading.end() < len(positions)):
        candidate = original(leading, "group", 1)
        if (not overlaps(candidate, spans) and re.fullmatch(r"[a-z0-9][a-z0-9 ._&-]+", leading[1])
                and re.search("[a-z]", leading[1])
                and not re.search(r"web|\bbd\b|rip|remux|mkv|mp4|flac|aac|\b(?:tv|raw|fin)\b", leading[1])):
            spans.append(candidate)

    if not any(span.kind == "anime" for span in spans):
        groups = [span.end for span in spans if span.kind == "group" and not title[:span.start].strip(" 【[「")]
        start = max(groups, default=0)
        for field in sorted(spans):
            if field.kind != "episode" or field.start <= start:
                continue
            fragment = title[start:field.start]
            match = re.fullmatch(r"[\s\]】」]*[\[【「]?\s*([^\[\]【】「」|]{3,100}?)\s*[\]】」]?\s*[-–—]?\s*[\[【「]?", fragment)
            if match and any(character.isalpha() for character in match[1]):
                span = Span(start + match.start(1), start + match.end(1), "anime")
                if not overlaps(span, spans):
                    spans.append(span)
            break

    name_end = min((span.end for span in spans if span.kind == "anime"), default=0)
    ambiguous_number = any(
        (span := original(match, "episode")).start >= name_end and not overlaps(span, spans)
        for match in BARE_EPISODE.finditer(text)
    )
    ambiguous = bool(spans and (not name_end or ambiguous_number))
    return tuple(sorted(spans)), ambiguous


def spans_from_data(values, length):
    result = []
    for value in values:
        if not isinstance(value, dict):
            continue
        start, end, kind = value.get("start"), value.get("end"), value.get("kind")
        if type(start) is int and type(end) is int and 0 <= start < end <= length and isinstance(kind, str) and kind in PATTERNS.keys() | {"anime"}:
            span = Span(start, end, kind)
            if not overlaps(span, result):
                result.append(span)
    return tuple(sorted(result))


def validate_suggestions(title, local, suggestions):
    if not isinstance(suggestions, list):
        return ()
    accepted = []
    normalized = folded(title)
    for item in suggestions[:24]:
        if not isinstance(item, dict) or not isinstance(item.get("kind"), str):
            continue
        spans = spans_from_data([item], len(title))
        if not spans:
            continue
        span = spans[0]
        snippet = title[span.start:span.end]
        if item.get("text") != snippet or overlaps(span, (*local, *accepted)):
            continue
        text = folded(snippet)
        pattern = PATTERNS.get(span.kind)
        # A rule must match at the same position in context, not just inside a
        # clipped fragment such as the HEVC substring of another token.
        prefix = folded(title[:span.start])
        match = pattern.match(normalized, len(prefix)) if pattern else None
        validated = bool(match and match.end() == len(prefix) + len(text))
        if span.kind == "episode":
            match = BARE_EPISODE.match(normalized, len(prefix))
            earlier = [anchor.end for anchor in local
                       if anchor.kind in {"anime", "season", "arc"} and anchor.end <= span.start]
            validated |= bool(match and match.end() == len(prefix) + len(text)
                              and earlier and any(anchor.kind == "anime" for anchor in local)
                              and GAP.fullmatch(title[max(earlier):span.start]))
        if span.kind == "group" and GROUP_TOKEN.fullmatch(text) and any(char.isalpha() for char in text):
            next_name = next((anchor for anchor in local if anchor.kind == "anime" and anchor.start >= span.end), None)
            gap = title[span.end:next_name.start] if next_name else ""
            validated |= bool(next_name and GAP.fullmatch(title[:span.start]) and GAP.fullmatch(gap)
                              and any(char in gap for char in "]】」|"))
        if span.kind == "anime" and not any(anchor.kind == "anime" for anchor in local):
            next_field = next((anchor for anchor in local if anchor.kind in {"episode", "season", "resolution"}
                               and anchor.start >= span.end), None)
            earlier_groups = [anchor.end for anchor in local if anchor.kind == "group" and anchor.end <= span.start]
            validated = bool(next_field and 3 <= len(text) <= 100 and any(char.isalpha() for char in text)
                             and not re.search(r"[\[\](){}【】「」《》|<>]", text)
                             and GAP.fullmatch(title[max(earlier_groups, default=0):span.start])
                             and GAP.fullmatch(title[span.end:next_field.start])
                             and not any(pattern.search(text) for pattern in PATTERNS.values()))
        if validated:
            accepted.append(span)
    return tuple(sorted(accepted))


def rich_title(title, spans, dark):
    palette = INKS[int(dark)]
    parts = []
    cursor = 0
    for span in sorted(spans):
        parts.append(escape(title[cursor:span.start]))
        parts.append(f'<span style="color:{palette[span.kind]}">{escape(title[span.start:span.end])}</span>')
        cursor = span.end
    parts.append(escape(title[cursor:]))
    return f'<span style="color:{palette["default"]}; white-space:pre-wrap">' + "".join(parts) + "</span>"
