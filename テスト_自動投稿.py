"""ユニットテスト: python -m unittest テスト_自動投稿 -v"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import X投稿
import 自動投稿
import 投稿文生成
from アフィリエイトリンク import アフィリエイトリンク作成, 商品, 商品リンク
from 投稿文生成 import 生成結果, 投稿候補


class アフィリエイトリンクのテスト(unittest.TestCase):
    def test_標準リンク(self):
        self.assertEqual(
            アフィリエイトリンク作成("b0chx3qbch", "hangtime-22"),
            "https://www.amazon.co.jp/dp/B0CHX3QBCH?tag=hangtime-22&linkCode=ll1",
        )

    def test_不正なASIN(self):
        with self.assertRaises(ValueError):
            アフィリエイトリンク作成("abc", "hangtime-22")

    def test_タグ未設定(self):
        with self.assertRaises(ValueError):
            アフィリエイトリンク作成("B0CHX3QBCH", "")

    def test_短縮URL優先(self):
        p = 商品("B0CHX3QBCH", "商品", 短縮URL="https://amzn.to/abc")
        self.assertEqual(商品リンク(p, "hangtime-22"), "https://amzn.to/abc")


class 文字数のテスト(unittest.TestCase):
    def test_日本語は2ポイント(self):
        self.assertEqual(X投稿.文字数ポイント("あいう"), 6)

    def test_英数字は1ポイント(self):
        self.assertEqual(X投稿.文字数ポイント("abc 12"), 6)

    def test_URLは23ポイント(self):
        self.assertEqual(X投稿.文字数ポイント("見て https://www.amazon.co.jp/dp/B0CHX3QBCH?tag=x-22"), 4 + 1 + 23)

    def test_本文の組み立て(self):
        投稿 = X投稿.本文を組み立て("本文です", ["美容", "スキンケア"])
        self.assertEqual(投稿, "本文です\n\n#美容 #スキンケア #PR")

    def test_PRタグは重複しない(self):
        投稿 = X投稿.本文を組み立て("本文です", ["美容", "PR"])
        self.assertEqual(投稿.count("#PR"), 1)

    def test_長すぎる本文は切り詰める(self):
        投稿 = X投稿.本文を組み立て("あ" * 200, ["タグ"])
        self.assertLessEqual(X投稿.文字数ポイント(投稿), 280)
        self.assertIn("…", 投稿)
        self.assertTrue(投稿.endswith("#PR"))

    def test_リンク投稿の組み立て(self):
        投稿 = X投稿.リンク投稿を組み立て("ここからチェックできるよ👇", "https://amzn.to/abc")
        self.assertEqual(投稿, "ここからチェックできるよ👇\n【PR】\nhttps://amzn.to/abc")

    def test_リプライとして投稿(self):
        client = mock.Mock()
        client.create_tweet.return_value = mock.Mock(data={"id": 99})
        self.assertEqual(X投稿.Xに投稿("本文", 返信先ID="12", client=client), "99")
        client.create_tweet.assert_called_once_with(text="本文", in_reply_to_tweet_id="12")


class 生成のテスト(unittest.TestCase):
    def test_プロンプトに変数が入る(self):
        p = 商品("B0CHX3QBCH", "テスト美容液", ジャンル="女性の美容", ターゲット="アラサーでニキビに悩む女性", 口調="お姉さん系", 特徴="低刺激")
        文 = 投稿文生成.プロンプトを組み立て(p, ["前回の投稿"])
        for 語 in ["女性の美容", "アラサーでニキビに悩む女性", "テスト美容液", "お姉さん系", "低刺激", "前回の投稿"]:
            self.assertIn(語, 文)
        self.assertNotIn("{ジャンル}", 文)

    def test_応答を解釈して最良を選ぶ(self):
        応答 = json.dumps(
            {
                "ターゲットの本音の悩み": ["自分だけ肌が汚い"],
                "候補": [
                    {"切り口": "共感型", "本文": "A", "ハッシュタグ": ["#美容"], "誘導文": "見てね", "伸びる確率": 60,
                     "採点": {"共感度": 20, "具体性": 10, "クリック誘導": 15, "拡散性": 15}, "採点理由": "r"},
                    {"切り口": "体験談型", "本文": "B", "ハッシュタグ": ["美容"], "誘導文": "見てね", "伸びる確率": 85,
                     "採点": {"共感度": 25, "具体性": 20, "クリック誘導": 20, "拡散性": 20}, "採点理由": "r"},
                ],
            },
            ensure_ascii=False,
        )
        結果 = 投稿文生成.応答を解釈(応答)
        self.assertEqual(len(結果.候補), 2)
        self.assertEqual(結果.最良.本文, "B")
        self.assertEqual(結果.候補[0].ハッシュタグ, ["美容"])
        self.assertEqual(結果.本音の悩み, ["自分だけ肌が汚い"])

    def test_候補なしはエラー(self):
        with self.assertRaises(RuntimeError):
            投稿文生成.応答を解釈('{"ターゲットの本音の悩み": [], "候補": []}')


class 商品選択のテスト(unittest.TestCase):
    def setUp(self):
        self.商品達 = [商品("B000000001", "A"), 商品("B000000002", "B"), 商品("B000000003", "C")]
        self.今 = datetime(2026, 9, 11, 12, 0, tzinfo=timezone(timedelta(hours=9)))

    def test_未投稿を優先(self):
        履歴 = [{"asin": "B000000001", "投稿日時": (self.今 - timedelta(days=1)).isoformat()}]
        self.assertEqual(自動投稿.次の商品を選ぶ(self.商品達, 履歴, 7, self.今).asin, "B000000002")

    def test_最も古い投稿を選ぶ(self):
        履歴 = [
            {"asin": "B000000001", "投稿日時": (self.今 - timedelta(days=10)).isoformat()},
            {"asin": "B000000002", "投稿日時": (self.今 - timedelta(days=30)).isoformat()},
            {"asin": "B000000003", "投稿日時": (self.今 - timedelta(days=20)).isoformat()},
        ]
        self.assertEqual(自動投稿.次の商品を選ぶ(self.商品達, 履歴, 7, self.今).asin, "B000000002")

    def test_全て最近投稿済みならエラー(self):
        履歴 = [{"asin": p.asin, "投稿日時": (self.今 - timedelta(days=1)).isoformat()} for p in self.商品達]
        with self.assertRaises(RuntimeError):
            自動投稿.次の商品を選ぶ(self.商品達, 履歴, 7, self.今)


class 実行フローのテスト(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        (d / "商品リスト.csv").write_text(
            "ASIN,商品名,ジャンル,ターゲット,口調,特徴,短縮URL\n"
            "B0CHX3QBCH,テスト商品,美容,アラサー女性,お姉さん系,軽い,\n",
            encoding="utf-8",
        )
        (d / "投稿履歴.json").write_text("[]", encoding="utf-8")
        self.履歴 = d / "投稿履歴.json"
        結果 = 生成結果(
            候補=[
                投稿候補("共感型", "いまいちな方", ["美容"], "見てね", 40),
                投稿候補("体験談型", "いい感じの商品でした", ["美容", "スキンケア"], "ここからチェックできるよ👇", 80,
                        {"共感度": 20, "具体性": 20, "クリック誘導": 20, "拡散性": 20}, "具体的"),
            ]
        )
        self.patches = [
            mock.patch.object(自動投稿, "商品リストファイル", d / "商品リスト.csv"),
            mock.patch.object(自動投稿, "投稿履歴ファイル", self.履歴),
            mock.patch.object(自動投稿, "投稿文を生成", return_value=結果),
            mock.patch.dict("os.environ", {"AMAZON_ASSOCIATE_TAG": "hangtime-22", "DRY_RUN": ""}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_ドライランは投稿しない(self):
        with mock.patch.object(自動投稿, "スレッド投稿") as 投稿:
            self.assertEqual(自動投稿.実行(dry_run=True, asin=None), 0)
            投稿.assert_not_called()
        self.assertEqual(json.loads(self.履歴.read_text(encoding="utf-8")), [])

    def test_本番は最良候補をスレッド投稿して履歴を保存(self):
        with mock.patch.object(自動投稿, "スレッド投稿", return_value=("12345", "12346")) as 投稿:
            self.assertEqual(自動投稿.実行(dry_run=False, asin=None), 0)
            投稿.assert_called_once()
            本文投稿, リンク投稿 = 投稿.call_args.args
        self.assertEqual(本文投稿, "いい感じの商品でした\n\n#美容 #スキンケア #PR")
        self.assertEqual(
            リンク投稿,
            "ここからチェックできるよ👇\n【PR】\nhttps://www.amazon.co.jp/dp/B0CHX3QBCH?tag=hangtime-22&linkCode=ll1",
        )
        履歴 = json.loads(self.履歴.read_text(encoding="utf-8"))
        self.assertEqual(len(履歴), 1)
        self.assertEqual(履歴[0]["投稿ID"], "12345")
        self.assertEqual(履歴[0]["リンク投稿ID"], "12346")
        self.assertEqual(履歴[0]["伸びる確率"], 80)
        self.assertEqual(len(履歴[0]["不採用候補"]), 1)


if __name__ == "__main__":
    unittest.main()
