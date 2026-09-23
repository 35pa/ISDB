"""選手カルテの API：個人課題・スタッツ・シュートチャート・成長記録カレンダー・自主練・フィードバック・目標。"""

from __future__ import annotations

import json
import re

import 集計
from データベース import 今日, 現在時刻, 行一覧を辞書に
from ルーティング import (
    APIエラー,
    リクエスト,
    ルート,
    チーム内の行,
    公開ユーザー情報,
    整数,
    文字列,
    日付,
    選択,
    選手を確認,
    最大文字数_長,
)


def _選手のスタッツ(リクエスト_: リクエスト, 選手ID: int) -> list[dict]:
    """新しい順。"""
    行一覧 = 行一覧を辞書に(
        リクエスト_.db.execute("SELECT * FROM stats WHERE player_id = ? AND team_id = ? ORDER BY date DESC, id DESC", (選手ID, リクエスト_.チームID)).fetchall()
    )
    for 行 in 行一覧:
        行["zones"] = json.loads(行["zones"] or "{}")
    return 行一覧


# ---------- カルテ ----------


@ルート("GET", "/api/players/{選手ID}/karte")
def 選手カルテ(リクエスト_: リクエスト, 選手ID: int):
    選手 = 選手を確認(リクエスト_, 選手ID)
    db = リクエスト_.db
    スタッツ = _選手のスタッツ(リクエスト_, 選手ID)
    return {
        "player": 公開ユーザー情報(選手),
        "issues": 行一覧を辞書に(
            db.execute("SELECT * FROM issues WHERE player_id = ? AND team_id = ? ORDER BY status = '解決', updated_at DESC", (選手ID, リクエスト_.チームID)).fetchall()
        ),
        "stats_summary": 集計.スタッツを集計(スタッツ),
        "stats": スタッツ[:20],
        "feedback": _フィードバック一覧(リクエスト_, 選手ID)[:5],
        "goals": 行一覧を辞書に(
            db.execute("SELECT * FROM goals WHERE team_id = ? AND scope = '個人' AND user_id = ? ORDER BY status != '進行中', deadline", (リクエスト_.チームID, 選手ID)).fetchall()
        ),
    }


# ---------- 個人課題 ----------


@ルート("POST", "/api/players/{選手ID}/issues")
def 課題追加(リクエスト_: リクエスト, 選手ID: int):
    選手を確認(リクエスト_, 選手ID)
    タイトル = 文字列(リクエスト_.本文, "title", "課題", 必須=True, 最大=100)
    詳細 = 文字列(リクエスト_.本文, "detail", "詳細", 最大=最大文字数_長)
    時刻 = 現在時刻()
    課題ID = リクエスト_.db.execute(
        "INSERT INTO issues (team_id, player_id, title, detail, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (リクエスト_.チームID, 選手ID, タイトル, 詳細, リクエスト_.ユーザー["id"], 時刻, 時刻),
    ).lastrowid
    return {"id": 課題ID}


@ルート("PUT", "/api/issues/{課題ID}")
def 課題編集(リクエスト_: リクエスト, 課題ID: int):
    課題 = チーム内の行(リクエスト_, "issues", 課題ID, "課題")
    選手を確認(リクエスト_, 課題["player_id"])
    本文 = リクエスト_.本文
    リクエスト_.db.execute(
        "UPDATE issues SET title = ?, detail = ?, status = ?, updated_at = ? WHERE id = ?",
        (
            文字列(本文, "title", "課題", 必須=True, 最大=100, 既定=課題["title"]),
            文字列(本文, "detail", "詳細", 最大=最大文字数_長, 既定=課題["detail"]),
            選択(本文, "status", "状態", ("取組中", "解決"), 既定=課題["status"]),
            現在時刻(),
            課題ID,
        ),
    )
    return {"id": 課題ID}


@ルート("DELETE", "/api/issues/{課題ID}")
def 課題削除(リクエスト_: リクエスト, 課題ID: int):
    課題 = チーム内の行(リクエスト_, "issues", 課題ID, "課題")
    選手を確認(リクエスト_, 課題["player_id"])
    リクエスト_.db.execute("DELETE FROM issues WHERE id = ?", (課題ID,))
    return {"ok": True}


