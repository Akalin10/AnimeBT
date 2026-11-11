"""Bounded multilingual search plans. Queries discover candidates, never prove ownership."""

from collections import defaultdict, deque
import re
import unicodedata

from .resource_match import recorded_ova_subtitle, season_numbers, shared_series_names, supplementary_names, traditional_name
from .series_resources import distinguishing_suffixes


def _key(name):
    # Do not use OpenCC here. Some sites index simplified and traditional separately.
    return " ".join(unicodedata.normalize("NFKC", name).casefold().split())


def _language(name):
    if re.search(r"[ぁ-ヿ]", name):
        return "jp"
    if re.search(r"[\u3400-\u9fff]", name):
        return "cjk"
    return "latin"


def _variants(name, *, minimum_cjk=4):
    parts = re.split(r"\s*[/／|｜]\s*|(?<=[\u3400-\u9fffぁ-ヿ])\s+(?=[a-zA-Z])"
                     r"|(?<=[a-zA-Z])\s+(?=[\u3400-\u9fffぁ-ヿ])", name)
    for part in parts:
        minimum = minimum_cjk if _language(part) in {"cjk", "jp"} else 4
        if part != name and len(re.sub(r"[\W_]", "", part)) >= minimum:
            yield part.strip(" -:()[]")


def plan_queries(source, matcher, episodes, kind, *, initial, budget):
    work = matcher.subject
    title, original = work["title"], work["original"]
    aliases = work.get("aliases", [])
    related = [entry for entry_id, entry in matcher.works.items() if entry_id != work["id"]]
    stems = shared_series_names(work, related)
    ova_stem, ova_subtitle = recorded_ova_subtitle(work) if kind == "ova" else ("", "")
    if ova_stem:
        stems.insert(0, ova_stem)
    if matcher.root["id"] != work["id"]:
        stems.extend((matcher.root["title"], matcher.root["original"]))
    names = [title, original, *aliases]
    seasons = matcher.seasons[work["id"]]
    specific = [name for name in aliases if seasons and season_numbers(name) == seasons]
    if kind in {"movie", "ova", "sp", "mini", "web"}:
        specific.extend(distinguishing_suffixes(work, matcher.root))
        specific.extend((ova_subtitle, *[part for name in (title, original) for part in re.split(r"[!！~～〜]", name)[1:]
                                        if len(re.sub(r"[\W_]", "", part)) >= 4]))
    variants = [part for name in names for part in _variants(name)]
    traditional = [traditional_name(name) for name in [*stems, title] if _language(name) == "cjk"]
    written = supplementary_names(work, ())
    chapters = [name for name in supplementary_names(work, episodes) if name not in written]
    if budget > 6:
        for name in names:
            words = re.findall(r"[A-Za-z]{3,}", name)
            if _language(name) == "latin" and 4 <= len(words) <= 7:
                variants.append("".join(word[0] for word in words).upper())

    preferred = tuple(dict.fromkeys((*getattr(source, "language_priority", ()), "cjk", "jp", "latin", "romaji")))
    tagged = work.get("aliasLanguages", {})
    buckets = defaultdict(deque)
    seen = {_key(initial)}
    plan = []

    def add(name):
        name = " ".join(name.split())
        key = _key(name)
        if key and key not in seen and len(plan) < budget:
            seen.add(key)
            plan.append(name)

    # A short series term can find an archive that omits the work's subtitle.
    if stems:
        add(stems[0])
    for name in [*specific, *names, *variants, *stems[1:], *written]:
        if name and _key(name) not in seen:
            language = tagged.get(name, _language(name))
            if language not in preferred:
                language = _language(name)
            if name == original and language == "cjk" and _key(name) != _key(title):
                language = "jp"
            buckets[language].append(name)
    for language in preferred:
        bucket = buckets[language]
        while bucket and _key(bucket[0]) in seen:
            bucket.popleft()
        if bucket:
            add(bucket.popleft())
    alternate = next((name for name in traditional if _key(name) not in seen), "")
    add(alternate)
    if chapters and kind in {"ova", "sp", "mini", "web"}:
        add(chapters[0])
    buckets["cjk"].extend(traditional)
    while len(plan) < budget and any(buckets.values()):
        for language in preferred:
            if buckets[language]:
                add(buckets[language].popleft())
    return plan
