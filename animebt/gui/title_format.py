"""Validated, display-only formatting of exact release-title fragments."""

from dataclasses import dataclass
from functools import lru_cache
from html import escape, unescape
import colorsys
import re

from .title_spans import BACKGROUNDS, PATTERNS, folded


FIELD_COLORS = {
    "group": "#A855F7", "anime": "#3B82F6", "episode": "#F59E0B",
    "type": "#14B8A6", "source": "#22C55E", "resolution": "#06B6D4",
    "video": "#EC4899", "audio": "#8B5CF6", "language": "#F97316", "other": "#64748B",
}
FIELD_PATTERNS = {
    "type": re.compile(r"(?:tv|ova|oad|sp\d*|specials?|movie|film|ona|剧场版|特别篇|特典|小剧场)", re.I),
    "source": re.compile(r"(?:web[- .]?(?:dl|rip)|blu[- .]?ray|bd(?:rip|mv)?|dvd(?:rip)?|hdtv|tvrip|remux)", re.I),
    "audio": re.compile(r"(?:aac|flac|alac|ac[- .]?3|e[- .]?ac[- .]?3|ddp?|dts(?:[- .]?(?:hd|ma))?|truehd|opus|pcm|mp3)"
                        r"(?:[ ._-]?(?:\d(?:\.\d)?|\d{2,3}k(?:bps)?|\d{2}bit|ch|hd|ma))*", re.I),
    "video": re.compile(r"(?:x26[45]|h[ .]?26[45]|hevc|avc|av1|vp9|mpeg[ -]?[24])(?:[- _]?(?:8|10|12)[- ]?bit)?", re.I),
    "resolution": PATTERNS["resolution"],
    "language": re.compile(r"(?:" + PATTERNS["language"].pattern + r")(?:字幕)?", re.I),
}
SEPARATORS = " \t\r\n[](){}【】「」『』《》_–—|/,："
ENTITY = re.compile(r"&(?:#[0-9]+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]+);")


@lru_cache(maxsize=2048)
def plain_title(title):
    """Decode one transport-entity layer for display, never modify source data."""
    return ENTITY.sub(lambda match: unescape(match[0]), title)


def escaped_title(title):
    return escape(plain_title(title))


def align_model_fields(title, values):
    """Repair counting errors only for an exact, uniquely occurring substring.

    No fuzzy matching, translation or repeated-fragment disambiguation is allowed.
    Persisted positions still pass the same strict validator as cached results.
    """
    if not isinstance(values, list) or len(values) > 64:
        return []
    aligned = []
    for value in values:
        if not isinstance(value, dict):
            continue
        text, start, end = (value.get(key) for key in ("text", "start", "end"))
        if (not isinstance(text, str) or not text or type(start) is not int or type(end) is not int):
            continue
        if not (0 <= start < end <= len(title) and title[start:end] == text):
            first = title.find(text)
            if first < 0 or title.find(text, first + 1) >= 0:
                continue
            value = dict(value, start=first, end=first + len(text))
        # Technical compound labels must not color an audio codec as video, etc.
        # Keep the original fragments; split only when every non-separator
        # character has a deterministic technical interpretation.
        kind = value.get("kind")
        if isinstance(kind, str) and (kind == "other" or kind in FIELD_PATTERNS
                                      and not FIELD_PATTERNS[kind].fullmatch(folded(text))):
            pieces = []
            for match in re.finditer(r"[^ _/]+", text):
                token = match[0]
                kinds = [name for name, pattern in FIELD_PATTERNS.items() if pattern.fullmatch(folded(token))]
                if len(kinds) != 1:
                    kinds = ["other"]
                offset = value["start"] + match.start()
                pieces.append({"kind": kinds[0], "text": token, "start": offset, "end": offset + len(token)})
            if pieces and any(piece["kind"] != "other" for piece in pieces):
                aligned.extend(pieces)
                continue
        aligned.append(value)
    return aligned


@dataclass(frozen=True)
class TitleField:
    kind: str
    start: int
    end: int

    def as_dict(self, title):
        return {"kind": self.kind, "start": self.start, "end": self.end,
                "text": title[self.start:self.end]}


