from hashlib import sha1
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import httpx

try:
    from animebt.gui.resource_actions import failure_reason, fetch_action, valid_magnet
except ModuleNotFoundError as error:
    if error.name != "PySide6":
        raise
    raise unittest.SkipTest("GUI dependencies are optional") from error


INFO = b"d6:lengthi1e4:name4:test12:piece lengthi16384e6:pieces20:" + sha1(b"x").digest() + b"e"
TORRENT = b"d4:info" + INFO + b"e"
DIGEST = sha1(INFO).hexdigest()
ROW = {"title": "Test release", "torrent_url": "https://example.test/test.torrent"}


class MagnetValidationTest(unittest.TestCase):
    def test_accepts_btih_and_btmh_and_rejects_invalid_uri(self):
        self.assertTrue(valid_magnet(f"magnet:?xt=urn:btih:{DIGEST}&dn=Test%20release", DIGEST))
        self.assertTrue(valid_magnet("magnet:?xt=urn:btmh:1220" + "a" * 64))
        self.assertFalse(valid_magnet("https://example.test/?xt=urn:btih:" + DIGEST))
        self.assertFalse(valid_magnet("magnet:?xt=urn:btih:invalid"))
        self.assertFalse(valid_magnet(f"magnet:?xt=urn:btih:{DIGEST}", "a" * 40))


class TorrentActionTest(unittest.IsolatedAsyncioTestCase):
    def client_with_response(self, response):
        client = httpx.AsyncClient
        transport = httpx.MockTransport(lambda _: response)
        return patch("animebt.gui.resource_actions.httpx.AsyncClient",
                     side_effect=lambda **options: client(transport=transport, **options))

    async def test_resolves_torrent_and_refuses_mismatched_hash(self):
        with self.client_with_response(httpx.Response(200, content=TORRENT)):
            self.assertEqual(await fetch_action(ROW), f"magnet:?xt=urn:btih:{DIGEST}")
        with self.client_with_response(httpx.Response(200, content=TORRENT)):
            with self.assertRaisesRegex(ValueError, "infohash"):
                await fetch_action(dict(ROW, info_hash="a" * 40))

    async def test_saves_torrent_and_does_not_overwrite(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "anime"
            with self.client_with_response(httpx.Response(200, content=TORRENT)):
                result = await fetch_action(ROW, destination)
            saved = Path(result)
            self.assertEqual(saved.suffix, ".torrent")
            self.assertEqual(saved.read_bytes(), TORRENT)
            with self.client_with_response(httpx.Response(200, content=TORRENT)):
                with self.assertRaises(FileExistsError):
                    await fetch_action(ROW, destination)
            self.assertEqual(saved.read_bytes(), TORRENT)

    async def test_http_error_and_invalid_file_have_specific_reasons(self):
        with self.client_with_response(httpx.Response(503)):
            with self.assertRaises(httpx.HTTPStatusError) as failed:
                await fetch_action(ROW)
        self.assertIn("HTTP 503", failure_reason(failed.exception))
        with self.client_with_response(httpx.Response(200, content=b"<html>error</html>")):
            with self.assertRaises(ValueError) as failed:
                await fetch_action(ROW)
        self.assertIn("无效", failure_reason(failed.exception))
