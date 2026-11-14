import html
import json
import re
import unittest

from animebt.gui.title_api import chat_payload, completion_content, endpoint_for, http_error
from animebt.gui.title_format import (
    FIELD_COLORS, align_model_fields, contrast, field_color, formatted_title, plain_title, validate_fields,
)


def fragment(title, kind, text):
    start = title.index(text)
    return {"kind": kind, "text": text, "start": start, "end": start + len(text)}


class DisplayFormatTest(unittest.TestCase):
    def test_field_order_exact_colors_and_omitted_missing_fields(self):
        title = "[1080p][简繁内封][HEVC][FLAC][WebRip][OVA][02][Anime 日本动画][LoliHouse][MKV]"
        values = [fragment(title, kind, text) for kind, text in (
            ("resolution", "1080p"), ("language", "简繁内封"), ("video", "HEVC"),
            ("audio", "FLAC"), ("source", "WebRip"), ("type", "OVA"),
            ("episode", "02"), ("anime", "Anime 日本动画"), ("group", "LoliHouse"), ("other", "MKV"),
        )]
        # Bare episode numbers require a preceding validated name.
        title = "[LoliHouse] Anime 日本动画 [02][OVA][WebRip][1080p][HEVC][FLAC][简繁内封][MKV]"
        values = [fragment(title, value["kind"], value["text"]) for value in values]
        fields = validate_fields(title, values)
        rendered = formatted_title(title, fields, False)
        self.assertEqual(html.unescape(re.sub("<[^>]+>", "", rendered)),
                         "[LoliHouse] [Anime 日本动画] [02] [OVA] [WebRip] [1080p] [HEVC] [FLAC] [简繁内封] [MKV]")
        self.assertEqual(re.findall(r"color:(#[0-9A-Fa-f]{6});", rendered), [field_color(kind, False) for kind in FIELD_COLORS])
        self.assertNotIn("background", rendered)
        self.assertNotIn("border", rendered)
        short = "Example Anime [1080p]"
        fields = validate_fields(short, [fragment(short, "anime", "Example Anime"), fragment(short, "resolution", "1080p")])
        self.assertEqual(re.sub("<[^>]+>", "", formatted_title(short, fields, True)), "[Example Anime] [1080p]")
        self.assertNotIn("未知", formatted_title(short, fields, True))

    def test_no_invented_values_wrong_types_or_ambiguous_positions(self):
        title = "🐟 [Anime 日本动画] [1080p] [1080p] <b>& tag"
        name = fragment(title, "anime", "Anime 日本动画")
        bad = [dict(name, text="Imaginary season"), dict(name, start=True),
               dict(name, kind="work_ids"), dict(name, kind=[]),
               fragment(title, "audio", "1080p"), dict(name, text="Anime", end=999)]
        self.assertEqual(validate_fields(title, bad), ())
        fixed = align_model_fields(title, [dict(name, start=0, end=4)])
        self.assertEqual(validate_fields(title, fixed), validate_fields(title, [name]))
        ambiguous = dict(fragment(title, "resolution", "1080p"), start=0, end=5)
        self.assertEqual(align_model_fields(title, [ambiguous]), [])
        self.assertEqual(validate_fields(title, [name, name]), ())
        rendered = formatted_title(title, validate_fields(title, [name]), True)
        self.assertIn("&lt;b&gt;&amp;", rendered)
        self.assertNotIn("<b>", rendered)
        extra = "Example Anime [HDR10+][AAC+][v2]"
        extra_fields = validate_fields(extra, [fragment(extra, "anime", "Example Anime")])
        self.assertIn("HDR10+ AAC+ v2", formatted_title(extra, extra_fields, False))
        self.assertEqual(formatted_title(title, (), True), html.escape(title))

    def test_mixed_language_ova_compound_tags_recover_exact_fragments(self):
        title = "【動漫國字幕組】[Re:從零開始的異世界生活][OVA][02][BDRip][HEVC_FLAC][1080P_Ma10P][簡繁外掛]"
        values = [fragment(title, kind, text) for kind, text in (
            ("group", "動漫國字幕組"), ("anime", "Re:從零開始的異世界生活"),
            ("type", "OVA"), ("episode", "02"), ("source", "BDRip"),
            ("video", "HEVC_FLAC"), ("resolution", "1080P_Ma10P"), ("language", "簡繁外掛"),
        )]
        # Simulate real model counting errors without permitting fuzzy recovery.
        values = [dict(value, start=value["start"] + 2, end=value["end"] + 2) for value in values]
        fields = validate_fields(title, align_model_fields(title, values))
        actual = {(field.kind, title[field.start:field.end]) for field in fields}
        self.assertLessEqual({("audio", "FLAC"), ("video", "HEVC"), ("resolution", "1080P"),
                              ("other", "Ma10P"), ("type", "OVA"), ("episode", "02")}, actual)
        self.assertNotIn(("video", "HEVC_FLAC"), actual)

    def test_colors_meet_aa_without_individual_field_backgrounds(self):
        from animebt.gui.title_spans import BACKGROUNDS
        for dark in (False, True):
            for kind in FIELD_COLORS:
                for background in (*BACKGROUNDS[int(dark)], "#454545" if dark else "#dbdbdb"):
                    self.assertGreaterEqual(contrast(field_color(kind, dark), background), 4.5, (dark, kind))

    def test_entities_are_decoded_once_then_html_escaped(self):
        title = "[Group&amp;Team] 日本动画 &amp; Anime &lt;img src=x&gt; [HEVC_FLAC]"
        fields = validate_fields(title, [fragment(title, "group", "Group&amp;Team"),
                                         fragment(title, "anime", "日本动画 &amp; Anime &lt;img src=x&gt;")])
        rich = formatted_title(title, fields, False)
        visible = html.unescape(re.sub("<[^>]+>", "", rich))
        self.assertIn("Group&Team", visible)
        self.assertIn("日本动画 & Anime <img src=x>", visible)
        self.assertNotIn("<img", rich)
        self.assertNotIn("&amp;amp;", rich)
        self.assertEqual(plain_title("&amp;amp; &amp; &#38; &#x26; &copy; &foo;"), "&amp; & & & © &foo;")
        partial = fragment(title, "other", "amp")
        self.assertEqual(validate_fields(title, [partial]), ())

    def test_misclassified_compound_fields_are_not_colored_as_a_name(self):
        title = "Anime 日本动画 HEVC AAC 1080p"
        self.assertEqual(validate_fields(title, [fragment(title, "anime", title)]), ())
        title = "Example Anime [HEVC_FLAC][CHS]"
        fields = validate_fields(title, align_model_fields(title, [
            fragment(title, "anime", "Example Anime"), fragment(title, "other", "HEVC_FLAC"),
            fragment(title, "language", "CHS"),
        ]))
        self.assertEqual([(f.kind, title[f.start:f.end]) for f in fields],
                         [("anime", "Example Anime"), ("video", "HEVC"), ("audio", "FLAC"), ("language", "CHS")])