def validate_fields(title, values):
    if not isinstance(values, list) or len(values) > 64:
        return ()
    # Validate name evidence before relying on it for bracketed groups or bare
    # episode numbers. A malformed model name must not authorize other fields.
    names = []
    for value in values:
        if (isinstance(value, dict) and value.get("kind") == "anime"
                and type(value.get("start")) is int and type(value.get("end")) is int):
            start, end = value["start"], value["end"]
            snippet = title[start:end]
            if (0 <= start < end <= len(title) and value.get("text") == snippet
                    and snippet == snippet.strip() and len(snippet) >= 2
                    and any(char.isalpha() for char in snippet)
                    and not re.search(r"[\[\]{}【】「」『』]", snippet)
                    and not any(pattern.fullmatch(folded(snippet)) for pattern in FIELD_PATTERNS.values())
                    and not PATTERNS["group"].fullmatch(folded(snippet))):
                names.append((start, end))
    candidates = []
    entities = [(match.start(), match.end()) for match in ENTITY.finditer(title)]
    for value in values:
        if not isinstance(value, dict):
            continue
        kind, start, end = (value.get(key) for key in ("kind", "start", "end"))
        if (not isinstance(kind, str) or kind not in FIELD_COLORS or type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(title) or value.get("text") != title[start:end]):
            continue
        snippet = title[start:end]
        if snippet != snippet.strip() or re.search(r"[\[\]{}【】「」『』]", snippet):
            continue
        if any(left < start < right or left < end < right for left, right in entities):
            continue
        normalized = folded(snippet)
        if kind in {"anime", "group"} and any(
            re.search(r"(?<![a-z0-9])(?:" + FIELD_PATTERNS[name].pattern + r")(?![a-z0-9])", normalized, re.I)
            for name in ("source", "resolution", "video", "audio")
        ):
            # Exact text is insufficient evidence for a name containing mixed
            # technical fields. Display the complete uncolored original instead.
            return ()
        if kind in FIELD_PATTERNS and not FIELD_PATTERNS[kind].fullmatch(normalized):
            continue
        if kind == "episode" and not (
            PATTERNS["season"].fullmatch(normalized) or PATTERNS["episode"].fullmatch(normalized)
            or PATTERNS["collection"].fullmatch(normalized)
            or re.fullmatch(r"s\d{1,2}e\d{1,4}(?:[-~]e?\d{1,4})?", normalized)
            or re.fullmatch(r"\d{1,3}(?:v\d+)?", normalized)
            and bool(names)
        ):
            continue
        if kind == "anime" and (
            len(snippet) < 2 or not any(char.isalpha() for char in snippet)
            or any(pattern.fullmatch(normalized) for pattern in FIELD_PATTERNS.values())
            or PATTERNS["group"].fullmatch(normalized)
        ):
            continue
        if kind == "group" and not (
            PATTERNS["group"].fullmatch(normalized)
            or re.fullmatch(r"\s*[\[【「]\s*", title[:start])
            and re.match(r"\s*[\]】」]", title[end:])
            and any(name_start > end for name_start, _ in names)
        ):
            continue
        candidates.append(TitleField(kind, start, end))
    # Conflicting or duplicated positions invalidate the item, rather than letting
    # model order decide which semantic label wins.
    candidates.sort(key=lambda field: (field.start, field.end))
    if any(left.end > right.start for left, right in zip(candidates, candidates[1:])):
        return ()
    return tuple(candidates)


def _luminance(color):
    values = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values]
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(first, second):
    low, high = sorted((_luminance(first), _luminance(second)))
    return (high + 0.05) / (low + 0.05)


@lru_cache(maxsize=20)
def field_color(kind, dark):
    """Keep the requested semantic hue; adapt only lightness for reading plates.

    Include GlassThemeManager's readingRange limits as well as normal/hover
    plates, so material tint cannot reduce contrast below AA. No span background.
    """
    seed = FIELD_COLORS[kind]
    backgrounds = (*BACKGROUNDS[int(dark)], "#454545" if dark else "#dbdbdb")
    rgb = tuple(int(seed[index:index + 2], 16) / 255 for index in (1, 3, 5))
    hue, lightness, saturation = colorsys.rgb_to_hls(*rgb)
    for step in range(101):
        target = lightness + ((1 if dark else 0) - lightness) * step / 100
        values = colorsys.hls_to_rgb(hue, target, saturation)
        color = "#" + "".join(f"{round(value * 255):02X}" for value in values)
        if all(contrast(color, background) >= 4.5 for background in backgrounds):
            return color
    return "#FFFFFF" if dark else "#000000"


@lru_cache(maxsize=2048)
def formatted_title(title, fields, dark):
    if not fields:
        return escaped_title(title)
    groups = {kind: [] for kind in FIELD_COLORS}
    cursor = 0
    for field in fields:
        # Retain meaningful unclaimed labels locally. No generated values enter
        # the formatted title, including when the model omits part of the input.
        fragments = re.split(r"[\[\](){}【】「」『』]", title[cursor:field.start])
        groups["other"].extend(_valuable(fragments))
        groups[field.kind].append(title[field.start:field.end])
        cursor = field.end
    groups["other"].extend(_valuable(re.split(r"[\[\](){}【】「」『』]", title[cursor:])))
    parts = []
    for kind, values in groups.items():
        if values:
            text = "[" + " ".join(values) + "]"
            parts.append(f'<span style="color:{field_color(kind, dark)};">'
                         + escaped_title(text) + "</span>")
    return " ".join(parts)


def _valuable(fragments):
    for fragment in fragments:
        value = fragment.strip(SEPARATORS)
        if value and not re.fullmatch(r"[-+:]+", value):
            yield value
