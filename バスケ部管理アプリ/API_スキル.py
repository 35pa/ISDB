"""個人能力値診断・スキルレベル判定・ステップバイステップ練習メニューの API。"""

from __future__ import annotations

import スキル診断
from データベース import 今日, 現在時刻, 行一覧を辞書に
from ルーティング import (
    APIエラー,
    リクエスト,
    ルート,
    URL,
    チーム内の行,
    整数,
    文字列,
    日付,
    真偽,
    選択,
    選手を確認,
    最大文字数_長,
)


# ---------- スキルカテゴリ ----------


def _カテゴリ一覧(リクエスト_: リクエスト) -> list[dict]:
    return 行一覧を辞書に(
        リクエスト_.db.execute("SELECT * FROM skill_categories WHERE team_id = ? ORDER BY sort, id", (リクエスト_.チームID,)).fetchall()
    )


@ルート("GET", "/api/skill-categories")
def カテゴリ一覧(リクエスト_: リクエスト):
    return _カテゴリ一覧(リクエスト_)


@ルート("POST", "/api/skill-categories", 権限="コーチ")
def カテゴリ追加(リクエスト_: リクエスト):
    名前 = 文字列(リクエスト_.本文, "name", "スキル名", 必須=True, 最大=20)
    if リクエスト_.db.execute("SELECT 1 FROM skill_categories WHERE team_id = ? AND name = ?", (リクエスト_.チームID, 名前)).fetchone():
        raise APIエラー(400, "同じ名前のスキルがすでにあります")
    順番 = リクエスト_.db.execute("SELECT COALESCE(MAX(sort), -1) + 1 FROM skill_categories WHERE team_id = ?", (リクエスト_.チームID,)).fetchone()[0]
    カテゴリID = リクエスト_.db.execute(
        "INSERT INTO skill_categories (team_id, name, sort) VALUES (?, ?, ?)", (リクエスト_.チームID, 名前, 順番)
    ).lastrowid
    return {"id": カテゴリID}


@ルート("PUT", "/api/skill-categories/{カテゴリID}", 権限="コーチ")
def カテゴリ編集(リクエスト_: リクエスト, カテゴリID: int):
    既存 = チーム内の行(リクエスト_, "skill_categories", カテゴリID, "スキル")
    名前 = 文字列(リクエスト_.本文, "name", "スキル名", 必須=True, 最大=20)
    重複 = リクエスト_.db.execute(
        "SELECT 1 FROM skill_categories WHERE team_id = ? AND name = ? AND id != ?", (リクエスト_.チームID, 名前, カテゴリID)
    ).fetchone()
    if 重複:
        raise APIエラー(400, "同じ名前のスキルがすでにあります")
    順番 = 整数(リクエスト_.本文, "sort", "並び順", 0, 1000, 既定=既存["sort"])
    リクエスト_.db.execute("UPDATE skill_categories SET name = ?, sort = ? WHERE id = ?", (名前, 順番, カテゴリID))
    return {"id": カテゴリID}


@ルート("DELETE", "/api/skill-categories/{カテゴリID}", 権限="コーチ")
def カテゴリ削除(リクエスト_: リクエスト, カテゴリID: int):
    チーム内の行(リクエスト_, "skill_categories", カテゴリID, "スキル")
    リクエスト_.db.execute("DELETE FROM skill_categories WHERE id = ?", (カテゴリID,))
    return {"ok": True}


# ---------- 能力値診断 ----------


def _最新評価(リクエスト_: リクエスト, 選手ID: int) -> dict[int, dict[str, int]]:
    行一覧 = リクエスト_.db.execute(
        """SELECT category_id, source, value FROM skill_assessments a
           WHERE player_id = ? AND team_id = ? AND id = (
             SELECT b.id FROM skill_assessments b
             WHERE b.player_id = a.player_id AND b.category_id = a.category_id AND b.source = a.source
             ORDER BY b.assessed_at DESC, b.id DESC LIMIT 1)""",
        (選手ID, リクエスト_.チームID),
    ).fetchall()
    結果: dict[int, dict[str, int]] = {}
    for 行 in 行一覧:
        結果.setdefault(行["category_id"], {})[行["source"]] = 行["value"]
    return 結果


