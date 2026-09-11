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
from アフィリエイトリンク import アフィリエイトリンク作成, 商品, 商品リンク
from 投稿文生成 import 生成結果


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
        p = 商品("B0CHX3QBCH", "商品", "カテ", "特徴", "価格", "https://amzn.to/abc")
        self.assertEqual(商品リンク(p, "hangtime-22"), "https://amzn.to/abc")


class 文字数のテスト(unittest.TestCase):
    def test_日本語は2ポイント(self):
        self.assertEqual(X投稿.文字数ポイント("あいう"), 6)

    def test_英数字は1ポイント(self):
        self.assertEqual(X投稿.文字数ポイント("abc 12"), 6)

    def test_URLは23ポイント(self):
        self.assertEqual(X投稿.文字数ポイント("見て https://www.amazon.co.jp/dp/B0CHX3QBCH?tag=x-22"), 4 + 1 + 23)

    def test_組み立て(self):
        投稿 = X投稿.投稿文を組み立て("本文です", ["ガジェット", "イヤホン"], "https://amzn.to/abc")
        self.assertEqual(投稿, "【PR】本文です\n\n#ガジェット #イヤホン\nhttps://amzn.to/abc")

    def test_長すぎる本文は切り詰める(self):
        投稿 = X投稿.投稿文を組み立て("あ" * 200, ["タグ"], "https://amzn.to/abc")
        self.assertLessEqual(X投稿.文字数ポイント(投稿), 280)
        self.assertIn("…", 投稿)
        self.assertTrue(投稿.startswith("【PR】"))


class 商品選択のテスト(unittest.TestCase):
    def setUp(self):
        self.商品達 = [
            商品("B000000001", "A", "c", "f", "p"),
            商品("B000000002", "B", "c", "f", "p"),
            商品("B000000003", "C", "c", "f", "p"),
        ]
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
            "ASIN,商品名,カテゴリ,特徴,価格帯,短縮URL\nB0CHX3QBCH,テスト商品,ガジェット,軽い,千円,\n",
            encoding="utf-8",
        )
        (d / "投稿履歴.json").write_text("[]", encoding="utf-8")
        self.履歴 = d / "投稿履歴.json"
        self.patches = [
            mock.patch.object(自動投稿, "商品リストファイル", d / "商品リスト.csv"),
            mock.patch.object(自動投稿, "投稿履歴ファイル", self.履歴),
            mock.patch.object(自動投稿, "投稿文を生成", return_value=生成結果("いい感じの商品でした", ["ガジェット"])),
            mock.patch.dict("os.environ", {"AMAZON_ASSOCIATE_TAG": "hangtime-22", "DRY_RUN": ""}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_ドライランは投稿しない(self):
        with mock.patch.object(自動投稿, "Xに投稿") as 投稿:
            self.assertEqual(自動投稿.実行(dry_run=True, asin=None), 0)
            投稿.assert_not_called()
        self.assertEqual(json.loads(self.履歴.read_text(encoding="utf-8")), [])

    def test_本番は投稿して履歴を保存(self):
        with mock.patch.object(自動投稿, "Xに投稿", return_value="12345") as 投稿:
            self.assertEqual(自動投稿.実行(dry_run=False, asin=None), 0)
            投稿.assert_called_once()
            全文 = 投稿.call_args.args[0]
        self.assertTrue(全文.startswith("【PR】いい感じの商品でした"))
        self.assertIn("https://www.amazon.co.jp/dp/B0CHX3QBCH?tag=hangtime-22", 全文)
        履歴 = json.loads(self.履歴.read_text(encoding="utf-8"))
        self.assertEqual(len(履歴), 1)
        self.assertEqual(履歴[0]["asin"], "B0CHX3QBCH")
        self.assertEqual(履歴[0]["投稿ID"], "12345")


if __name__ == "__main__":
    unittest.main()
