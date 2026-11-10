import json
import unittest

try:
    from PySide6.QtCore import QByteArray, QObject, Signal
    from PySide6.QtNetwork import QNetworkReply
except ModuleNotFoundError as error:
    if error.name != "PySide6":
        raise
    raise unittest.SkipTest("GUI dependencies are optional") from error

from animebt.gui.bangumi import BangumiSearch, subject_summary


class PendingReply(QObject):
    finished = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.aborted = False
        self.code = 200
        self.body = {"data": []}

    def abort(self):
        self.aborted = True

    def attribute(self, _attribute):
        return self.code

    def error(self):
        return QNetworkReply.NetworkError.NoError

    def readAll(self):
        return QByteArray(json.dumps(self.body).encode("utf-8"))


class ControlledNetwork(QObject):
    def __init__(self):
        super().__init__()
        self.replies = []
        self.keywords = []
        self.offsets = []
        self.relations = []

    def post(self, request, body):
        reply = PendingReply(self)
        self.replies.append(reply)
        self.keywords.append(json.loads(body)["keyword"])
        self.offsets.append(request.url().query())
        return reply

    def get(self, request):
        reply = PendingReply(self)
        self.replies.append(reply)
        self.relations.append(request.url().path())
        return reply


class BangumiSearchTest(unittest.TestCase):
    anchor = {
        "id": 55770, "name_cn": "进击的巨人", "name": "進撃の巨人",
        "infobox": [{"key": "别名", "value": [
            {"v": "進擊的巨人"}, {"v": "Shingeki no Kyojin"}, {"v": "Attack on Titan"}, {"v": "Another alias"},
        ]}],
    }

    @staticmethod
    def finish(reply, body):
        reply.body = body
        reply.finished.emit()

    def test_multilingual_supplements_require_evidence_and_keep_stable_id_order(self):
        network = ControlledNetwork()
        search = BangumiSearch(manager=network)
        search.search("  进击的巨人  ")
        search.search("进击的巨人")
        self.assertEqual(network.keywords, ["进击的巨人"])
        self.finish(network.replies[0], {"data": [self.anchor, self.anchor, {"id": 80993, "name": "进击的巨人 OAD"}]})
        self.assertEqual(network.keywords, ["进击的巨人", "進撃の巨人", "Shingeki no Kyojin", "Attack on Titan"])
        self.assertEqual(network.relations, ["/v0/subjects/55770/subjects"])
        self.finish(network.replies[3], {"data": [{"id": 15, "name": "零食攻击"},
                                                  {"id": 16, "name": "联动动画"},
                                                  {"id": 141781, "name": "进击！巨人中学校"}]})
        self.finish(network.replies[2], {"data": [{"id": 101267, "name": "剧场版 后篇"},
                                                  {"id": 17, "name": "同名关键词衍生"}]})
        self.finish(network.replies[4], [{"id": 141781, "type": 2, "relation": "不同世界观"},
                                         {"id": 101267, "type": 2, "relation": "总集篇"},
                                         {"id": 16, "type": 2, "relation": "联动"},
                                         {"id": 17, "type": 4, "relation": "衍生"}])
        self.assertEqual(search.status, "loading")
        self.finish(network.replies[1], {"data": [{"id": 101267, "name": "剧场版 后篇"},
                                                  {"id": 80993, "name": "不同来源名称"}]})
        self.assertEqual([row["id"] for row in search.results], [55770, 80993, 101267, 141781])
        self.assertEqual(search.primaryCount, 2)
        self.assertEqual(search.results[1]["title"], "进击的巨人 OAD")
        search.search("进击的巨人")
        self.assertEqual(len(network.replies), 5)
        self.assertEqual(len(search.results), 4)

    def test_supplements_are_capped_and_unavailable_relations_keep_only_exact_matches(self):
        network = ControlledNetwork()
        search = BangumiSearch(manager=network)
        search.search("进击的巨人")
        self.finish(network.replies[0], {"data": [self.anchor]})
        network.replies[4].code = 503
        self.finish(network.replies[4], [])
        self.finish(network.replies[1], {"data": [{"id": n, "name": "进击的巨人"} for n in range(1, 15)]})
        self.finish(network.replies[2], {"data": [{"id": 77, "name": "进击的巨人 仅包含名称"}]})
        self.finish(network.replies[3], {"data": []})
        self.assertEqual([row["id"] for row in search.results], [55770, *range(1, 9)])
        search.search("进击的巨人")
        self.assertEqual(len(network.replies), 6)

    def test_second_original_page_precedes_supplements_and_deduplicates_overlap(self):
        network = ControlledNetwork()
        search = BangumiSearch(manager=network)
        search.search("进击的巨人")
        primary = [self.anchor, *({"id": n, "name": f"条目 {n}"} for n in range(1, 20))]
        self.finish(network.replies[0], {"data": primary, "total": 22})
        self.assertIn("offset=20", network.offsets[1])
        self.assertEqual(search.status, "loading")
        self.assertEqual([row["id"] for row in search.candidates], [55770, *range(1, 20)])
        search.select(55770)
        self.assertEqual(search.selected["id"], 55770)
        sequel = {"id": 508708, "name": "剧场版 进击的巨人 完结篇"}
        self.finish(network.replies[2], {"data": [sequel, {"id": 100, "name": "进击的巨人"}]})
        self.finish(network.replies[3], {"data": []})
        self.finish(network.replies[4], {"data": []})
        self.finish(network.replies[5], [{"id": 508708, "type": 2, "relation": "总集篇"}])
        self.assertEqual(search.status, "loading")
        self.finish(network.replies[1], {"data": [primary[-1], sequel, {"id": 200, "name": "四格动画"}]})
        self.assertEqual(search.primaryCount, 22)
        self.assertEqual([row["id"] for row in search.results[-3:]], [508708, 200, 100])
        self.assertEqual(search.candidates, search.results)

    def test_cancel_during_supplement_keeps_primary_and_ignores_all_late_replies(self):
        network = ControlledNetwork()
        search = BangumiSearch(manager=network)
        search.search("进击的巨人")
        self.finish(network.replies[0], {"data": [self.anchor]})
        search.cancel()
        self.assertEqual(search.status, "ready")
        self.assertEqual([row["id"] for row in search.results], [55770])
        self.assertTrue(all(reply.aborted for reply in network.replies[1:]))
        search.search("另一部")
        self.finish(network.replies[-1], {"data": [{"id": 22, "name": "另一部"}]})
        for reply in network.replies[1:5]:
            self.finish(reply, {"data": [{"id": 100, "name": "进击的巨人"}]})
        self.assertEqual([row["id"] for row in search.results], [22])
        search.search("取消首轮")
        search.cancel()
        self.assertEqual(search.status, "cancelled")
        self.assertTrue(network.replies[-1].aborted)

    def test_cover_prefers_largest_variant_and_keeps_unique_fallbacks(self):
        large = "https://lain.bgm.tv/pic/cover/l/example.jpg"
        medium = "https://lain.bgm.tv/r/800/pic/cover/l/example.jpg"
        row = {"id": 1, "name": "Anime", "images": {
            "common": "https://other.invalid/pic/cover/example.jpg",
            "medium": medium,
            "large": large,
            "small": medium,
        }}
        summary = subject_summary(row)
        self.assertEqual(summary["cover"], large)
        self.assertEqual(summary["coverAlternatives"], [medium])
        del row["images"]["large"]
        self.assertEqual(subject_summary(row)["cover"], medium)

    def test_late_reply_cannot_replace_results_or_selection(self):
        network = ControlledNetwork()
        search = BangumiSearch(manager=network)
        search.search("旧请求")
        search.search("新请求")
        older, newer = network.replies
        self.assertTrue(older.aborted)

        newer.body = {"data": [{"id": 2, "name": "新条目"}], "total": 1}
        newer.finished.emit()
        search.select(2)
        older.body = {"data": [{"id": 1, "name": "旧条目"}], "total": 1}
        older.finished.emit()

        self.assertEqual(search.status, "ready")
        self.assertEqual([row["id"] for row in search.results], [2])
        self.assertEqual(search.selected["id"], 2)

    def test_http_failure_clears_results_and_reports_status(self):
        network = ControlledNetwork()
        search = BangumiSearch(manager=network)
        search.search("动画")
        reply = network.replies[-1]
        reply.code = 503
        reply.finished.emit()

        self.assertEqual(search.status, "error")
        self.assertIn("503", search.error)
        self.assertEqual(search.results, [])