def _スタッツ一覧(リクエスト_: リクエスト, 選手ID: int) -> list[dict]:
    return 行一覧を辞書に(
        リクエスト_.db.execute("SELECT * FROM stats WHERE player_id = ? AND team_id = ? ORDER BY date DESC, id DESC", (選手ID, リクエスト_.チームID)).fetchall()
    )


def 選手の診断(リクエスト_: リクエスト, 選手ID: int) -> list[dict]:
    return スキル診断.スキル診断(_カテゴリ一覧(リクエスト_), _最新評価(リクエスト_, 選手ID), _スタッツ一覧(リクエスト_, 選手ID))


@ルート("GET", "/api/players/{選手ID}/skills")
def 能力値診断(リクエスト_: リクエスト, 選手ID: int):
    選手を確認(リクエスト_, 選手ID)
    履歴 = 行一覧を辞書に(
        リクエスト_.db.execute(
            """SELECT a.id, a.category_id, c.name AS category_name, a.source, a.value, a.assessed_at, u.name AS assessor_name
               FROM skill_assessments a JOIN skill_categories c ON c.id = a.category_id
               LEFT JOIN users u ON u.id = a.assessor_id
               WHERE a.player_id = ? AND a.team_id = ? ORDER BY a.assessed_at DESC, a.id DESC LIMIT 200""",
            (選手ID, リクエスト_.チームID),
        ).fetchall()
    )
    return {
        "diagnosis": 選手の診断(リクエスト_, 選手ID),
        "history": 履歴,
        "weights": スキル診断.評価元の重み,
        "thresholds": スキル診断.レベル境界,
        "levels": スキル診断.レベルの目安(),
    }


