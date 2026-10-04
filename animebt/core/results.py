from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime


def publication_date(value):
    if not value:
        return None
    try:
        try:
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone(timedelta(hours=8)))
        return date.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def display_date(value):
    date = publication_date(value)
    return date.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M") if date else "未知"


def filter_sort(resources, sources=None, resolution=None, codec=None, fansub=None, sort="time_desc"):
    filtered = []
    for resource in resources:
        metadata = resource.metadata
        if sources is not None and not set(resource.sources).intersection(sources):
            continue
        if resolution and metadata.resolution != resolution:
            continue
        if codec and metadata.codec != codec:
            continue
        if fansub and (metadata.fansub or "").casefold() != fansub.casefold():
            continue
        filtered.append(resource)
    if sort.startswith("time"):
        key = lambda r: publication_date(r.publish_time)
    elif sort.startswith("size"):
        key = lambda r: r.size
    elif sort in ("name_asc", "name_desc"):
        return sorted(filtered, key=lambda r: (r.metadata.anime_name.casefold(), r.title.casefold()),
                      reverse=sort == "name_desc")
    elif sort.rsplit("_", 1)[0] in ("episode", "resolution", "codec", "fansub", "sources"):
        import re
        field = sort.rsplit("_", 1)[0]
        def key(r):
            value = " / ".join(r.sources) if field == "sources" else getattr(r.metadata, field)
            if not value:
                return None
            return tuple((0, int(part)) if part.isdigit() else (1, part.casefold())
                         for part in re.split(r"(\d+)", value) if part)
    elif sort == "source":
        return sorted(filtered, key=lambda r: (min(r.sources, default=r.source).casefold(), r.title.casefold()))
    else:
        raise ValueError(f"未知排序: {sort}")
    known = [r for r in filtered if key(r) is not None]
    unknown = [r for r in filtered if key(r) is None]
    return sorted(known, key=key, reverse=sort.endswith("desc")) + unknown
