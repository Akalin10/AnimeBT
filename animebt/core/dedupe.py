from dataclasses import replace
from animebt.models import Resource
from animebt.models.title import normalized_title


def deduplicate(items: list[Resource]) -> list[Resource]:
    # Hash groups are formed first; hashless rows must not bridge conflicting hashes.
    groups = []
    hashes = {}
    for position, original in enumerate(items):
        if not original.info_hash:
            continue
        item = replace(original, sources=list(original.sources))
        if item.info_hash in hashes:
            group = groups[hashes[item.info_hash]]
            merge(group[0], item)
            group[1].append(item)
        else:
            hashes[item.info_hash] = len(groups)
            groups.append((item, [item], position))
    aliases = {}
    for index, (_, members, _) in enumerate(groups):
        for member in members:
            if member.size is not None:
                aliases.setdefault((normalized_title(member.title), member.size), set()).add(index)
    for position, original in enumerate(items):
        if original.info_hash:
            continue
        item = replace(original, sources=list(original.sources))
        key = (normalized_title(item.title), item.size)
        candidates = aliases.get(key, set()) if item.size is not None else set()
        if len(candidates) == 1:
            index = next(iter(candidates))
            group = groups[index]
            merge(group[0], item)
            groups[index] = (group[0], group[1], min(position, group[2]))
        else:
            groups.append((item, [item], position))
            if item.size is not None and not candidates:
                aliases.setdefault(key, set()).add(len(groups) - 1)
    return [r for r, _, _ in sorted(groups, key=lambda g: g[2])]


def merge(target, item):
    target.sources = list(dict.fromkeys(target.sources + item.sources))
    for name in ("magnet", "torrent_url", "info_hash", "publish_time"):
        if not getattr(target, name):
            setattr(target, name, getattr(item, name))