@ルート("POST", "/api/players/{選手ID}/assessments")
def 能力値登録(リクエスト_: リクエスト, 選手ID: int):
    """コーチが入力すれば「コーチ」評価、選手本人が入力すれば「自己評価」として記録する。"""
    選手を確認(リクエスト_, 選手ID)
    評価元 = "コーチ" if リクエスト_.コーチか else "自己評価"
    項目一覧 = リクエスト_.本文.get("items")
    if not isinstance(項目一覧, list) or not 項目一覧:
        raise APIエラー(400, "評価するスキルを1つ以上入力してください")
    カテゴリID一覧 = {c["id"] for c in _カテゴリ一覧(リクエスト_)}
    時刻 = 現在時刻()
    登録 = []
    for 項目 in 項目一覧:
        if not isinstance(項目, dict):
            raise APIエラー(400, "評価の形式が正しくありません")
        カテゴリID = 整数(項目, "category_id", "スキル", 1, 10**9, 既定=None)
        if カテゴリID not in カテゴリID一覧:
            raise APIエラー(404, "スキルが見つかりません")
        登録.append((カテゴリID, 整数(項目, "value", "評価値", 0, 100, 既定=None)))
    for カテゴリID, 値 in 登録:
        リクエスト_.db.execute(
            """INSERT INTO skill_assessments (team_id, player_id, category_id, source, value, assessor_id, assessed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (リクエスト_.チームID, 選手ID, カテゴリID, 評価元, 値, リクエスト_.ユーザー["id"], 時刻),
        )
    return {"source": 評価元, "count": len(登録)}


# ---------- ドリル（スキル×レベルごとのステップ） ----------


def _ドリル入力(リクエスト_: リクエスト, ドリルID: int | None = None) -> tuple:
    本文 = リクエスト_.本文
    カテゴリID = 整数(本文, "category_id", "スキル", 1, 10**9, 既定=None)
    チーム内の行(リクエスト_, "skill_categories", カテゴリID, "スキル")
    次ID = 本文.get("next_step_id")
    if 次ID in (None, "", 0):
        次ID = None
    else:
        次ID = 整数(本文, "next_step_id", "次のステップ", 1, 10**9)
        if 次ID == ドリルID:
            raise APIエラー(400, "次のステップに自分自身は指定できません")
        チーム内の行(リクエスト_, "drill_steps", 次ID, "次のステップ")
    return (
        カテゴリID,
        選択(本文, "level", "レベル", スキル診断.レベル一覧, 既定=スキル診断.レベル一覧[0]),
        整数(本文, "step_no", "ステップ番号", 1, 100, 既定=1),
        文字列(本文, "title", "ドリル名", 必須=True, 最大=60),
        文字列(本文, "content", "内容", 最大=最大文字数_長),
        整数(本文, "minutes", "目安時間（分）", 0, 300, 既定=10),
        文字列(本文, "clear_condition", "クリア条件", 最大=200),
        次ID,
    )


@ルート("GET", "/api/drills")
def ドリル一覧(リクエスト_: リクエスト):
    条件 = "d.team_id = ?"
    引数: list = [リクエスト_.チームID]
    if リクエスト_.クエリ.get("category_id", "").isdigit():
        条件 += " AND d.category_id = ?"
        引数.append(int(リクエスト_.クエリ["category_id"]))
    行一覧 = 行一覧を辞書に(
        リクエスト_.db.execute(
            f"""SELECT d.*, c.name AS category_name FROM drill_steps d JOIN skill_categories c ON c.id = d.category_id
                WHERE {条件} ORDER BY c.sort, c.id""",
            引数,
        ).fetchall()
    )
    カテゴリ別: dict[int, list[dict]] = {}
    for 行 in 行一覧:
        カテゴリ別.setdefault(行["category_id"], []).append(行)
    結果 = []
    for 行一覧_ in カテゴリ別.values():
        for 順番, ドリル in enumerate(スキル診断.ドリルを段階順に並べる(行一覧_), start=1):
            結果.append({**ドリル, "order": 順番})
    return 結果


@ルート("POST", "/api/drills", 権限="コーチ")
def ドリル追加(リクエスト_: リクエスト):
    値 = _ドリル入力(リクエスト_)
    ドリルID = リクエスト_.db.execute(
        """INSERT INTO drill_steps (team_id, category_id, level, step_no, title, content, minutes, clear_condition, next_step_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (リクエスト_.チームID, *値),
    ).lastrowid
    # 「このドリルの前に置く」指定があれば、前のドリルの次ステップを差し替える
    if リクエスト_.本文.get("insert_after_id"):
        前ID = 整数(リクエスト_.本文, "insert_after_id", "前のステップ", 1, 10**9)
        前 = チーム内の行(リクエスト_, "drill_steps", 前ID, "前のステップ")
        if 値[7] is None:
            リクエスト_.db.execute("UPDATE drill_steps SET next_step_id = ? WHERE id = ?", (前["next_step_id"], ドリルID))
        リクエスト_.db.execute("UPDATE drill_steps SET next_step_id = ? WHERE id = ?", (ドリルID, 前ID))
    return {"id": ドリルID}


@ルート("PUT", "/api/drills/{ドリルID}", 権限="コーチ")
def ドリル編集(リクエスト_: リクエスト, ドリルID: int):
    チーム内の行(リクエスト_, "drill_steps", ドリルID, "ドリル")
    値 = _ドリル入力(リクエスト_, ドリルID)
    リクエスト_.db.execute(
        """UPDATE drill_steps SET category_id = ?, level = ?, step_no = ?, title = ?, content = ?, minutes = ?,
               clear_condition = ?, next_step_id = ? WHERE id = ?""",
        (*値, ドリルID),
    )
    return {"id": ドリルID}


@ルート("DELETE", "/api/drills/{ドリルID}", 権限="コーチ")
def ドリル削除(リクエスト_: リクエスト, ドリルID: int):
    ドリル = チーム内の行(リクエスト_, "drill_steps", ドリルID, "ドリル")
    # つながりが切れないよう、前のドリルの次ステップを削除するドリルの次へつなぎ直す
    リクエスト_.db.execute(
        "UPDATE drill_steps SET next_step_id = ? WHERE next_step_id = ? AND team_id = ?",
        (ドリル["next_step_id"], ドリルID, リクエスト_.チームID),
    )
    リクエスト_.db.execute("DELETE FROM drill_steps WHERE id = ?", (ドリルID,))
    return {"ok": True}


# ---------- ステップ進行 ----------


def _選手のステップ状況(リクエスト_: リクエスト, 選手ID: int, 診断: list[dict] | None = None) -> list[dict]:
    db = リクエスト_.db
    診断 = 診断 if 診断 is not None else 選手の診断(リクエスト_, 選手ID)
    ドリル一覧_ = 行一覧を辞書に(db.execute("SELECT * FROM drill_steps WHERE team_id = ?", (リクエスト_.チームID,)).fetchall())
    進捗 = {
        行["drill_id"]: dict(行)
        for 行 in db.execute("SELECT * FROM player_step_progress WHERE player_id = ? AND team_id = ?", (選手ID, リクエスト_.チームID)).fetchall()
    }
    上書き = {
        行["category_id"]: dict(行)
        for 行 in db.execute("SELECT * FROM step_overrides WHERE player_id = ? AND team_id = ?", (選手ID, リクエスト_.チームID)).fetchall()
    }
    状況一覧 = []
    for 項目 in 診断:
        カテゴリID = 項目["category_id"]
        並び = スキル診断.ドリルを段階順に並べる(d for d in ドリル一覧_ if d["category_id"] == カテゴリID)
        状態 = {ID: 行["status"] for ID, 行 in 進捗.items()}
        上書き指定 = 上書き.get(カテゴリID)
        現在 = スキル診断.現在のステップ(並び, 状態, 項目["level"], 上書き指定["drill_id"] if 上書き指定 else None)
        段階 = []
        for 順番, d in enumerate(並び, start=1):
            p = 進捗.get(d["id"])
            段階.append(
                {
                    **d,
                    "order": 順番,
                    "status": p["status"] if p else "未着手",
                    "self_rating": p["self_rating"] if p else 0,
                    "report": p["report"] if p else "",
                    "video_url": p["video_url"] if p else "",
                    "is_current": 現在 is not None and d["id"] == 現在["id"],
                }
            )
        完了数 = sum(1 for d in 段階 if d["status"] == "完了")
        状況一覧.append(
            {
                "category_id": カテゴリID,
                "category_name": 項目["name"],
                "diagnosis": 項目,
                "steps": 段階,
                "current": next((d for d in 段階 if d["is_current"]), None),
                "completed": 完了数,
                "total": len(段階),
                "override": 上書き指定,
            }
        )
    return 状況一覧


def おすすめステップ(リクエスト_: リクエスト, 選手ID: int) -> list[dict]:
    """「次に取り組むべき練習メニュー」を優先度順に返す（優先項目→総合値の低い順→未診断）。"""
    状況一覧 = _選手のステップ状況(リクエスト_, 選手ID)

    def 並び順(状況: dict):
        診断 = 状況["diagnosis"]
        return (
            0 if 状況["override"] else 1,
            診断["priority"] if 診断["priority"] is not None else 99,
            診断["value"] if 診断["value"] is not None else 1000,
            状況["category_id"],
        )

    return [
        {
            "category_id": 状況["category_id"],
            "category_name": 状況["category_name"],
            "level": 状況["diagnosis"]["level"],
            "value": 状況["diagnosis"]["value"],
            "priority": 状況["diagnosis"]["priority"],
            "overridden": bool(状況["override"]),
            "override_note": 状況["override"]["note"] if 状況["override"] else "",
            "drill": 状況["current"],
            "completed": 状況["completed"],
            "total": 状況["total"],
        }
        for 状況 in sorted(状況一覧, key=並び順)
        if 状況["current"] is not None
    ]


@ルート("GET", "/api/players/{選手ID}/steps")
def ステップ状況(リクエスト_: リクエスト, 選手ID: int):
    選手を確認(リクエスト_, 選手ID)
    報告 = 行一覧を辞書に(
        リクエスト_.db.execute(
            """SELECT r.*, d.title, d.level, c.name AS category_name FROM step_reports r
               JOIN drill_steps d ON d.id = r.drill_id JOIN skill_categories c ON c.id = d.category_id
               WHERE r.player_id = ? AND r.team_id = ? ORDER BY r.created_at DESC, r.id DESC LIMIT 30""",
            (選手ID, リクエスト_.チームID),
        ).fetchall()
    )
    return {"categories": _選手のステップ状況(リクエスト_, 選手ID), "recommendations": おすすめステップ(リクエスト_, 選手ID), "reports": 報告}


def _進捗を更新(リクエスト_: リクエスト, 選手ID: int, ドリルID: int, 状態: str, 評価: int | None = None, 報告: str | None = None, 動画: str | None = None) -> None:
    既存 = リクエスト_.db.execute("SELECT * FROM player_step_progress WHERE player_id = ? AND drill_id = ?", (選手ID, ドリルID)).fetchone()
    値 = {
        "self_rating": 評価 if 評価 is not None else (既存["self_rating"] if 既存 else 0),
        "report": 報告 if 報告 is not None else (既存["report"] if 既存 else ""),
        "video_url": 動画 if 動画 is not None else (既存["video_url"] if 既存 else ""),
    }
    リクエスト_.db.execute(
        """INSERT INTO player_step_progress (player_id, drill_id, team_id, status, self_rating, report, video_url, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (player_id, drill_id) DO UPDATE SET status = excluded.status, self_rating = excluded.self_rating,
             report = excluded.report, video_url = excluded.video_url, updated_at = excluded.updated_at""",
        (選手ID, ドリルID, リクエスト_.チームID, 状態, 値["self_rating"], 値["report"], 値["video_url"], 現在時刻()),
    )


@ルート("POST", "/api/players/{選手ID}/steps/report")
def 完了報告(リクエスト_: リクエスト, 選手ID: int):
    """ドリル実施の報告。クリア条件を満たしたら完了にして、自動的に次のステップを「実施中」にする。"""
    選手を確認(リクエスト_, 選手ID)
    本文 = リクエスト_.本文
    ドリル = チーム内の行(リクエスト_, "drill_steps", 整数(本文, "drill_id", "ドリル", 1, 10**9, 既定=None), "ドリル")
    評価 = 整数(本文, "self_rating", "自己評価", 1, 5, 既定=None)
    コメント = 文字列(本文, "comment", "コメント", 最大=1000)
    動画 = URL(本文, "video_url", "動画URL")
    クリア = 真偽(本文, "cleared", False)
    実施日 = 日付(本文, "date", "実施日", 必須=False) or 今日()
    リクエスト_.db.execute(
        """INSERT INTO step_reports (team_id, player_id, drill_id, date, self_rating, comment, video_url, cleared, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (リクエスト_.チームID, 選手ID, ドリル["id"], 実施日, 評価, コメント, 動画, クリア, 現在時刻()),
    )
    _進捗を更新(リクエスト_, 選手ID, ドリル["id"], "完了" if クリア else "実施中", 評価, コメント, 動画)
    次 = None
    if クリア:
        # コーチの上書き指定を達成したら指定を外し、通常の段階順に戻す
        リクエスト_.db.execute(
            "DELETE FROM step_overrides WHERE player_id = ? AND category_id = ? AND drill_id = ?",
            (選手ID, ドリル["category_id"], ドリル["id"]),
        )
        状況 = next(s for s in _選手のステップ状況(リクエスト_, 選手ID) if s["category_id"] == ドリル["category_id"])
        次 = 状況["current"]
        if 次 is not None and 次["status"] == "未着手":
            _進捗を更新(リクエスト_, 選手ID, 次["id"], "実施中")
            次 = {**次, "status": "実施中"}
    return {"cleared": bool(クリア), "next": 次}


@ルート("PUT", "/api/players/{選手ID}/steps/status", 権限="コーチ")
def ステップ状態変更(リクエスト_: リクエスト, 選手ID: int):
    """コーチが完了・やり直しなどを直接調整する。"""
    選手を確認(リクエスト_, 選手ID)
    ドリル = チーム内の行(リクエスト_, "drill_steps", 整数(リクエスト_.本文, "drill_id", "ドリル", 1, 10**9, 既定=None), "ドリル")
    状態 = 選択(リクエスト_.本文, "status", "状態", ("未着手", "実施中", "完了"))
    if 状態 == "未着手":
        リクエスト_.db.execute("DELETE FROM player_step_progress WHERE player_id = ? AND drill_id = ?", (選手ID, ドリル["id"]))
    else:
        _進捗を更新(リクエスト_, 選手ID, ドリル["id"], 状態)
    return {"ok": True}


@ルート("PUT", "/api/players/{選手ID}/steps/override", 権限="コーチ")
def 提示メニュー上書き(リクエスト_: リクエスト, 選手ID: int):
    """自動提示の代わりに、コーチが指定したドリルをその選手に提示する。drill_id を空にすると解除。"""
    選手を確認(リクエスト_, 選手ID)
    本文 = リクエスト_.本文
    カテゴリID = 整数(本文, "category_id", "スキル", 1, 10**9, 既定=None)
    チーム内の行(リクエスト_, "skill_categories", カテゴリID, "スキル")
    if 本文.get("drill_id") in (None, "", 0):
        リクエスト_.db.execute("DELETE FROM step_overrides WHERE player_id = ? AND category_id = ?", (選手ID, カテゴリID))
        return {"ok": True}
    ドリル = チーム内の行(リクエスト_, "drill_steps", 整数(本文, "drill_id", "ドリル", 1, 10**9), "ドリル")
    if ドリル["category_id"] != カテゴリID:
        raise APIエラー(400, "スキルとドリルの組み合わせが正しくありません")
    リクエスト_.db.execute(
        """INSERT INTO step_overrides (player_id, category_id, team_id, drill_id, note, updated_at) VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT (player_id, category_id) DO UPDATE SET drill_id = excluded.drill_id, note = excluded.note, updated_at = excluded.updated_at""",
        (選手ID, カテゴリID, リクエスト_.チームID, ドリル["id"], 文字列(本文, "note", "コーチからのメモ", 最大=200), 現在時刻()),
    )
    進捗 = リクエスト_.db.execute("SELECT status FROM player_step_progress WHERE player_id = ? AND drill_id = ?", (選手ID, ドリル["id"])).fetchone()
    if 進捗 is None or 進捗["status"] == "完了":
        _進捗を更新(リクエスト_, 選手ID, ドリル["id"], "実施中")
    return {"ok": True}


@ルート("GET", "/api/steps/overview", 権限="コーチ")
def ステップ一覧表(リクエスト_: リクエスト):
    """チーム全選手 × スキルの ステップ進行状況（現在のドリル・完了数）の一覧。"""
    選手一覧 = リクエスト_.db.execute(
        """SELECT id, name, number, grade, position FROM users WHERE team_id = ? AND role = 'player' AND active = 1
           ORDER BY CASE WHEN number GLOB '[0-9]*' THEN CAST(number AS INTEGER) ELSE 9999 END, name""",
        (リクエスト_.チームID,),
    ).fetchall()
    最終報告 = {
        行["player_id"]: 行["last"]
        for 行 in リクエスト_.db.execute(
            "SELECT player_id, MAX(date) AS last FROM step_reports WHERE team_id = ? GROUP BY player_id", (リクエスト_.チームID,)
        ).fetchall()
    }
    結果 = []
    for 選手 in 選手一覧:
        状況一覧 = _選手のステップ状況(リクエスト_, 選手["id"])
        結果.append(
            {
                "player": dict(選手),
                "last_report": 最終報告.get(選手["id"], ""),
                "categories": [
                    {
                        "category_id": s["category_id"],
                        "category_name": s["category_name"],
                        "level": s["diagnosis"]["level"],
                        "value": s["diagnosis"]["value"],
                        "priority": s["diagnosis"]["priority"],
                        "completed": s["completed"],
                        "total": s["total"],
                        "current": {"id": s["current"]["id"], "title": s["current"]["title"], "level": s["current"]["level"], "order": s["current"]["order"], "status": s["current"]["status"]} if s["current"] else None,
                        "overridden": bool(s["override"]),
                    }
                    for s in 状況一覧
                ],
            }
        )
    return {"categories": _カテゴリ一覧(リクエスト_), "players": 結果}
