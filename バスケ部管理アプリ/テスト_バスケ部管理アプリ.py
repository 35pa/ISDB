"""バスケ部管理アプリのテスト。

実行: python -m unittest テスト_バスケ部管理アプリ -v   （バスケ部管理アプリ フォルダで）
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import スキル診断
import 集計
from サーバー import サーバーを作成


# ---------- 純粋関数 ----------


class スキル診断のテスト(unittest.TestCase):
    def test_レベル判定(self):
        self.assertEqual(スキル診断.レベル判定(None), "未診断")
        self.assertEqual(スキル診断.レベル判定(39), "初級")
        self.assertEqual(スキル診断.レベル判定(40), "中級")
        self.assertEqual(スキル診断.レベル判定(69), "中級")
        self.assertEqual(スキル診断.レベル判定(70), "上級")

    def test_総合値は入力された評価元だけで重み付き平均(self):
        self.assertIsNone(スキル診断.総合値({}))
        self.assertEqual(スキル診断.総合値({"コーチ": 60}), 60)
        # コーチ0.5・自己0.2 → (60*0.5 + 90*0.2) / 0.7 = 68.57
        self.assertEqual(スキル診断.総合値({"コーチ": 60, "自己評価": 90}), 69)
        self.assertEqual(スキル診断.総合値({"コーチ": 50, "スタッツ": 80, "自己評価": 20}), 53)

    def test_スタッツから能力値(self):
        self.assertIsNone(スキル診断.スタッツから能力値("シュート", [{"fga": 20, "fgm": 10}]))  # 1試合では算出しない
        良い = [{"fga": 10, "fgm": 6, "tpm": 1, "fta": 0, "ftm": 0}] * 3
        悪い = [{"fga": 10, "fgm": 2, "tpm": 0, "fta": 0, "ftm": 0}] * 3
        self.assertGreater(スキル診断.スタッツから能力値("シュート", 良い), スキル診断.スタッツから能力値("シュート", 悪い))
        self.assertEqual(スキル診断.スタッツから能力値("リバウンド", [{"rebounds": 10}] * 2), 95)
        self.assertIsNone(スキル診断.スタッツから能力値("フィジカル", [{"points": 10}] * 5))

    def test_優先順位は総合値の低い順に3つ(self):
        カテゴリ = [{"id": i, "name": f"S{i}"} for i in range(1, 6)]
        評価 = {1: {"コーチ": 80}, 2: {"コーチ": 30}, 3: {"コーチ": 50}, 4: {"コーチ": 20}}
        結果 = {d["category_id"]: d for d in スキル診断.スキル診断(カテゴリ, 評価, [])}
        self.assertEqual([結果[i]["priority"] for i in (4, 2, 3, 1, 5)], [1, 2, 3, None, None])
        self.assertEqual(結果[5]["level"], "未診断")

    def test_自己評価との差の警告(self):
        結果 = スキル診断.スキル診断([{"id": 1, "name": "パス"}], {1: {"コーチ": 30, "自己評価": 80}}, [])
        self.assertTrue(結果[0]["gap_warning"])
        self.assertEqual(結果[0]["gap"], 50)

    def _ドリル(self):
        return [
            {"id": 3, "level": "中級", "step_no": 1, "next_step_id": 4},
            {"id": 1, "level": "初級", "step_no": 1, "next_step_id": 2},
            {"id": 4, "level": "上級", "step_no": 1, "next_step_id": None},
            {"id": 2, "level": "初級", "step_no": 2, "next_step_id": 3},
        ]

    def test_ドリルは次ステップのつながり順(self):
        self.assertEqual([d["id"] for d in スキル診断.ドリルを段階順に並べる(self._ドリル())], [1, 2, 3, 4])

    def test_循環参照でも全ドリルを返す(self):
        ドリル = [{"id": 1, "level": "初級", "step_no": 1, "next_step_id": 2}, {"id": 2, "level": "初級", "step_no": 2, "next_step_id": 1}]
        self.assertEqual(sorted(d["id"] for d in スキル診断.ドリルを段階順に並べる(ドリル)), [1, 2])

    def test_現在のステップ(self):
        並び = スキル診断.ドリルを段階順に並べる(self._ドリル())
        self.assertEqual(スキル診断.現在のステップ(並び, {}, "未診断")["id"], 1)
        self.assertEqual(スキル診断.現在のステップ(並び, {1: "完了"}, "初級")["id"], 2)
        # 中級と診断されたら初級は飛ばす
        self.assertEqual(スキル診断.現在のステップ(並び, {}, "中級")["id"], 3)
        # レベルをクリアしたら次のレベルへ
        self.assertEqual(スキル診断.現在のステップ(並び, {1: "完了", 2: "完了"}, "初級")["id"], 3)
        self.assertIsNone(スキル診断.現在のステップ(並び, {1: "完了", 2: "完了", 3: "完了", 4: "完了"}, "初級"))
        # コーチの上書き指定が優先
        self.assertEqual(スキル診断.現在のステップ(並び, {}, "中級", 上書きドリルID=1)["id"], 1)
        self.assertEqual(スキル診断.現在のステップ(並び, {1: "完了"}, "中級", 上書きドリルID=1)["id"], 3)


class 集計のテスト(unittest.TestCase):
    def test_スタッツ集計と成功率(self):
        行 = [
            {"id": 1, "date": "2026-05-01", "points": 10, "fgm": 4, "fga": 10, "tpm": 1, "tpa": 3, "ftm": 1, "fta": 2, "zones": {"ゴール下": {"a": 4, "m": 3}}},
            {"id": 2, "date": "2026-05-08", "points": 6, "fgm": 3, "fga": 5, "tpm": 0, "tpa": 1, "ftm": 0, "fta": 0, "zones": json.dumps({"ゴール下": {"a": 2, "m": 1}})},
        ]
        結果 = 集計.スタッツを集計(行)
        self.assertEqual(結果["games"], 2)
        self.assertEqual(結果["averages"]["points"], 8)
        self.assertEqual(結果["fg_pct"], 46.7)
        ゴール下 = next(z for z in 結果["shot_chart"] if z["zone"] == "ゴール下")
        self.assertEqual((ゴール下["a"], ゴール下["m"], ゴール下["pct"]), (6, 4, 66.7))
        self.assertEqual([t["date"] for t in 結果["trend"]], ["2026-05-01", "2026-05-08"])

    def test_得点の検算(self):
        self.assertEqual(集計.得点を検算({"fgm": 5, "tpm": 2, "ftm": 3}), 2 * 3 + 3 * 2 + 3)

    def test_エリアの検証(self):
        with self.assertRaises(ValueError):
            集計.エリア内訳を検証({"どこか": {"a": 1, "m": 0}})
        with self.assertRaises(ValueError):
            集計.エリア内訳を検証({"ペイント": {"a": 1, "m": 2}})

    def test_成長記録カレンダー(self):
        結果 = 集計.成長記録カレンダー(
            2026, 2,
            [{"date": "2026-02-02", "title": "練習", "kind": "練習", "status": "出席"}, {"date": "2026-02-03", "title": "練習", "kind": "練習", "status": "欠席"}],
            [{"date": "2026-02-02", "title": "ドリル", "cleared": 1}],
            [{"id": 1, "date": "2026-02-03", "minutes": 30, "content": "自主練"}],
        )
        self.assertEqual(len(結果["days"]), 28)
        self.assertEqual(結果["days"][1]["level"], 2)
        self.assertEqual(結果["days"][2]["level"], 1)  # 欠席は数えない、自主練のみ
        self.assertEqual(結果["active_days"], 2)
        self.assertEqual(結果["longest_streak"], 2)
        self.assertEqual(結果["self_practice_minutes"], 30)


# ---------- API（実際にサーバーを起動して確認） ----------


class APIのテスト(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.一時 = tempfile.TemporaryDirectory()
        cls.サーバー, _ = サーバーを作成(Path(cls.一時.name) / "テスト.sqlite3", "127.0.0.1", 0, 静か=True)
        cls.基本 = f"http://127.0.0.1:{cls.サーバー.server_address[1]}"
        threading.Thread(target=cls.サーバー.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.サーバー.shutdown()
        cls.サーバー.server_close()
        cls.一時.cleanup()

    def 呼ぶ(self, メソッド, パス, 本文=None, トークン=None, 期待=200):
        データ = json.dumps(本文).encode() if 本文 is not None else None
        要求 = urllib.request.Request(self.基本 + urllib.parse.quote(パス, safe="/?=&%"), data=データ, method=メソッド)
        要求.add_header("Content-Type", "application/json")
        if トークン:
            要求.add_header("Authorization", f"Bearer {トークン}")
        try:
            with urllib.request.urlopen(要求) as 応答:
                状態, 結果 = 応答.status, json.loads(応答.read() or b"null")
        except urllib.error.HTTPError as エラー:
            状態, 結果 = エラー.code, json.loads(エラー.read() or b"null")
        self.assertEqual(状態, 期待, f"{メソッド} {パス} → {状態} {結果}")
        return 結果

    def チームを作る(self, 名前="テスト高校"):
        結果 = self.呼ぶ("POST", "/api/teams", {"team_name": 名前, "name": "監督", "login_id": "coach", "password": "password1"})
        return 結果["token"], 結果["team"]["code"]

    def 選手を追加(self, コーチ, コード, ログインID="player1", 名前="選手A"):
        結果 = self.呼ぶ("POST", "/api/members", {"name": 名前, "login_id": ログインID, "role": "player", "number": "4"}, コーチ)
        ログイン = self.呼ぶ("POST", "/api/login", {"team_code": コード, "login_id": ログインID, "password": 結果["initial_password"]})
        return 結果["member"]["id"], ログイン["token"]

    def test_静的ファイルとセキュリティヘッダー(self):
        with urllib.request.urlopen(self.基本 + "/") as 応答:
            self.assertIn("バスケ部ノート", 応答.read().decode())
            self.assertIn("default-src 'self'", 応答.headers["Content-Security-Policy"])
        with self.assertRaises(urllib.error.HTTPError) as 例外:
            urllib.request.urlopen(self.基本 + "/..%2F..%2F" + urllib.parse.quote("サーバー.py"))
        self.assertEqual(例外.exception.code, 404)

    def test_ログインとパスワード(self):
        コーチ, コード = self.チームを作る()
        self.呼ぶ("GET", "/api/me", 期待=401)
        self.呼ぶ("POST", "/api/login", {"team_code": コード, "login_id": "coach", "password": "違う"}, 期待=401)
        結果 = self.呼ぶ("POST", "/api/login", {"team_code": コード.lower(), "login_id": "COACH", "password": "password1"})
        self.assertEqual(結果["user"]["role"], "coach")
        新 = self.呼ぶ("PUT", "/api/me/password", {"current": "password1", "new": "newpass99"}, 結果["token"])
        self.呼ぶ("GET", "/api/me", トークン=結果["token"], 期待=401)  # 古いセッションは無効
        self.呼ぶ("GET", "/api/me", トークン=新["token"])
        self.呼ぶ("POST", "/api/logout", {}, 新["token"])
        self.呼ぶ("GET", "/api/me", トークン=新["token"], 期待=401)
        self.assertEqual(コーチ != 新["token"], True)

    def test_チームの初期データ(self):
        コーチ, _ = self.チームを作る()
        self.assertEqual(len(self.呼ぶ("GET", "/api/skill-categories", トークン=コーチ)), 6)
        self.assertGreater(len(self.呼ぶ("GET", "/api/drills", トークン=コーチ)), 30)
        self.assertGreater(len(self.呼ぶ("GET", "/api/menus", トークン=コーチ)), 5)
        self.assertTrue(any(t["is_template"] for t in self.呼ぶ("GET", "/api/tactics", トークン=コーチ)))

    def test_他チームのデータは見えない(self):
        コーチA, コードA = self.チームを作る("A高校")
        コーチB, _ = self.チームを作る("B高校")
        選手A, _ = self.選手を追加(コーチA, コードA)
        予定 = self.呼ぶ("POST", "/api/events", {"kind": "練習", "date": "2026-06-01"}, コーチA)
        メニュー = self.呼ぶ("GET", "/api/menus", トークン=コーチA)[0]
        戦術 = self.呼ぶ("GET", "/api/tactics", トークン=コーチA)[0]
        self.呼ぶ("GET", f"/api/events/{予定['id']}", トークン=コーチB, 期待=404)
        self.呼ぶ("PUT", f"/api/menus/{メニュー['id']}", {"name": "乗っ取り"}, コーチB, 期待=404)
        self.呼ぶ("GET", f"/api/tactics/{戦術['id']}", トークン=コーチB, 期待=404)
        self.呼ぶ("GET", f"/api/players/{選手A}/karte", トークン=コーチB, 期待=404)
        self.呼ぶ("PUT", f"/api/members/{選手A}", {"name": "変更"}, コーチB, 期待=404)
        # B の予定に A のメニューを入れることもできない
        self.呼ぶ("POST", "/api/events", {"date": "2026-06-01", "menu_ids": [メニュー["id"]]}, コーチB, 期待=404)
        self.assertEqual(len(self.呼ぶ("GET", "/api/members", トークン=コーチB)), 1)

    def test_選手の権限(self):
        コーチ, コード = self.チームを作る()
        選手1, 選手1トークン = self.選手を追加(コーチ, コード, "player1", "選手A")
        選手2, _ = self.選手を追加(コーチ, コード, "player2", "選手B")
        # 個人情報の編集はコーチのみ
        self.呼ぶ("PUT", f"/api/members/{選手1}", {"name": "自分で変更"}, 選手1トークン, 期待=403)
        self.呼ぶ("POST", "/api/members", {"name": "x", "login_id": "xyz"}, 選手1トークン, 期待=403)
        # 他の選手のカルテは見られない
        self.呼ぶ("GET", f"/api/players/{選手1}/karte", トークン=選手1トークン)
        self.呼ぶ("GET", f"/api/players/{選手2}/karte", トークン=選手1トークン, 期待=403)
        self.呼ぶ("GET", f"/api/players/{選手2}/skills", トークン=選手1トークン, 期待=403)
        # お知らせ配信・予定作成・戦術作成はコーチのみ
        self.呼ぶ("POST", "/api/posts", {"kind": "お知らせ", "title": "x"}, 選手1トークン, 期待=403)
        self.呼ぶ("POST", "/api/posts", {"kind": "掲示板", "title": "x"}, 選手1トークン)
        self.呼ぶ("POST", "/api/events", {"date": "2026-06-01"}, 選手1トークン, 期待=403)
        self.呼ぶ("POST", "/api/stats/game", {"date": "2026-06-01", "rows": []}, 選手1トークン, 期待=403)
        # 他の選手の出欠は代理入力できない
        予定 = self.呼ぶ("POST", "/api/events", {"date": "2099-06-01"}, コーチ)
        self.呼ぶ("PUT", f"/api/events/{予定['id']}/attendance", {"status": "出席", "user_id": 選手2}, 選手1トークン, 期待=403)
        # 下書きの予定は選手に見えない
        下書き = self.呼ぶ("POST", "/api/events", {"date": "2099-06-02", "published": False}, コーチ)
        self.呼ぶ("GET", f"/api/events/{下書き['id']}", トークン=選手1トークン, 期待=404)
        self.assertNotIn(下書き["id"], [e["id"] for e in self.呼ぶ("GET", "/api/events", トークン=選手1トークン)])

    def test_出欠と既読(self):
        コーチ, コード = self.チームを作る()
        選手, 選手トークン = self.選手を追加(コーチ, コード)
        予定 = self.呼ぶ("POST", "/api/events", {"date": "2099-06-01", "menu_ids": [m["id"] for m in self.呼ぶ("GET", "/api/menus", トークン=コーチ)[:2]]}, コーチ)
        詳細 = self.呼ぶ("GET", f"/api/events/{予定['id']}", トークン=コーチ)
        self.assertEqual(詳細["summary"]["既読"], 1)
        self.assertEqual(len(詳細["menus"]), 2)
        self.呼ぶ("GET", f"/api/events/{予定['id']}", トークン=選手トークン)
        self.呼ぶ("PUT", f"/api/events/{予定['id']}/attendance", {"status": "欠席", "comment": "通院"}, 選手トークン)
        self.呼ぶ("PUT", f"/api/events/{予定['id']}/attendance", {"status": "寝坊"}, 選手トークン, 期待=400)
        詳細 = self.呼ぶ("GET", f"/api/events/{予定['id']}", トークン=コーチ)
        self.assertEqual((詳細["summary"]["既読"], 詳細["summary"]["欠席"], 詳細["summary"]["未回答"]), (2, 1, 1))
        # コーチの代理入力
        self.呼ぶ("PUT", f"/api/events/{予定['id']}/attendance", {"status": "出席", "user_id": 選手}, コーチ)
        self.assertEqual(self.呼ぶ("GET", f"/api/events/{予定['id']}", トークン=選手トークン)["my_status"], "出席")
        # 練習履歴の検索（メニュー名で）
        名前 = 詳細["menus"][0]["name"]
        self.assertEqual(len(self.呼ぶ("GET", f"/api/events?q={urllib.parse.quote(名前)}", トークン=コーチ)), 1)
        # 複製
        複製 = self.呼ぶ("POST", f"/api/events/{予定['id']}/copy", {"date": "2099-06-08"}, コーチ)
        self.assertEqual(len(self.呼ぶ("GET", f"/api/events/{複製['id']}", トークン=コーチ)["menus"]), 2)

    def test_お知らせの既読(self):
        コーチ, コード = self.チームを作る()
        _, 選手トークン = self.選手を追加(コーチ, コード)
        投稿 = self.呼ぶ("POST", "/api/posts", {"kind": "お知らせ", "title": "集合時間", "body": "8時"}, コーチ)
        self.assertEqual(len(self.呼ぶ("GET", "/api/home", トークン=選手トークン)["unread_notices"]), 1)
        選手から = self.呼ぶ("GET", f"/api/posts/{投稿['id']}", トークン=選手トークン)
        self.assertNotIn("reads", 選手から)  # 誰が読んだかはコーチのみ
        self.assertEqual(len(self.呼ぶ("GET", "/api/home", トークン=選手トークン)["unread_notices"]), 0)
        コーチから = self.呼ぶ("GET", f"/api/posts/{投稿['id']}", トークン=コーチ)
        self.assertEqual(コーチから["read_count"], 2)
        self.assertTrue(all(r["read_at"] for r in コーチから["reads"]))

    def test_戦術図とクイズ(self):
        コーチ, コード = self.チームを作る()
        _, 選手トークン = self.選手を追加(コーチ, コード)
        図 = {"frames": [{"players": [{"id": "O1", "team": "O", "label": "1", "x": 250, "y": 300}], "ball": "O1", "lines": [{"type": "pass", "points": [[250, 300], [100, 200]]}], "note": "パス"}]}
        self.呼ぶ("POST", "/api/tactics", {"title": "x", "data": {"frames": [{"players": [{"id": "O1", "team": "O", "x": 999, "y": 0}]}]}}, コーチ, 期待=400)
        戦術 = self.呼ぶ("POST", "/api/tactics", {"title": "速攻", "kind": "オフェンス", "data": 図}, コーチ)
        クイズ = self.呼ぶ("POST", f"/api/tactics/{戦術['id']}/quizzes", {"question": "誰にパス？", "choices": ["2番", "3番"], "answer_index": 1, "explanation": "3番が空く"}, コーチ)
        選手から = self.呼ぶ("GET", f"/api/tactics/{戦術['id']}", トークン=選手トークン)
        self.assertIsNone(選手から["quizzes"][0]["answer_index"])  # 回答前は正解を隠す
        self.assertFalse(self.呼ぶ("POST", f"/api/quizzes/{クイズ['id']}/answer", {"choice": 0}, 選手トークン)["correct"])
        self.assertTrue(self.呼ぶ("POST", f"/api/quizzes/{クイズ['id']}/answer", {"choice": 1}, 選手トークン)["correct"])
        self.呼ぶ("PUT", f"/api/tactics/{戦術['id']}/check", {"understood": 2, "comment": "分かった"}, 選手トークン)
        コーチから = self.呼ぶ("GET", f"/api/tactics/{戦術['id']}", トークン=コーチ)
        self.assertEqual((コーチから["checks"][0]["understood"], コーチから["checks"][0]["correct"]), (2, 1))
        # 非公開の戦術は選手に見えない
        複製 = self.呼ぶ("POST", f"/api/tactics/{戦術['id']}/copy", {}, コーチ)
        self.呼ぶ("GET", f"/api/tactics/{複製['id']}", トークン=選手トークン, 期待=404)
        self.assertEqual(len(self.呼ぶ("GET", f"/api/tactics/{複製['id']}", トークン=コーチ)["quizzes"]), 1)

    def test_スタッツとシュートエリア(self):
        コーチ, コード = self.チームを作る()
        選手, 選手トークン = self.選手を追加(コーチ, コード)
        # エリア別だけ入力すると FG・3P・得点を自動計算
        self.呼ぶ("POST", "/api/stats/game", {"date": "2026-06-01", "label": "練習試合", "rows": [
            {"player_id": 選手, "rebounds": 5, "ftm": 1, "fta": 2, "zones": {"ゴール下": {"a": 4, "m": 3}, "3Pトップ": {"a": 3, "m": 1}}},
        ]}, コーチ)
        結果 = self.呼ぶ("GET", f"/api/players/{選手}/stats", トークン=選手トークン)
        行 = 結果["rows"][0]
        self.assertEqual((行["fga"], 行["fgm"], 行["tpa"], 行["tpm"], 行["points"]), (7, 4, 3, 1, 10))
        self.assertEqual(結果["summary"]["fg_pct"], 57.1)
        self.呼ぶ("POST", f"/api/players/{選手}/stats", {"date": "2026-06-02", "fgm": 5, "fga": 3}, コーチ, 期待=400)
        self.呼ぶ("POST", f"/api/players/{選手}/stats", {"date": "2026-06-02", "fga": 2, "zones": {"ペイント": {"a": 3, "m": 1}}}, コーチ, 期待=400)

    def test_能力値診断とステップの自動進行(self):
        コーチ, コード = self.チームを作る()
        選手, 選手トークン = self.選手を追加(コーチ, コード)
        カテゴリ = {c["name"]: c["id"] for c in self.呼ぶ("GET", "/api/skill-categories", トークン=コーチ)}
        self.呼ぶ("POST", f"/api/players/{選手}/assessments", {"items": [
            {"category_id": カテゴリ["シュート"], "value": 30}, {"category_id": カテゴリ["パス"], "value": 75}, {"category_id": カテゴリ["ドリブル"], "value": 50},
        ]}, コーチ)
        self.呼ぶ("POST", f"/api/players/{選手}/assessments", {"items": [{"category_id": カテゴリ["シュート"], "value": 101}]}, 選手トークン, 期待=400)
        self.呼ぶ("POST", f"/api/players/{選手}/assessments", {"items": [{"category_id": カテゴリ["シュート"], "value": 80}]}, 選手トークン)
        診断 = {d["name"]: d for d in self.呼ぶ("GET", f"/api/players/{選手}/skills", トークン=選手トークン)["diagnosis"]}
        self.assertEqual((診断["シュート"]["coach"], 診断["シュート"]["self"]), (30, 80))
        self.assertTrue(診断["シュート"]["gap_warning"])
        self.assertEqual(診断["パス"]["level"], "上級")
        # シュート：(30×0.5 + 80×0.2) / 0.7 = 44 が一番低い
        self.assertEqual((診断["シュート"]["value"], 診断["シュート"]["priority"], 診断["ドリブル"]["priority"]), (44, 1, 2))

        ステップ = self.呼ぶ("GET", f"/api/players/{選手}/steps", トークン=選手トークン)
        おすすめ = ステップ["recommendations"]
        self.assertEqual(おすすめ[0]["category_name"], "シュート")
        self.assertEqual(おすすめ[0]["drill"]["level"], "中級")  # 中級と診断 → 初級は飛ばす
        パス = next(r for r in おすすめ if r["category_name"] == "パス")
        self.assertEqual(パス["drill"]["level"], "上級")

        # クリアしなければ同じステップのまま
        最初 = おすすめ[0]["drill"]
        r = self.呼ぶ("POST", f"/api/players/{選手}/steps/report", {"drill_id": 最初["id"], "self_rating": 2, "cleared": False}, 選手トークン)
        self.assertFalse(r["cleared"])
        self.assertEqual(self.呼ぶ("GET", f"/api/players/{選手}/steps", トークン=選手トークン)["recommendations"][0]["drill"]["id"], 最初["id"])
        # クリアすると次のステップが自動で「実施中」に
        r = self.呼ぶ("POST", f"/api/players/{選手}/steps/report", {"drill_id": 最初["id"], "self_rating": 5, "cleared": True, "video_url": "https://example.com/v"}, 選手トークン)
        self.assertTrue(r["cleared"])
        self.assertNotEqual(r["next"]["id"], 最初["id"])
        self.assertEqual(r["next"]["status"], "実施中")
        self.呼ぶ("POST", f"/api/players/{選手}/steps/report", {"drill_id": 最初["id"], "self_rating": 5, "video_url": "javascript:alert(1)"}, 選手トークン, 期待=400)

        # コーチが上書きで初級ドリルを提示
        ドリブル初級 = next(d for d in self.呼ぶ("GET", f"/api/drills?category_id={カテゴリ['ドリブル']}", トークン=コーチ) if d["level"] == "初級")
        self.呼ぶ("PUT", f"/api/players/{選手}/steps/override", {"category_id": カテゴリ["ドリブル"], "drill_id": ドリブル初級["id"], "note": "基礎から"}, 選手トークン, 期待=403)
        self.呼ぶ("PUT", f"/api/players/{選手}/steps/override", {"category_id": カテゴリ["ドリブル"], "drill_id": ドリブル初級["id"], "note": "基礎から"}, コーチ)
        先頭 = self.呼ぶ("GET", f"/api/players/{選手}/steps", トークン=選手トークン)["recommendations"][0]
        self.assertEqual((先頭["drill"]["id"], 先頭["overridden"], 先頭["override_note"]), (ドリブル初級["id"], True, "基礎から"))
        # 指定ドリルをクリアすると指定は外れて通常の順番に戻る
        self.呼ぶ("POST", f"/api/players/{選手}/steps/report", {"drill_id": ドリブル初級["id"], "self_rating": 4, "cleared": True}, 選手トークン)
        self.assertFalse(self.呼ぶ("GET", f"/api/players/{選手}/steps", トークン=選手トークン)["recommendations"][0]["overridden"])

        一覧 = self.呼ぶ("GET", "/api/steps/overview", トークン=コーチ)
        self.assertEqual(len(一覧["players"]), 1)
        self.呼ぶ("GET", "/api/steps/overview", トークン=選手トークン, 期待=403)
        # カレンダーに報告が反映
        カレンダー = self.呼ぶ("GET", f"/api/players/{選手}/calendar", トークン=選手トークン)
        self.assertGreaterEqual(カレンダー["active_days"], 1)

    def test_ドリルの追加と削除でつながりを保つ(self):
        コーチ, _ = self.チームを作る()
        シュート = next(c["id"] for c in self.呼ぶ("GET", "/api/skill-categories", トークン=コーチ) if c["name"] == "シュート")
        並び = lambda: [d["id"] for d in self.呼ぶ("GET", f"/api/drills?category_id={シュート}", トークン=コーチ)]  # noqa: E731
        元 = 並び()
        新 = self.呼ぶ("POST", "/api/drills", {"category_id": シュート, "level": "初級", "title": "新ドリル", "insert_after_id": 元[0]}, コーチ)
        self.assertEqual(並び(), [元[0], 新["id"], *元[1:]])
        self.呼ぶ("DELETE", f"/api/drills/{元[1]}", トークン=コーチ)
        self.assertEqual(並び(), [元[0], 新["id"], *元[2:]])
        self.呼ぶ("PUT", f"/api/drills/{新['id']}", {"category_id": シュート, "title": "自己参照", "next_step_id": 新["id"]}, コーチ, 期待=400)

    def test_目標とフィードバック(self):
        コーチ, コード = self.チームを作る()
        選手, 選手トークン = self.選手を追加(コーチ, コード)
        self.呼ぶ("POST", "/api/goals", {"scope": "チーム", "content": "ベスト8"}, 選手トークン, 期待=403)
        チーム目標 = self.呼ぶ("POST", "/api/goals", {"scope": "チーム", "content": "ベスト8", "deadline": "2026-08-01"}, コーチ)
        自分 = self.呼ぶ("POST", "/api/goals", {"scope": "個人", "content": "FT70%"}, 選手トークン)
        self.呼ぶ("PUT", f"/api/goals/{チーム目標['id']}", {"progress": 50}, 選手トークン, 期待=403)
        self.呼ぶ("PUT", f"/api/goals/{自分['id']}", {"progress": 100, "status": "達成", "reflection": "毎日50本"}, 選手トークン)
        目標 = self.呼ぶ("GET", "/api/goals", トークン=選手トークン)
        self.assertEqual({g["scope"] for g in 目標}, {"チーム", "個人"})
        self.assertEqual(next(g for g in 目標 if g["id"] == 自分["id"])["reflection"], "毎日50本")

        fb = self.呼ぶ("POST", f"/api/players/{選手}/feedback", {"body": "顔を上げよう"}, コーチ)
        self.assertEqual(self.呼ぶ("GET", "/api/home", トークン=選手トークン)["unconfirmed_feedback"], 1)
        self.呼ぶ("POST", f"/api/feedback/{fb['id']}/confirm", {"reply": "はい"}, コーチ, 期待=403)
        self.呼ぶ("POST", f"/api/feedback/{fb['id']}/confirm", {"reply": "はい"}, 選手トークン)
        self.assertEqual(self.呼ぶ("GET", "/api/home", トークン=選手トークン)["unconfirmed_feedback"], 0)

    def test_退部とコーチ不在の防止(self):
        コーチ, コード = self.チームを作る()
        選手, 選手トークン = self.選手を追加(コーチ, コード)
        自分 = self.呼ぶ("GET", "/api/me", トークン=コーチ)["user"]["id"]
        self.呼ぶ("DELETE", f"/api/members/{自分}", トークン=コーチ, 期待=400)
        self.呼ぶ("PUT", f"/api/members/{自分}", {"name": "監督", "role": "player"}, コーチ, 期待=400)
        self.呼ぶ("DELETE", f"/api/members/{選手}", トークン=コーチ)
        self.呼ぶ("GET", "/api/me", トークン=選手トークン, 期待=401)
        self.assertEqual(len(self.呼ぶ("GET", "/api/members", トークン=コーチ)), 1)

    def test_不正な入力(self):
        コーチ, _ = self.チームを作る()
        self.呼ぶ("POST", "/api/teams", {"team_name": "x", "name": "y", "login_id": "ab", "password": "password1"}, 期待=400)
        self.呼ぶ("POST", "/api/teams", {"team_name": "x", "name": "y", "login_id": "abc", "password": "short"}, 期待=400)
        self.呼ぶ("POST", "/api/events", {"date": "2026-13-01"}, コーチ, 期待=400)
        self.呼ぶ("POST", "/api/events", {"date": "2026-06-01", "start_time": "18:00", "end_time": "17:00"}, コーチ, 期待=400)
        self.呼ぶ("POST", "/api/members", {"name": "x", "login_id": "abc", "photo": "data:text/html;base64,AAAA"}, コーチ, 期待=400)
        self.呼ぶ("GET", "/api/存在しない", トークン=コーチ, 期待=404)
        要求 = urllib.request.Request(self.基本 + "/api/login", data=b"{broken", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as 例外:
            urllib.request.urlopen(要求)
        self.assertEqual(例外.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
