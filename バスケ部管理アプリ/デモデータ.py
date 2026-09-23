"""動作確認用のデモチーム（サンプルデータ入り）を作る。

チームコード DEMO22 ／ コーチ: coach ／ 選手: player1〜player8 ／ パスワードは全員 demo-pass1
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import date, timedelta

import 初期データ
from データベース import 今日, 現在時刻
from 認証 import パスワードをハッシュ化

デモのチームコード = "DEMO22"
デモのパスワード = "demo-pass1"

選手一覧 = [
    ("player1", "佐藤 蓮", "2年", "PG", "4"),
    ("player2", "鈴木 陽翔", "2年", "SG", "5"),
    ("player3", "高橋 湊", "2年", "SF", "6"),
    ("player4", "田中 大和", "2年", "PF", "7"),
    ("player5", "伊藤 悠真", "1年", "C", "8"),
    ("player6", "渡辺 朝陽", "1年", "SG", "9"),
    ("player7", "山本 颯", "1年", "SF", "10"),
    ("player8", "中村 樹", "1年", "PF", "11"),
]


def デモチームを作成(接続先: sqlite3.Connection) -> str:
    案内 = f"デモチーム: チームコード {デモのチームコード} ／ コーチ coach ／ 選手 player1〜player8 ／ パスワード {デモのパスワード}"
    if 接続先.execute("SELECT 1 FROM teams WHERE code = ?", (デモのチームコード,)).fetchone():
        return 案内 + "（作成済み）"
    乱数 = random.Random(22)
    時刻 = 現在時刻()
    本日 = date.fromisoformat(今日())
    ハッシュ = パスワードをハッシュ化(デモのパスワード)
    チームID = 接続先.execute("INSERT INTO teams (name, code, created_at) VALUES (?, ?, ?)", ("県立みなと高校 男子バスケ部", デモのチームコード, 時刻)).lastrowid
    コーチID = 接続先.execute(
        "INSERT INTO users (team_id, login_id, name, role, password_hash, created_at) VALUES (?, 'coach', '山田 監督', 'coach', ?, ?)",
        (チームID, ハッシュ, 時刻),
    ).lastrowid
    初期データ.チームの初期データを投入(接続先, チームID, コーチID)
    選手ID = []
    for ログインID, 氏名, 学年, ポジション, 背番号 in 選手一覧:
        選手ID.append(
            接続先.execute(
                """INSERT INTO users (team_id, login_id, name, role, grade, position, number, password_hash, created_at)
                   VALUES (?, ?, ?, 'player', ?, ?, ?, ?, ?)""",
                (チームID, ログインID, 氏名, 学年, ポジション, 背番号, ハッシュ, 時刻),
            ).lastrowid
        )

    メニューID = [行[0] for 行 in 接続先.execute("SELECT id FROM menus WHERE team_id = ? ORDER BY id", (チームID,)).fetchall()]
    # 過去3週間と今後2週間の練習（火・木・土）と、今週末の練習試合
    for 差 in range(-21, 15):
        日 = 本日 + timedelta(days=差)
        if 日.weekday() not in (1, 3, 5):
            continue
        予定ID = 接続先.execute(
            """INSERT INTO events (team_id, kind, title, date, start_time, end_time, place, notes, published, created_by, created_at)
               VALUES (?, '練習', ?, ?, ?, ?, '体育館', '', 1, ?, ?)""",
            (チームID, "通常練習" if 日.weekday() != 5 else "土曜練習", 日.isoformat(), "16:00" if 日.weekday() != 5 else "09:00", "18:30" if 日.weekday() != 5 else "12:00", コーチID, 時刻),
        ).lastrowid
        選択 = [メニューID[0], メニューID[1], *乱数.sample(メニューID[2:-1], 4), メニューID[-1]]
        for 順番, m in enumerate(選択):
            接続先.execute("INSERT INTO event_menus (event_id, menu_id, sort) VALUES (?, ?, ?)", (予定ID, m, 順番))
        if 差 <= 2:
            for p in 選手ID:
                if 差 > 0 and 乱数.random() < 0.4:
                    continue  # 未回答
                状態 = 乱数.choices(["出席", "欠席", "遅刻"], weights=[85, 10, 5])[0]
                接続先.execute(
                    "INSERT INTO attendance (event_id, user_id, status, comment, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (予定ID, p, 状態, "通院のため" if 状態 == "欠席" else "", 時刻),
                )
                if 乱数.random() < 0.9:
                    接続先.execute("INSERT INTO event_views (event_id, user_id, viewed_at) VALUES (?, ?, ?)", (予定ID, p, 時刻))
    試合日 = 本日 + timedelta(days=(6 - 本日.weekday()) % 7 or 7)
    接続先.execute(
        """INSERT INTO events (team_id, kind, title, date, start_time, end_time, place, notes, published, created_by, created_at)
           VALUES (?, '試合', '練習試合 vs 北高', ?, '10:00', '15:00', '北高校 体育館', '8:45 正門集合。白・黒ユニフォーム持参。', 1, ?, ?)""",
        (チームID, 試合日.isoformat(), コーチID, 時刻),
    )

    # 過去の試合スタッツ（5試合）
    実力 = [乱数.uniform(0.7, 1.3) for _ in 選手ID]
    for 試合 in range(5):
        日 = (本日 - timedelta(days=7 * (5 - 試合) + 1)).isoformat()
        for 位置, p in enumerate(選手ID):
            if 位置 >= 7 and 乱数.random() < 0.5:
                continue
            k = 実力[位置]
            エリア = {}
            fga = fgm = tpa = tpm = 0
            for 名前, 基本確率, 本数 in (("ゴール下", 0.55, 3), ("ペイント", 0.42, 2), ("ミドル左", 0.35, 1), ("ミドル正面", 0.38, 1), ("ミドル右", 0.35, 1), ("3P左ウイング", 0.28, 1), ("3Pトップ", 0.3, 1), ("3P右コーナー", 0.3, 1)):
                a = 乱数.randint(0, 本数 + (2 if 位置 < 3 and 名前.startswith("3P") else 0))
                m = sum(1 for _ in range(a) if 乱数.random() < 基本確率 * k)
                if a:
                    エリア[名前] = {"a": a, "m": m}
                fga += a
                fgm += m
                if 名前.startswith("3P"):
                    tpa += a
                    tpm += m
            fta = 乱数.randint(0, 4)
            ftm = sum(1 for _ in range(fta) if 乱数.random() < 0.6 * k)
            接続先.execute(
                """INSERT INTO stats (team_id, player_id, date, label, minutes, points, rebounds, assists, steals, blocks, turnovers,
                       fgm, fga, tpm, tpa, ftm, fta, zones, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    チームID, p, 日, f"練習試合{試合 + 1}", 乱数.randint(8, 28),
                    (fgm - tpm) * 2 + tpm * 3 + ftm,
                    乱数.randint(0, 4 + (5 if 位置 in (3, 4) else 0)),
                    乱数.randint(0, 2 + (4 if 位置 == 0 else 0)),
                    乱数.randint(0, 3), 乱数.randint(0, 1 + (2 if 位置 == 4 else 0)), 乱数.randint(0, 3),
                    fgm, fga, tpm, tpa, ftm, fta, json.dumps(エリア, ensure_ascii=False), 時刻,
                ),
            )

    カテゴリ = 接続先.execute("SELECT id, name FROM skill_categories WHERE team_id = ? ORDER BY sort", (チームID,)).fetchall()
    for p in 選手ID:
        for c in カテゴリ:
            接続先.execute(
                "INSERT INTO skill_assessments (team_id, player_id, category_id, source, value, assessor_id, assessed_at) VALUES (?, ?, ?, 'コーチ', ?, ?, ?)",
                (チームID, p, c["id"], 乱数.randint(25, 80), コーチID, 時刻),
            )
            if 乱数.random() < 0.7:
                接続先.execute(
                    "INSERT INTO skill_assessments (team_id, player_id, category_id, source, value, assessor_id, assessed_at) VALUES (?, ?, ?, '自己評価', ?, ?, ?)",
                    (チームID, p, c["id"], 乱数.randint(30, 85), p, 時刻),
                )

    # 佐藤くんはシュートの初級を1つクリア済み
    最初のドリル = 接続先.execute(
        """SELECT d.id FROM drill_steps d JOIN skill_categories c ON c.id = d.category_id
           WHERE d.team_id = ? AND c.name = 'シュート' ORDER BY d.id LIMIT 2""",
        (チームID,),
    ).fetchall()
    接続先.execute(
        "INSERT INTO player_step_progress (player_id, drill_id, team_id, status, self_rating, report, updated_at) VALUES (?, ?, ?, '完了', 4, '10本中8本入った', ?)",
        (選手ID[0], 最初のドリル[0][0], チームID, 時刻),
    )
    接続先.execute(
        "INSERT INTO step_reports (team_id, player_id, drill_id, date, self_rating, comment, cleared, created_at) VALUES (?, ?, ?, ?, 4, '10本中8本入った', 1, ?)",
        (チームID, 選手ID[0], 最初のドリル[0][0], (本日 - timedelta(days=2)).isoformat(), 時刻),
    )
    for 差 in (1, 3, 4, 6):
        接続先.execute(
            "INSERT INTO practice_logs (team_id, player_id, date, minutes, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (チームID, 選手ID[0], (本日 - timedelta(days=差)).isoformat(), 30, "公園でドリブル練習", 時刻),
        )

    接続先.execute(
        "INSERT INTO posts (team_id, kind, title, body, author_id, created_at) VALUES (?, 'お知らせ', ?, ?, ?, ?)",
        (チームID, "練習試合のお知らせ", f"{試合日.month}月{試合日.day}日に北高と練習試合を行います。出欠を今週中に入力してください。", コーチID, 時刻),
    )
    接続先.execute(
        "INSERT INTO posts (team_id, kind, title, body, author_id, created_at) VALUES (?, '掲示板', ?, ?, ?, ?)",
        (チームID, "シューズの洗い方", "体育館シューズの裏を拭くと滑りにくくなるよ！", 選手ID[1], 時刻),
    )
    接続先.execute(
        "INSERT INTO goals (team_id, scope, user_id, content, deadline, progress, status, created_at, updated_at) VALUES (?, 'チーム', NULL, ?, ?, 30, '進行中', ?, ?)",
        (チームID, "夏の地区大会でベスト8", (本日 + timedelta(days=90)).isoformat(), 時刻, 時刻),
    )
    接続先.execute(
        "INSERT INTO goals (team_id, scope, user_id, content, deadline, progress, status, created_at, updated_at) VALUES (?, '個人', ?, ?, ?, 40, '進行中', ?, ?)",
        (チームID, 選手ID[0], "フリースロー成功率70%", (本日 + timedelta(days=45)).isoformat(), 時刻, 時刻),
    )
    接続先.execute(
        "INSERT INTO feedback (team_id, player_id, coach_id, body, created_at) VALUES (?, ?, ?, ?, ?)",
        (チームID, 選手ID[0], コーチID, "ドライブのとき顔が下がっている。ヘルプの位置を見てからパスを選ぼう。", 時刻),
    )
    接続先.execute(
        "INSERT INTO issues (team_id, player_id, title, detail, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (チームID, 選手ID[0], "左手のレイアップ", "左からのドライブで右手に持ち替えてしまう", コーチID, 時刻, 時刻),
    )
    接続先.commit()
    return 案内
