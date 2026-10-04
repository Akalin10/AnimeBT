"""Conservative release parsing; original titles are retained."""
from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class TitleMetadata:
    anime_name: str
    episode: str | None = None
    fansub: str | None = None
    resolution: str | None = None
    codec: str | None = None


def clean_title(title):
    return unicodedata.normalize("NFKC", title).translate(str.maketrans({"【": "[", "】": "]", "–": "-", "—": "-"}))


def parse_title(title):
    text = clean_title(title)
    specifications = text.replace("_", " ")
    match = re.search(r"(?i)(?<!\d)(2160|1080|720|480)\s*[pi]\b", specifications)
    resolution = match[1] + "p" if match else None
    if not resolution:
        if re.search(r"(?i)\b(?:3840\s*[x×]\s*2160|4k)\b", specifications):
            resolution = "2160p"
        elif re.search(r"(?i)\b1920\s*[x×]\s*1080\b", specifications):
            resolution = "1080p"
    codec = "HEVC" if re.search(r"(?i)\b(?:hevc|[hx][ ._-]?265)\b", specifications) else (
        "AVC" if re.search(r"(?i)\b(?:avc|[hx][ ._-]?264)\b", specifications) else None)
    group = re.match(r"^\s*\[([^\]]+)\]", text)
    fansub = None
    if group and not re.search(r"(?i)\b(?:\d{3,4}p|hevc|avc|web.?dl|b[dr]rip|\d{8}|4k)\b", group[1]):
        fansub = group[1].strip()
        text = text[group.end():].strip()
    # Many releases enclose the anime name itself in a second bracket.
    bracket_name = re.match(r"^\[([^\]]+)\]", text)
    if bracket_name and not re.match(r"(?i)^(?:\d|web|b[dr]rip|hevc|avc|[hx][ ._-]?26[45]|aac|flac|cht|chs|mp4|mkv)", bracket_name[1]):
        text = bracket_name[1] + text[bracket_name.end():]
    # Prefer the local episode in '[18- 总第84]', keeping the cumulative number in the original title.
    episode_match = re.search(r"\[(\d{1,3}(?:\.\d+)?)(?:[vV]\d+)?\s*[-~]?\s*[总總]\s*第?\s*\d+(?:\s*[话話集])?\]", text)
    if episode_match is None:
        patterns = [
            r"(?i)(?:\b(?:ep(?:isode)?|e)\s*)(\d{1,3}(?:\.\d+)?)(?:[vV]\d+)?",
            r"第\s*(\d{1,3}(?:\.\d+)?)\s*[话話集]",
            r"\s-\s*(\d{1,3}(?:\.\d+)?(?:\s*[-~]\s*\d{1,3})?)(?:[vV]\d+)?(?=\s|\[|\(|$)",
            r"\[(\d{1,3}(?:\s*[-~]\s*\d{1,3})?)(?:[vV]\d+)?\]",
        ]
        candidates = [match for pattern in patterns if (match := re.search(pattern, text))]
        episode_match = min(candidates, key=lambda match: match.start()) if candidates else None
    episode = re.sub(r"\s+", "", episode_match[1]) if episode_match else None
    name = text[:episode_match.start()].strip(" -") if episode_match else text
    name = re.sub(r"\[[^\]]*\]", "", name)
    name = re.split(r"(?i)\s*\((?:\d{3,4}p|\d{3,4}[x×]\d{3,4}|web|hevc|avc|cr\s)", name)[0]
    return TitleMetadata(name.strip(" -") or title, episode, fansub, resolution, codec)


def normalized_title(title):
    """Retain episode, language, group, revision and other release information."""
    text = clean_title(title).casefold()
    text = re.sub(r"\b(?:hevc|[hx][ ._-]?265)\b", "hevc", text)
    text = re.sub(r"\b(?:avc|[hx][ ._-]?264)\b", "avc", text)
    text = re.sub(r"[\s\[\](){}_]+", "", text)
    # A release range such as 01-12 must not collapse into episode 0112.
    return re.sub(r"(?<!\d)-|-(?!\d)", "", text)
