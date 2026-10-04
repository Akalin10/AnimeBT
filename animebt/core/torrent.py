import hashlib


def torrent_hash(data: bytes) -> str:
    """Hash the original bencoded info bytes (never re-encode them)."""
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("种子文件超过 8 MiB")

    def parse(pos, depth=0):
        if depth > 100 or pos >= len(data):
            raise ValueError("无效种子文件")
        token = data[pos:pos + 1]
        if token == b"i":
            end = data.index(b"e", pos)
            int(data[pos + 1:end])
            return end + 1
        if token in (b"l", b"d"):
            current = pos + 1
            while current < len(data) and data[current:current + 1] != b"e":
                current = parse(current, depth + 1)
            if current >= len(data):
                raise ValueError("种子文件不完整")
            return current + 1
        colon = data.index(b":", pos)
        length = int(data[pos:colon])
        end = colon + 1 + length
        if length < 0 or end > len(data):
            raise ValueError("无效字节串")
        return end

    if not data.startswith(b"d"):
        raise ValueError("无效种子文件")
    pos = 1
    digest = None
    while pos < len(data) and data[pos:pos + 1] != b"e":
        colon = data.index(b":", pos)
        key_end = parse(pos)
        key = data[colon + 1:key_end]
        end = parse(key_end)
        if key == b"info":
            if data[key_end:key_end + 1] != b"d" or digest:
                raise ValueError("无效 info 字典")
            digest = hashlib.sha1(data[key_end:end]).hexdigest()
        pos = end
    if digest is None or pos != len(data) - 1 or data[pos:] != b"e":
        raise ValueError("种子缺少 info 或包含多余数据")
    return digest


async def resolve_magnet(resource, client):
    if resource.magnet:
        return resource.magnet
    if not resource.torrent_url:
        raise ValueError("此资源没有 Magnet 或种子链接")
    content = await fetch_torrent(resource.torrent_url, client)
    resource.info_hash = torrent_hash(content)
    resource.magnet = f"magnet:?xt=urn:btih:{resource.info_hash}"
    return resource.magnet


async def fetch_torrent(url, client):
    if not url:
        raise ValueError("此资源没有种子链接")
    content = bytearray()
    async with client.stream("GET", url) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            content.extend(chunk)
            if len(content) > 8 * 1024 * 1024:
                raise ValueError("种子文件超过 8 MiB")
    return bytes(content)


async def save_torrent(resource, path, client):
    """Validate a fetched torrent before saving; never overwrite an existing file."""
    from pathlib import Path
    target = Path(path).expanduser()
    if target.suffix.lower() != ".torrent":
        target = target.with_name(target.name + ".torrent")
    content = await fetch_torrent(resource.torrent_url, client)
    digest = torrent_hash(content)
    if resource.info_hash and digest != resource.info_hash:
        raise ValueError("种子 infohash 与搜索结果不一致")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(content)
    return target
