"""練習メニュー（テンプレート）と予定（練習・試合カレンダー）・出欠の API。"""

from __future__ import annotations

from データベース import 現在時刻, 行一覧を辞書に
from ルーティング import (
    APIエラー,
    リクエスト,
    ルート,
    チーム内の行,
    整数,
    文字列,
    日付,
    時刻,
    真偽,
    選択,
    最大文字数_長,
)

出欠の選択肢 = ("出席", "欠席", "遅刻", "早退")
予定の種類 = ("練習", "試合", "その他")


# ---------- 練習メニュー ----------


def _メニュー入力(本文: dict) -> tuple:
    return (
        文字列(本文, "name", "ドリル名", 必須=True, 最大=60),
        文字列(本文, "purpose", "目的", 最大=200),
        整数(本文, "minutes", "所要時間（分）", 0, 600),
        文字列(本文, "equipment", "使用道具", 最大=200),
        文字列(本文, "category", "分類", 最大=30),
        文字列(本文, "description", "やり方", 最大=最大文字数_長),
    )


@ルート("GET", "/api/menus")
def メニュー一覧(リクエスト_: リクエスト):
    キーワード = リクエスト_.クエリ.get("q", "").strip()
    条件 = "m.team_id = ?"
    引数: list = [リクエスト_.チームID]
    if キーワード:
        条件 += " AND (m.name LIKE ? OR m.purpose LIKE ? OR m.category LIKE ? OR m.equipment LIKE ?)"
        引数 += [f"%{キーワード}%"] * 4
    return 行一覧を辞書に(
        リクエスト_.db.execute(
            f"""SELECT m.*, (SELECT COUNT(*) FROM event_menus em WHERE em.menu_id = m.id) AS used_count,
                   (SELECT MAX(e.date) FROM event_menus em JOIN events e ON e.id = em.event_id WHERE em.menu_id = m.id) AS last_used
                FROM menus m WHERE {条件} ORDER BY m.category, m.name""",
            引数,
        ).fetchall()
    )