# ---------- スタッツ ----------


def _スタッツ入力(本文: dict) -> dict:
    値 = {
        "date": 日付(本文, "date", "日付"),
        "label": 文字列(本文, "label", "試合名", 最大=60),
    }
    名前 = {
        "minutes": "出場時間", "rebounds": "リバウンド", "assists": "アシスト", "steals": "スティール",
        "blocks": "ブロック", "turnovers": "ターンオーバー", "fgm": "FG成功", "fga": "FG試投",
        "tpm": "3P成功", "tpa": "3P試投", "ftm": "FT成功", "fta": "FT試投",
    }
    for キー, 表示名 in 名前.items():
        値[キー] = 整数(本文, キー, 表示名, 0, 200)
    try:
        値["zones"] = 集計.エリア内訳を検証(本文.get("zones"))
    except (ValueError, TypeError, AttributeError, json.JSONDecodeError) as エラー:
        raise APIエラー(400, str(エラー) if isinstance(エラー, ValueError) else "シュートエリアの形式が正しくありません") from None
    エリア試投 = sum(v["a"] for v in 値["zones"].values())
    エリア成功 = sum(v["m"] for v in 値["zones"].values())
    if エリア試投 and not 値["fga"]:
        # エリア別だけ入力された場合は合計を自動で埋める
        値["fga"], 値["fgm"] = エリア試投, エリア成功
        値["tpa"] = sum(v["a"] for k, v in 値["zones"].items() if k.startswith("3P"))
        値["tpm"] = sum(v["m"] for k, v in 値["zones"].items() if k.startswith("3P"))
    if 値["fgm"] > 値["fga"] or 値["tpm"] > 値["tpa"] or 値["ftm"] > 値["fta"]:
        raise APIエラー(400, "成功数が試投数を超えています")
    if 値["tpa"] > 値["fga"] or 値["tpm"] > 値["fgm"]:
        raise APIエラー(400, "3Pの数はFG（全シュート）の数に含めて入力してください")
    if エリア試投 > 値["fga"]:
        raise APIエラー(400, "エリア別の試投数の合計がFG試投数を超えています")
    if 本文.get("points") in (None, ""):
        値["points"] = 集計.得点を検算(値)
    else:
        値["points"] = 整数(本文, "points", "得点", 0, 200)
    return 値


def _スタッツ保存(リクエスト_: リクエスト, 選手ID: int, 値: dict, スタッツID: int | None = None) -> int:
    列 = ("date", "label", "minutes", "points", "rebounds", "assists", "steals", "blocks", "turnovers", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "zones")
    データ = [json.dumps(値[k], ensure_ascii=False) if k == "zones" else 値[k] for k in 列]
    if スタッツID is None:
        return リクエスト_.db.execute(
            f"INSERT INTO stats (team_id, player_id, {', '.join(列)}, created_at) VALUES (?, ?, {', '.join('?' * len(列))}, ?)",
            (リクエスト_.チームID, 選手ID, *データ, 現在時刻()),
        ).lastrowid
    リクエスト_.db.execute(f"UPDATE stats SET {', '.join(f'{k} = ?' for k in 列)} WHERE id = ?", (*データ, スタッツID))
    return スタッツID


@ルート("GET", "/api/players/{選手ID}/stats")
def スタッツ一覧(リクエスト_: リクエスト, 選手ID: int):
    選手を確認(リクエスト_, 選手ID)
    スタッツ = _選手のスタッツ(リクエスト_, 選手ID)
    return {"rows": スタッツ, "summary": 集計.スタッツを集計(スタッツ)}


@ルート("POST", "/api/players/{選手ID}/stats", 権限="コーチ")
def スタッツ追加(リクエスト_: リクエスト, 選手ID: int):
    選手を確認(リクエスト_, 選手ID)
    return {"id": _スタッツ保存(リクエスト_, 選手ID, _スタッツ入力(リクエスト_.本文))}


