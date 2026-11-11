"""Shared resource presentation for keyword and verified poster searches."""

from dataclasses import replace
from hashlib import sha256

from animebt.core.dedupe import deduplicate
from animebt.core.results import display_date, filter_sort, publication_date

from .resource_match import episode_label
from .series_resources import merge_attributions
from .title_spans import parse_display_title


def resource_rows(resources, matcher=None):
    by_hash = {}
    if matcher:
        for resource in resources:
            attribution = matcher.classify(resource)
            if resource.info_hash:
                by_hash.setdefault(resource.info_hash, []).append((resource, attribution))
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
        category = attribution.category(matcher.subject["id"]) if attribution else "搜索资源"
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
        published = publication_date(resource.publish_time)
        rows.append({
            "key": resource.info_hash or sha256(
                repr((resource.title, resource.torrent_url, resource.magnet, resource.size,
                      resource.source, resource.source_id, resource.publish_time)).encode("utf-8")
            ).hexdigest(),
            "title": resource.title,
            "titleSpans": [span.as_dict() for span in spans],
            "titleAmbiguous": ambiguous,
            "episode": episode_label(resource),
            "resolution": resource.metadata.resolution or "未知",
            "fansub": resource.metadata.fansub or "未知",
            "size": resource.display_size,
            "date": display_date(resource.publish_time),
            "sort_time": published.timestamp() if published else None,
            "sort_size": resource.size,
            "sources": " / ".join(resource.sources),
            "provenance": resource.origins,
            "magnet": resource.magnet or "",
            "torrent_url": resource.torrent_url or "",
            "info_hash": resource.info_hash or "",
            "category": category,
            "work_ids": work_ids,
            "works": [matcher.works[entry_id]["title"] for entry_id in work_ids],
        })
    return rows