@ルート("POST", "/api/menus", 権限="コーチ")
def メニュー作成(リクエスト_: リクエスト):
    値 = _メニュー入力(リクエスト_.本文)
    メニューID = リクエスト_.db.execute(
        """INSERT INTO menus (team_id, name, purpose, minutes, equipment, category, description, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (リクエスト_.チームID, *値, 現在時刻()),
    ).lastrowid
    return チーム内の行(リクエスト_, "menus", メニューID)


@ルート("PUT", "/api/menus/{メニューID}", 権限="コーチ")
def メニュー編集(リクエスト_: リクエスト, メニューID: int):
    チーム内の行(リクエスト_, "menus", メニューID, "練習メニュー")
    値 = _メニュー入力(リクエスト_.本文)
    リクエスト_.db.execute(
        "UPDATE menus SET name = ?, purpose = ?, minutes = ?, equipment = ?, category = ?, description = ? WHERE id = ?",
        (*値, メニューID),
    )
    return チーム内の行(リクエスト_, "menus", メニューID)


@ルート("DELETE", "/api/menus/{メニューID}", 権限="コーチ")
def メニュー削除(リクエスト_: リクエスト, メニューID: int):
    チーム内の行(リクエスト_, "menus", メニューID, "練習メニュー")
    リクエスト_.db.execute("DELETE FROM menus WHERE id = ?", (メニューID,))
    return {"ok": True}


# ---------- 予定（カレンダー） ----------


def _予定入力(リクエスト_: リクエスト) -> dict:
    本文 = リクエスト_.本文
    値 = {
        "kind": 選択(本文, "kind", "種類", 予定の種類, 既定="練習"),
        "title": 文字列(本文, "title", "タイトル", 最大=60),
        "date": 日付(本文, "date", "日付"),
        "start_time": 時刻(本文, "start_time", "開始時刻"),
        "end_time": 時刻(本文, "end_time", "終了時刻"),
        "place": 文字列(本文, "place", "場所", 最大=60),
        "notes": 文字列(本文, "notes", "メモ", 最大=最大文字数_長),
        "published": 真偽(本文, "published", True),
    }
    if not 値["title"]:
        値["title"] = 値["kind"]
    if 値["start_time"] and 値["end_time"] and 値["end_time"] < 値["start_time"]:
        raise APIエラー(400, "終了時刻は開始時刻より後にしてください")
    メニューID一覧 = 本文.get("menu_ids", [])
    if not isinstance(メニューID一覧, list) or len(メニューID一覧) > 50:
        raise APIエラー(400, "練習メニューの指定が正しくありません")
    for メニューID in メニューID一覧:
        if not isinstance(メニューID, int):
            raise APIエラー(400, "練習メニューの指定が正しくありません")
        チーム内の行(リクエスト_, "menus", メニューID, "練習メニュー")
    値["menu_ids"] = メニューID一覧
    return 値


def _メニューを保存(リクエスト_: リクエスト, 予定ID: int, メニューID一覧: list[int]) -> None:
    リクエスト_.db.execute("DELETE FROM event_menus WHERE event_id = ?", (予定ID,))
    for 順番, メニューID in enumerate(メニューID一覧):
        リクエスト_.db.execute("INSERT INTO event_menus (event_id, menu_id, sort) VALUES (?, ?, ?)", (予定ID, メニューID, 順番))


def _予定を取得(リクエスト_: リクエスト, 予定ID: int) -> dict:
    予定 = チーム内の行(リクエスト_, "events", 予定ID, "予定")
    if not 予定["published"] and not リクエスト_.コーチか:
        raise APIエラー(404, "予定が見つかりません")
    return 予定


@ルート("GET", "/api/events")
def 予定一覧(リクエスト_: リクエスト):
    """期間（from/to）・キーワード（q：タイトル・メモ・メニュー名）・種類で絞り込み。練習履歴の検索にも使う。"""
    クエリ = リクエスト_.クエリ
    条件 = ["e.team_id = ?"]
    引数: list = [リクエスト_.ユーザー["id"], リクエスト_.チームID]
    if not リクエスト_.コーチか:
        条件.append("e.published = 1")
    if クエリ.get("from"):
        条件.append("e.date >= ?")
        引数.append(日付(クエリ, "from", "開始日"))
    if クエリ.get("to"):
        条件.append("e.date <= ?")
        引数.append(日付(クエリ, "to", "終了日"))
    if クエリ.get("kind") in 予定の種類:
        条件.append("e.kind = ?")
        引数.append(クエリ["kind"])
    if クエリ.get("menu_id", "").isdigit():
        条件.append("EXISTS (SELECT 1 FROM event_menus em WHERE em.event_id = e.id AND em.menu_id = ?)")
        引数.append(int(クエリ["menu_id"]))
    if クエリ.get("q", "").strip():
        キーワード = f"%{クエリ['q'].strip()}%"
        条件.append(
            """(e.title LIKE ? OR e.notes LIKE ? OR e.place LIKE ? OR EXISTS (
                 SELECT 1 FROM event_menus em JOIN menus m ON m.id = em.menu_id
                 WHERE em.event_id = e.id AND m.name LIKE ?))"""
        )
        引数 += [キーワード] * 4
    並び = "DESC" if クエリ.get("order") == "desc" else "ASC"
    予定 = 行一覧を辞書に(
        リクエスト_.db.execute(
            f"""SELECT e.*, a.status AS my_status,
                   (SELECT COUNT(*) FROM attendance x JOIN users xu ON xu.id = x.user_id AND xu.active = 1
                      WHERE x.event_id = e.id AND x.status IN ('出席', '遅刻', '早退')) AS attend_count,
                   (SELECT COUNT(*) FROM attendance x JOIN users xu ON xu.id = x.user_id AND xu.active = 1
                      WHERE x.event_id = e.id) AS answered_count,
                   (SELECT COALESCE(SUM(m.minutes), 0) FROM event_menus em JOIN menus m ON m.id = em.menu_id
                      WHERE em.event_id = e.id) AS total_minutes
                FROM events e LEFT JOIN attendance a ON a.event_id = e.id AND a.user_id = ?
                WHERE {' AND '.join(条件)} ORDER BY e.date {並び}, e.start_time {並び} LIMIT 500""",
            引数,
        ).fetchall()
    )
    if 予定:
        ID一覧 = [行["id"] for 行 in 予定]
        メニュー = リクエスト_.db.execute(
            f"""SELECT em.event_id, m.id, m.name, m.minutes FROM event_menus em JOIN menus m ON m.id = em.menu_id
                WHERE em.event_id IN ({','.join('?' * len(ID一覧))}) ORDER BY em.event_id, em.sort""",
            ID一覧,
        ).fetchall()
        対応: dict[int, list] = {}
        for 行 in メニュー:
            対応.setdefault(行["event_id"], []).append({"id": 行["id"], "name": 行["name"], "minutes": 行["minutes"]})
        for 行 in 予定:
            行["menus"] = 対応.get(行["id"], [])
    return 予定


@ルート("POST", "/api/events", 権限="コーチ")
def 予定作成(リクエスト_: リクエスト):
    値 = _予定入力(リクエスト_)
    予定ID = リクエスト_.db.execute(
        """INSERT INTO events (team_id, kind, title, date, start_time, end_time, place, notes, published, created_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (リクエスト_.チームID, 値["kind"], 値["title"], 値["date"], 値["start_time"], 値["end_time"], 値["place"], 値["notes"], 値["published"], リクエスト_.ユーザー["id"], 現在時刻()),
    ).lastrowid
    _メニューを保存(リクエスト_, 予定ID, 値["menu_ids"])
    return {"id": 予定ID}


@ルート("POST", "/api/events/{予定ID}/copy", 権限="コーチ")
def 予定複製(リクエスト_: リクエスト, 予定ID: int):
    """過去の練習を別の日にそのまま再利用する（メニュー構成ごとコピー）。"""
    元 = チーム内の行(リクエスト_, "events", 予定ID, "予定")
    新しい日付 = 日付(リクエスト_.本文, "date", "日付")
    新ID = リクエスト_.db.execute(
        """INSERT INTO events (team_id, kind, title, date, start_time, end_time, place, notes, published, created_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (リクエスト_.チームID, 元["kind"], 元["title"], 新しい日付, 元["start_time"], 元["end_time"], 元["place"], 元["notes"], 元["published"], リクエスト_.ユーザー["id"], 現在時刻()),
    ).lastrowid
    リクエスト_.db.execute(
        "INSERT INTO event_menus (event_id, menu_id, sort) SELECT ?, menu_id, sort FROM event_menus WHERE event_id = ?",
        (新ID, 予定ID),
    )
    return {"id": 新ID}


@ルート("GET", "/api/events/{予定ID}")
def 予定詳細(リクエスト_: リクエスト, 予定ID: int):
    予定 = _予定を取得(リクエスト_, 予定ID)
    db = リクエスト_.db
    自分ID = リクエスト_.ユーザー["id"]
    db.execute("INSERT OR IGNORE INTO event_views (event_id, user_id, viewed_at) VALUES (?, ?, ?)", (予定ID, 自分ID, 現在時刻()))
    予定["menus"] = 行一覧を辞書に(
        db.execute(
            """SELECT m.* FROM event_menus em JOIN menus m ON m.id = em.menu_id
               WHERE em.event_id = ? ORDER BY em.sort""",
            (予定ID,),
        ).fetchall()
    )
    メンバー = 行一覧を辞書に(
        db.execute(
            """SELECT u.id, u.name, u.role, u.number, u.grade, a.status, a.comment, a.updated_at, v.viewed_at
               FROM users u
               LEFT JOIN attendance a ON a.event_id = ? AND a.user_id = u.id
               LEFT JOIN event_views v ON v.event_id = ? AND v.user_id = u.id
               WHERE u.team_id = ? AND u.active = 1
               ORDER BY u.role, CASE WHEN u.number GLOB '[0-9]*' THEN CAST(u.number AS INTEGER) ELSE 9999 END, u.name""",
            (予定ID, 予定ID, リクエスト_.チームID),
        ).fetchall()
    )
    集計 = {状態: sum(1 for 行 in メンバー if 行["status"] == 状態) for 状態 in 出欠の選択肢}
    集計["未回答"] = sum(1 for 行 in メンバー if not 行["status"])
    集計["既読"] = sum(1 for 行 in メンバー if 行["viewed_at"])
    自分 = next((行 for 行 in メンバー if 行["id"] == 自分ID), None)
    予定["my_status"] = 自分["status"] if 自分 else None
    予定["my_comment"] = 自分["comment"] if 自分 else ""
    予定["summary"] = 集計
    予定["member_count"] = len(メンバー)
    予定["attendance"] = メンバー  # 出欠一覧はチーム全員が見られる（誰が来るか分かるように）
    予定["total_minutes"] = sum(int(m["minutes"] or 0) for m in 予定["menus"])
    return 予定


@ルート("PUT", "/api/events/{予定ID}", 権限="コーチ")
def 予定編集(リクエスト_: リクエスト, 予定ID: int):
    チーム内の行(リクエスト_, "events", 予定ID, "予定")
    値 = _予定入力(リクエスト_)
    リクエスト_.db.execute(
        """UPDATE events SET kind = ?, title = ?, date = ?, start_time = ?, end_time = ?, place = ?, notes = ?, published = ?
           WHERE id = ?""",
        (値["kind"], 値["title"], 値["date"], 値["start_time"], 値["end_time"], 値["place"], 値["notes"], 値["published"], 予定ID),
    )
    _メニューを保存(リクエスト_, 予定ID, 値["menu_ids"])
    return {"id": 予定ID}


@ルート("DELETE", "/api/events/{予定ID}", 権限="コーチ")
def 予定削除(リクエスト_: リクエスト, 予定ID: int):
    チーム内の行(リクエスト_, "events", 予定ID, "予定")
    リクエスト_.db.execute("DELETE FROM events WHERE id = ?", (予定ID,))
    return {"ok": True}


@ルート("PUT", "/api/events/{予定ID}/attendance")
def 出欠回答(リクエスト_: リクエスト, 予定ID: int):
    """本人の出欠を登録。コーチは user_id を指定して他のメンバーの出欠も代理入力できる。"""
    _予定を取得(リクエスト_, 予定ID)
    本文 = リクエスト_.本文
    対象ID = リクエスト_.ユーザー["id"]
    if 本文.get("user_id") not in (None, "", 対象ID):
        if not リクエスト_.コーチか:
            raise APIエラー(403, "他のメンバーの出欠はコーチのみ入力できます")
        対象ID = 整数(本文, "user_id", "メンバー", 1, 10**9)
        対象 = チーム内の行(リクエスト_, "users", 対象ID, "メンバー")
        if not 対象["active"]:
            raise APIエラー(404, "メンバーが見つかりません")
    状態 = 本文.get("status")
    if 状態 in (None, ""):
        リクエスト_.db.execute("DELETE FROM attendance WHERE event_id = ? AND user_id = ?", (予定ID, 対象ID))
        return {"ok": True}
    状態 = 選択(本文, "status", "出欠", 出欠の選択肢)
    コメント = 文字列(本文, "comment", "コメント", 最大=200)
    リクエスト_.db.execute(
        """INSERT INTO attendance (event_id, user_id, status, comment, updated_at) VALUES (?, ?, ?, ?, ?)
           ON CONFLICT (event_id, user_id) DO UPDATE SET status = excluded.status, comment = excluded.comment, updated_at = excluded.updated_at""",
        (予定ID, 対象ID, 状態, コメント, 現在時刻()),
    )
    return {"ok": True}