@ルート("POST", "/api/stats/game", 権限="コーチ")
def 試合スタッツ一括登録(リクエスト_: リクエスト):
    """1試合分をまとめて登録。{date, label, rows: [{player_id, points, ...}]}"""
    本文 = リクエスト_.本文
    行一覧 = 本文.get("rows")
    if not isinstance(行一覧, list) or not 1 <= len(行一覧) <= 30:
        raise APIエラー(400, "選手ごとのスタッツを1人以上入力してください")
    入力 = []
    for 行 in 行一覧:
        if not isinstance(行, dict):
            raise APIエラー(400, "スタッツの形式が正しくありません")
        選手ID = 整数(行, "player_id", "選手", 1, 10**9, 既定=None)
        選手 = 選手を確認(リクエスト_, 選手ID)
        try:
            入力.append((選手ID, _スタッツ入力({**行, "date": 本文.get("date"), "label": 本文.get("label", "")})))
        except APIエラー as エラー:
            raise APIエラー(400, f"{選手['name']}：{エラー.メッセージ}") from None
    return {"ids": [_スタッツ保存(リクエスト_, 選手ID, 値) for 選手ID, 値 in 入力]}


@ルート("PUT", "/api/stats/{スタッツID}", 権限="コーチ")
def スタッツ編集(リクエスト_: リクエスト, スタッツID: int):
    元 = チーム内の行(リクエスト_, "stats", スタッツID, "スタッツ")
    return {"id": _スタッツ保存(リクエスト_, 元["player_id"], _スタッツ入力(リクエスト_.本文), スタッツID)}


@ルート("DELETE", "/api/stats/{スタッツID}", 権限="コーチ")
def スタッツ削除(リクエスト_: リクエスト, スタッツID: int):
    チーム内の行(リクエスト_, "stats", スタッツID, "スタッツ")
    リクエスト_.db.execute("DELETE FROM stats WHERE id = ?", (スタッツID,))
    return {"ok": True}


@ルート("GET", "/api/stats/team")
def チームスタッツ(リクエスト_: リクエスト):
    """選手別の1試合平均・成功率の一覧（チーム内ランキング用）。"""
    選手一覧 = リクエスト_.db.execute(
        "SELECT * FROM users WHERE team_id = ? AND role = 'player' AND active = 1 ORDER BY CAST(number AS INTEGER), name",
        (リクエスト_.チームID,),
    ).fetchall()
    結果 = []
    for 選手 in 選手一覧:
        要約 = 集計.スタッツを集計(_選手のスタッツ(リクエスト_, 選手["id"]))
        結果.append(
            {
                "player": {"id": 選手["id"], "name": 選手["name"], "number": 選手["number"], "position": 選手["position"]},
                "games": 要約["games"],
                "averages": 要約["averages"],
                "fg_pct": 要約["fg_pct"],
                "tp_pct": 要約["tp_pct"],
                "ft_pct": 要約["ft_pct"],
            }
        )
    return 結果


# ---------- 自主練・成長記録カレンダー ----------


@ルート("POST", "/api/players/{選手ID}/practice-logs")
def 自主練記録(リクエスト_: リクエスト, 選手ID: int):
    選手を確認(リクエスト_, 選手ID)
    本文 = リクエスト_.本文
    記録ID = リクエスト_.db.execute(
        "INSERT INTO practice_logs (team_id, player_id, date, minutes, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            リクエスト_.チームID,
            選手ID,
            日付(本文, "date", "日付", 必須=False) or 今日(),
            整数(本文, "minutes", "時間（分）", 1, 600, 既定=None),
            文字列(本文, "content", "内容", 必須=True, 最大=300),
            現在時刻(),
        ),
    ).lastrowid
    return {"id": 記録ID}


@ルート("DELETE", "/api/practice-logs/{記録ID}")
def 自主練削除(リクエスト_: リクエスト, 記録ID: int):
    記録 = チーム内の行(リクエスト_, "practice_logs", 記録ID, "自主練の記録")
    選手を確認(リクエスト_, 記録["player_id"])
    リクエスト_.db.execute("DELETE FROM practice_logs WHERE id = ?", (記録ID,))
    return {"ok": True}


