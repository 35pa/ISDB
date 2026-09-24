"""作戦ボード（戦術図）・戦術テンプレート・理解度チェック（クイズ／コメント）の API。

図データの形式（ハーフコート 横500×縦470、上がゴール側）:
{"frames": [{"players": [{"id": "O1", "team": "O", "label": "1", "x": 250, "y": 330}, ...],
             "ball": "O1",
             "lines": [{"type": "move|pass|dribble|screen", "points": [[x, y], ...]}],
             "note": "このコマの説明"}]}
コマ（frames）を順番に見せることでセットプレーの流れを表現する。
"""

from __future__ import annotations

import json

from データベース import 現在時刻, 行一覧を辞書に
from ルーティング import (
    APIエラー,
    リクエスト,
    ルート,
    チーム内の行,
    整数,
    文字列,
    真偽,
    選択,
    最大文字数_長,
)

戦術の種別 = ("オフェンス", "ディフェンス")
線の種類 = ("move", "pass", "dribble", "screen")
コート幅 = 500
コート奥行 = 470
理解度 = {0: "よく分からない", 1: "だいたい分かった", 2: "理解した"}


def 図データを検証(図: object) -> dict:
    if isinstance(図, str):
        try:
            図 = json.loads(図)
        except json.JSONDecodeError:
            raise APIエラー(400, "戦術図のデータが壊れています") from None
    if not isinstance(図, dict) or not isinstance(図.get("frames"), list) or not 1 <= len(図["frames"]) <= 20:
        raise APIエラー(400, "戦術図には1〜20コマが必要です")

    def 座標(値, 上限: int) -> float:
        if not isinstance(値, (int, float)) or isinstance(値, bool) or not 0 <= 値 <= 上限:
            raise APIエラー(400, "戦術図の座標がコートの外です")
        return round(float(値), 1)

    コマ一覧 = []
    for コマ in 図["frames"]:
        if not isinstance(コマ, dict):
            raise APIエラー(400, "戦術図のコマの形式が正しくありません")
        選手一覧 = コマ.get("players", [])
        線一覧 = コマ.get("lines", [])
        if not isinstance(選手一覧, list) or len(選手一覧) > 12 or not isinstance(線一覧, list) or len(線一覧) > 40:
            raise APIエラー(400, "戦術図の選手は12人まで、線は40本までです")
        選手 = []
        ID集合 = set()
        for p in 選手一覧:
            if not isinstance(p, dict) or p.get("team") not in ("O", "X"):
                raise APIエラー(400, "戦術図の選手の形式が正しくありません")
            選手ID = str(p.get("id", ""))[:5]
            if not 選手ID or 選手ID in ID集合:
                raise APIエラー(400, "戦術図の選手IDが重複しています")
            ID集合.add(選手ID)
            選手.append({"id": 選手ID, "team": p["team"], "label": str(p.get("label", ""))[:3], "x": 座標(p.get("x"), コート幅), "y": 座標(p.get("y"), コート奥行)})
        線 = []
        for l in 線一覧:
            if not isinstance(l, dict) or l.get("type") not in 線の種類 or not isinstance(l.get("points"), list):
                raise APIエラー(400, "戦術図の線の形式が正しくありません")
            点 = l["points"]
            if not 2 <= len(点) <= 60 or not all(isinstance(q, list) and len(q) == 2 for q in 点):
                raise APIエラー(400, "戦術図の線の点の数が正しくありません")
            線.append({"type": l["type"], "points": [[座標(q[0], コート幅), 座標(q[1], コート奥行)] for q in 点]})
        ボール = コマ.get("ball")
        if ボール is not None and ボール not in ID集合:
            ボール = None
        コマ一覧.append({"players": 選手, "ball": ボール, "lines": 線, "note": str(コマ.get("note", ""))[:300]})
    return {"frames": コマ一覧}


def _戦術入力(リクエスト_: リクエスト) -> tuple:
    本文 = リクエスト_.本文
    return (
        選択(本文, "kind", "種別", 戦術の種別, 既定="オフェンス"),
        文字列(本文, "title", "タイトル", 必須=True, 最大=60),
        文字列(本文, "description", "説明", 最大=最大文字数_長),
        json.dumps(図データを検証(本文.get("data")), ensure_ascii=False),
        真偽(本文, "is_template", False),
        真偽(本文, "published", True),
    )