class APIFormatTest(unittest.TestCase):
    def test_endpoints_and_provider_payload(self):
        for base in ("https://api.deepseek.com", "https://api.deepseek.com/v1",
                     "https://api.deepseek.com/v1/chat/completions"):
            endpoint = endpoint_for(base)
            self.assertEqual(endpoint.count("/chat/completions"), 1)
            payload = chat_payload(endpoint, "deepseek-flash", [])
            self.assertEqual(payload["thinking"], {"type": "disabled"})
            self.assertEqual(payload["response_format"], {"type": "json_object"})
        for base in ("https://user:secret@test.invalid", "https://test.invalid/?key=secret",
                     "http://remote.invalid/v1", "https://test.invalid:99999", "not a URL"):
            self.assertEqual(endpoint_for(base), "")
        payload = chat_payload(endpoint_for("http://localhost:1234/v1"), "local-model", [])
        self.assertNotIn("thinking", payload)
        self.assertNotIn("response_format", payload)

    def test_errors_are_distinct_and_do_not_echo_credentials(self):
        for code, expected in ((401, "Key"), (402, "余额"), (403, "权限"), (404, "路径"),
                               (429, "限流"), (503, "服务端"), (400, "参数")):
            message = http_error(code, b'{"error":{"message":"secret-credential"}}')
            self.assertIn(expected, message)
            self.assertIn(str(code), message)
            self.assertNotIn("secret-credential", message)
        self.assertIn("模型不存在", http_error(404, b'{"error":{"code":"model_not_found"}}'))
        self.assertIn("配额", http_error(429, b'{"error":{"code":"insufficient_quota"}}'))

    def test_structured_response_validation(self):
        def response(content, reason="stop"):
            return json.dumps({"choices": [{"message": {"content": content}, "finish_reason": reason}]}).encode()
        self.assertEqual(completion_content(response('```json\n{"items":[]}\n```')), {"items": []})
        for content in ("", "[]", "not JSON"):
            with self.assertRaises(ValueError):
                completion_content(response(content))
        with self.assertRaisesRegex(ValueError, "截断"):
            completion_content(response('{"items":[]}', "length"))
        for body in (b'[]', b'{}', b'{"choices":[{}]}', b'{"choices":[null]}'):
            with self.assertRaises(ValueError):
                completion_content(body)