@ルート("GET", "/api/players/{選手ID}/calendar")
def 成長記録(リクエスト_: リクエスト, 選手ID: int):
    選手を確認(リクエスト_, 選手ID)
    月指定 = リクエスト_.クエリ.get("month") or 今日()[:7]
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", 月指定):
        raise APIエラー(400, "月は YYYY-MM 形式で指定してください")
    年, 月 = int(月指定[:4]), int(月指定[5:])
    範囲 = (f"{月指定}-01", f"{月指定}-31")
    db = リクエスト_.db
    出欠 = 行一覧を辞書に(
        db.execute(
            """SELECT e.date, e.title, e.kind, a.status FROM attendance a JOIN events e ON e.id = a.event_id
               WHERE a.user_id = ? AND e.team_id = ? AND e.date BETWEEN ? AND ?""",
            (選手ID, リクエスト_.チームID, *範囲),
        ).fetchall()
    )
    報告 = 行一覧を辞書に(
        db.execute(
            """SELECT r.date, d.title, r.cleared FROM step_reports r JOIN drill_steps d ON d.id = r.drill_id
               WHERE r.player_id = ? AND r.team_id = ? AND r.date BETWEEN ? AND ?""",
            (選手ID, リクエスト_.チームID, *範囲),
        ).fetchall()
    )
    自主練 = 行一覧を辞書に(
        db.execute(
            "SELECT id, date, minutes, content FROM practice_logs WHERE player_id = ? AND team_id = ? AND date BETWEEN ? AND ?",
            (選手ID, リクエスト_.チームID, *範囲),
        ).fetchall()
    )
    return 集計.成長記録カレンダー(年, 月, 出欠, 報告, 自主練)


# ---------- フィードバック ----------


def _フィードバック一覧(リクエスト_: リクエスト, 選手ID: int) -> list[dict]:
    return 行一覧を辞書に(
        リクエスト_.db.execute(
            """SELECT f.*, u.name AS coach_name FROM feedback f LEFT JOIN users u ON u.id = f.coach_id
               WHERE f.player_id = ? AND f.team_id = ? ORDER BY f.created_at DESC, f.id DESC""",
            (選手ID, リクエスト_.チームID),
        ).fetchall()
    )


@ルート("GET", "/api/players/{選手ID}/feedback")
def フィードバック一覧(リクエスト_: リクエスト, 選手ID: int):
    選手を確認(リクエスト_, 選手ID)
    return _フィードバック一覧(リクエスト_, 選手ID)


@ルート("POST", "/api/players/{選手ID}/feedback", 権限="コーチ")
def フィードバック送信(リクエスト_: リクエスト, 選手ID: int):
    選手を確認(リクエスト_, 選手ID)
    内容 = 文字列(リクエスト_.本文, "body", "コメント", 必須=True, 最大=2000)
    フィードバックID = リクエスト_.db.execute(
        "INSERT INTO feedback (team_id, player_id, coach_id, body, created_at) VALUES (?, ?, ?, ?, ?)",
        (リクエスト_.チームID, 選手ID, リクエスト_.ユーザー["id"], 内容, 現在時刻()),
    ).lastrowid
    return {"id": フィードバックID}


@ルート("POST", "/api/feedback/{フィードバックID}/confirm")
def フィードバック確認(リクエスト_: リクエスト, フィードバックID: int):
    行 = チーム内の行(リクエスト_, "feedback", フィードバックID, "フィードバック")
    if 行["player_id"] != リクエスト_.ユーザー["id"]:
        raise APIエラー(403, "本人のみ確認できます")
    返信 = 文字列(リクエスト_.本文, "reply", "返信", 最大=1000)
    リクエスト_.db.execute("UPDATE feedback SET confirmed_at = ?, reply = ? WHERE id = ?", (現在時刻(), 返信, フィードバックID))
    return {"ok": True}


@ルート("DELETE", "/api/feedback/{フィードバックID}", 権限="コーチ")
def フィードバック削除(リクエスト_: リクエスト, フィードバックID: int):
    チーム内の行(リクエスト_, "feedback", フィードバックID, "フィードバック")
    リクエスト_.db.execute("DELETE FROM feedback WHERE id = ?", (フィードバックID,))
    return {"ok": True}