def _戦術を取得(リクエスト_: リクエスト, 戦術ID: int) -> dict:
    戦術 = チーム内の行(リクエスト_, "tactics", 戦術ID, "戦術")
    if not 戦術["published"] and not リクエスト_.コーチか:
        raise APIエラー(404, "戦術が見つかりません")
    return 戦術


def _クイズを取得(リクエスト_: リクエスト, クイズID: int) -> dict:
    行 = リクエスト_.db.execute(
        """SELECT q.*, t.published FROM tactic_quizzes q JOIN tactics t ON t.id = q.tactic_id
           WHERE q.id = ? AND t.team_id = ?""",
        (クイズID, リクエスト_.チームID),
    ).fetchone()
    if 行 is None or (not 行["published"] and not リクエスト_.コーチか):
        raise APIエラー(404, "クイズが見つかりません")
    return dict(行)


@ルート("GET", "/api/tactics")
def 戦術一覧(リクエスト_: リクエスト):
    クエリ = リクエスト_.クエリ
    条件 = ["t.team_id = ?"]
    引数: list = [リクエスト_.ユーザー["id"], リクエスト_.ユーザー["id"], リクエスト_.チームID]
    if not リクエスト_.コーチか:
        条件.append("t.published = 1")
    if クエリ.get("kind") in 戦術の種別:
        条件.append("t.kind = ?")
        引数.append(クエリ["kind"])
    if クエリ.get("template") in ("0", "1"):
        条件.append("t.is_template = ?")
        引数.append(int(クエリ["template"]))
    if クエリ.get("q", "").strip():
        条件.append("(t.title LIKE ? OR t.description LIKE ?)")
        引数 += [f"%{クエリ['q'].strip()}%"] * 2
    行一覧 = 行一覧を辞書に(
        リクエスト_.db.execute(
            f"""SELECT t.*, c.understood AS my_understood,
                   (SELECT COUNT(*) FROM tactic_quizzes q WHERE q.tactic_id = t.id) AS quiz_count,
                   (SELECT COUNT(*) FROM tactic_quizzes q JOIN tactic_answers a ON a.quiz_id = q.id
                      WHERE q.tactic_id = t.id AND a.user_id = ? AND a.correct = 1) AS my_correct,
                   (SELECT COUNT(*) FROM tactic_checks x JOIN users xu ON xu.id = x.user_id AND xu.active = 1
                      WHERE x.tactic_id = t.id AND x.understood = 2) AS understood_count
                FROM tactics t LEFT JOIN tactic_checks c ON c.tactic_id = t.id AND c.user_id = ?
                WHERE {' AND '.join(条件)} ORDER BY t.is_template, t.updated_at DESC, t.id""",
            引数,
        ).fetchall()
    )
    for 行 in 行一覧:
        行["data"] = json.loads(行["data"])
    return 行一覧


@ルート("POST", "/api/tactics", 権限="コーチ")
def 戦術作成(リクエスト_: リクエスト):
    値 = _戦術入力(リクエスト_)
    時刻 = 現在時刻()
    戦術ID = リクエスト_.db.execute(
        """INSERT INTO tactics (team_id, kind, title, description, data, is_template, published, created_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (リクエスト_.チームID, *値, リクエスト_.ユーザー["id"], 時刻, 時刻),
    ).lastrowid
    return {"id": 戦術ID}


@ルート("GET", "/api/tactics/{戦術ID}")
def 戦術詳細(リクエスト_: リクエスト, 戦術ID: int):
    戦術 = _戦術を取得(リクエスト_, 戦術ID)
    db = リクエスト_.db
    自分ID = リクエスト_.ユーザー["id"]
    戦術["data"] = json.loads(戦術["data"])
    作成者 = db.execute("SELECT name FROM users WHERE id = ?", (戦術["created_by"],)).fetchone()
    戦術["created_by_name"] = 作成者["name"] if 作成者 else ""
    クイズ一覧 = 行一覧を辞書に(db.execute("SELECT * FROM tactic_quizzes WHERE tactic_id = ? ORDER BY id", (戦術ID,)).fetchall())
    自分の回答 = {
        行["quiz_id"]: dict(行)
        for 行 in db.execute(
            """SELECT a.* FROM tactic_answers a JOIN tactic_quizzes q ON q.id = a.quiz_id
               WHERE q.tactic_id = ? AND a.user_id = ?""",
            (戦術ID, 自分ID),
        ).fetchall()
    }
    for クイズ in クイズ一覧:
        クイズ["choices"] = json.loads(クイズ["choices"])
        回答 = 自分の回答.get(クイズ["id"])
        クイズ["my_choice"] = 回答["choice"] if 回答 else None
        クイズ["my_correct"] = bool(回答["correct"]) if 回答 else None
        if not リクエスト_.コーチか and 回答 is None:
            # 答える前の選手には正解を見せない
            クイズ["answer_index"] = None
            クイズ["explanation"] = ""
    戦術["quizzes"] = クイズ一覧
    自分の確認 = db.execute("SELECT understood, comment, updated_at FROM tactic_checks WHERE tactic_id = ? AND user_id = ?", (戦術ID, 自分ID)).fetchone()
    戦術["my_check"] = dict(自分の確認) if 自分の確認 else None
    確認一覧 = 行一覧を辞書に(
        db.execute(
            """SELECT u.id, u.name, u.number, c.understood, c.comment, c.updated_at,
                   (SELECT COUNT(*) FROM tactic_answers a JOIN tactic_quizzes q ON q.id = a.quiz_id
                      WHERE q.tactic_id = ? AND a.user_id = u.id) AS answered,
                   (SELECT COUNT(*) FROM tactic_answers a JOIN tactic_quizzes q ON q.id = a.quiz_id
                      WHERE q.tactic_id = ? AND a.user_id = u.id AND a.correct = 1) AS correct
               FROM users u LEFT JOIN tactic_checks c ON c.tactic_id = ? AND c.user_id = u.id
               WHERE u.team_id = ? AND u.active = 1 AND u.role = 'player'
               ORDER BY CASE WHEN u.number GLOB '[0-9]*' THEN CAST(u.number AS INTEGER) ELSE 9999 END, u.name""",
            (戦術ID, 戦術ID, 戦術ID, リクエスト_.チームID),
        ).fetchall()
    )
    # コメントはチーム内で共有（疑問点をみんなで解消する）。誰がどれだけ正解したかはコーチのみ。
    戦術["comments"] = [
        {"name": 行["name"], "understood": 行["understood"], "comment": 行["comment"], "updated_at": 行["updated_at"]}
        for 行 in 確認一覧
        if 行["comment"]
    ]
    if リクエスト_.コーチか:
        戦術["checks"] = 確認一覧
    return 戦術


@ルート("PUT", "/api/tactics/{戦術ID}", 権限="コーチ")
def 戦術編集(リクエスト_: リクエスト, 戦術ID: int):
    チーム内の行(リクエスト_, "tactics", 戦術ID, "戦術")
    値 = _戦術入力(リクエスト_)
    リクエスト_.db.execute(
        """UPDATE tactics SET kind = ?, title = ?, description = ?, data = ?, is_template = ?, published = ?, updated_at = ?
           WHERE id = ?""",
        (*値, 現在時刻(), 戦術ID),
    )
    return {"id": 戦術ID}


@ルート("DELETE", "/api/tactics/{戦術ID}", 権限="コーチ")
def 戦術削除(リクエスト_: リクエスト, 戦術ID: int):
    チーム内の行(リクエスト_, "tactics", 戦術ID, "戦術")
    リクエスト_.db.execute("DELETE FROM tactics WHERE id = ?", (戦術ID,))
    return {"ok": True}


@ルート("POST", "/api/tactics/{戦術ID}/copy", 権限="コーチ")
def 戦術複製(リクエスト_: リクエスト, 戦術ID: int):
    """テンプレート（または既存の戦術）を元に新しい戦術を作る。クイズもコピーする。"""
    元 = チーム内の行(リクエスト_, "tactics", 戦術ID, "戦術")
    時刻 = 現在時刻()
    タイトル = 文字列(リクエスト_.本文, "title", "タイトル", 最大=60) or f"{元['title']}（コピー）"
    新ID = リクエスト_.db.execute(
        """INSERT INTO tactics (team_id, kind, title, description, data, is_template, published, created_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, ?)""",
        (リクエスト_.チームID, 元["kind"], タイトル, 元["description"], 元["data"], リクエスト_.ユーザー["id"], 時刻, 時刻),
    ).lastrowid
    リクエスト_.db.execute(
        """INSERT INTO tactic_quizzes (tactic_id, question, choices, answer_index, explanation)
           SELECT ?, question, choices, answer_index, explanation FROM tactic_quizzes WHERE tactic_id = ? ORDER BY id""",
        (新ID, 戦術ID),
    )
    return {"id": 新ID}


def _クイズ入力(本文: dict) -> tuple:
    選択肢 = 本文.get("choices")
    if not isinstance(選択肢, list) or not 2 <= len(選択肢) <= 5:
        raise APIエラー(400, "選択肢は2〜5個にしてください")
    選択肢 = [文字列({"v": 値}, "v", f"選択肢{i + 1}", 必須=True, 最大=100) for i, 値 in enumerate(選択肢)]
    return (
        文字列(本文, "question", "問題文", 必須=True, 最大=300),
        json.dumps(選択肢, ensure_ascii=False),
        整数(本文, "answer_index", "正解", 0, len(選択肢) - 1, 既定=None),
        文字列(本文, "explanation", "解説", 最大=1000),
    )


@ルート("POST", "/api/tactics/{戦術ID}/quizzes", 権限="コーチ")
def クイズ作成(リクエスト_: リクエスト, 戦術ID: int):
    チーム内の行(リクエスト_, "tactics", 戦術ID, "戦術")
    値 = _クイズ入力(リクエスト_.本文)
    クイズID = リクエスト_.db.execute(
        "INSERT INTO tactic_quizzes (tactic_id, question, choices, answer_index, explanation) VALUES (?, ?, ?, ?, ?)",
        (戦術ID, *値),
    ).lastrowid
    return {"id": クイズID}


@ルート("PUT", "/api/quizzes/{クイズID}", 権限="コーチ")
def クイズ編集(リクエスト_: リクエスト, クイズID: int):
    _クイズを取得(リクエスト_, クイズID)
    値 = _クイズ入力(リクエスト_.本文)
    リクエスト_.db.execute(
        "UPDATE tactic_quizzes SET question = ?, choices = ?, answer_index = ?, explanation = ? WHERE id = ?", (*値, クイズID)
    )
    # 問題が変わったので過去の回答は採点し直す
    リクエスト_.db.execute("UPDATE tactic_answers SET correct = (choice = ?) WHERE quiz_id = ?", (値[2], クイズID))
    return {"id": クイズID}


@ルート("DELETE", "/api/quizzes/{クイズID}", 権限="コーチ")
def クイズ削除(リクエスト_: リクエスト, クイズID: int):
    _クイズを取得(リクエスト_, クイズID)
    リクエスト_.db.execute("DELETE FROM tactic_quizzes WHERE id = ?", (クイズID,))
    return {"ok": True}


@ルート("POST", "/api/quizzes/{クイズID}/answer")
def クイズ回答(リクエスト_: リクエスト, クイズID: int):
    クイズ = _クイズを取得(リクエスト_, クイズID)
    選択肢数 = len(json.loads(クイズ["choices"]))
    回答 = 整数(リクエスト_.本文, "choice", "回答", 0, 選択肢数 - 1, 既定=None)
    正解 = int(回答 == クイズ["answer_index"])
    リクエスト_.db.execute(
        """INSERT INTO tactic_answers (quiz_id, user_id, choice, correct, answered_at) VALUES (?, ?, ?, ?, ?)
           ON CONFLICT (quiz_id, user_id) DO UPDATE SET choice = excluded.choice, correct = excluded.correct, answered_at = excluded.answered_at""",
        (クイズID, リクエスト_.ユーザー["id"], 回答, 正解, 現在時刻()),
    )
    return {"correct": bool(正解), "answer_index": クイズ["answer_index"], "explanation": クイズ["explanation"]}


@ルート("PUT", "/api/tactics/{戦術ID}/check")
def 理解度登録(リクエスト_: リクエスト, 戦術ID: int):
    _戦術を取得(リクエスト_, 戦術ID)
    度合い = 整数(リクエスト_.本文, "understood", "理解度", 0, 2, 既定=None)
    コメント = 文字列(リクエスト_.本文, "comment", "コメント", 最大=500)
    リクエスト_.db.execute(
        """INSERT INTO tactic_checks (tactic_id, user_id, understood, comment, updated_at) VALUES (?, ?, ?, ?, ?)
           ON CONFLICT (tactic_id, user_id) DO UPDATE SET understood = excluded.understood, comment = excluded.comment, updated_at = excluded.updated_at""",
        (戦術ID, リクエスト_.ユーザー["id"], 度合い, コメント, 現在時刻()),
    )
    return {"ok": True}