# ---------- 目標 ----------


def _目標の権限(リクエスト_: リクエスト, 目標: dict) -> None:
    if リクエスト_.コーチか:
        return
    if 目標["scope"] == "チーム" or 目標["user_id"] != リクエスト_.ユーザー["id"]:
        raise APIエラー(403, "チーム目標と他の選手の目標はコーチのみ編集できます")


@ルート("GET", "/api/goals")
def 目標一覧(リクエスト_: リクエスト):
    条件 = "g.team_id = ? AND (g.scope = 'チーム' OR (u.active = 1 AND (? OR g.user_id = ?)))"
    引数: list = [リクエスト_.チームID, int(リクエスト_.コーチか), リクエスト_.ユーザー["id"]]
    if リクエスト_.クエリ.get("user_id", "").isdigit():
        条件 += " AND (g.scope = 'チーム' OR g.user_id = ?)"
        引数.append(int(リクエスト_.クエリ["user_id"]))
    return 行一覧を辞書に(
        リクエスト_.db.execute(
            f"""SELECT g.*, u.name AS user_name FROM goals g LEFT JOIN users u ON u.id = g.user_id
                WHERE {条件} ORDER BY g.scope = '個人', g.status != '進行中', g.deadline = '', g.deadline, g.id""",
            引数,
        ).fetchall()
    )


def _目標入力(本文: dict, 既存: dict | None = None) -> tuple:
    既 = 既存 or {}
    return (
        文字列(本文, "content", "目標", 必須=True, 最大=300, 既定=既.get("content", "")),
        日付(本文, "deadline", "期限", 必須=False) if "deadline" in 本文 else 既.get("deadline", ""),
        整数(本文, "progress", "達成度", 0, 100, 既定=既.get("progress", 0)),
        選択(本文, "status", "状態", ("進行中", "達成", "未達成"), 既定=既.get("status", "進行中")),
        文字列(本文, "reflection", "振り返り", 最大=2000, 既定=既.get("reflection", "")),
    )


@ルート("POST", "/api/goals")
def 目標作成(リクエスト_: リクエスト):
    本文 = リクエスト_.本文
    範囲 = 選択(本文, "scope", "対象", ("個人", "チーム"), 既定="個人")
    対象ID = None
    if 範囲 == "チーム":
        if not リクエスト_.コーチか:
            raise APIエラー(403, "チーム目標はコーチのみ設定できます")
    else:
        対象ID = リクエスト_.ユーザー["id"] if not リクエスト_.コーチか else 整数(本文, "user_id", "選手", 1, 10**9, 既定=None)
        選手を確認(リクエスト_, 対象ID)
    時刻 = 現在時刻()
    目標ID = リクエスト_.db.execute(
        """INSERT INTO goals (team_id, scope, user_id, content, deadline, progress, status, reflection, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (リクエスト_.チームID, 範囲, 対象ID, *_目標入力(本文), 時刻, 時刻),
    ).lastrowid
    return {"id": 目標ID}


@ルート("PUT", "/api/goals/{目標ID}")
def 目標編集(リクエスト_: リクエスト, 目標ID: int):
    目標 = チーム内の行(リクエスト_, "goals", 目標ID, "目標")
    _目標の権限(リクエスト_, 目標)
    リクエスト_.db.execute(
        "UPDATE goals SET content = ?, deadline = ?, progress = ?, status = ?, reflection = ?, updated_at = ? WHERE id = ?",
        (*_目標入力(リクエスト_.本文, 目標), 現在時刻(), 目標ID),
    )
    return {"id": 目標ID}


@ルート("DELETE", "/api/goals/{目標ID}")
def 目標削除(リクエスト_: リクエスト, 目標ID: int):
    目標 = チーム内の行(リクエスト_, "goals", 目標ID, "目標")
    _目標の権限(リクエスト_, 目標)
    リクエスト_.db.execute("DELETE FROM goals WHERE id = ?", (目標ID,))
    return {"ok": True}
