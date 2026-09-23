"""チーム運営の API：チーム作成・ログイン・メンバー管理・連絡／掲示板・ホーム。"""

from __future__ import annotations

import re
import threading
import time
from datetime import date, timedelta

import 初期データ
from データベース import 今日, 現在時刻, 行一覧を辞書に
from ルーティング import (
    APIエラー,
    リクエスト,
    ルート,
    チーム内の行,
    公開ユーザー情報,
    文字列,
    選択,
    最大文字数_長,
)
from 認証 import (
    セッションを作成,
    セッションを削除,
    チームコードを発行,
    パスワードをハッシュ化,
    パスワードを照合,
    ユーザーのセッションを全削除,
    仮パスワードを発行,
)

写真の最大サイズ = 400_000  # data URL の文字数。画面側で縮小してから送る
ログイン失敗の上限 = 5
ログイン停止秒数 = 300
_失敗記録: dict[str, list[float]] = {}
_失敗記録ロック = threading.Lock()


def _パスワードを確認(パスワード: str) -> str:
    if len(パスワード) < 8:
        raise APIエラー(400, "パスワードは8文字以上にしてください")
    if len(パスワード) > 128:
        raise APIエラー(400, "パスワードが長すぎます")
    return パスワード


def _ログインIDを確認(値: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", 値):
        raise APIエラー(400, "ログインIDは半角英数字（3〜30文字、記号は _ . - のみ）で入力してください")
    return 値.lower()


def _写真を確認(値: str) -> str:
    if not 値:
        return ""
    if not re.match(r"^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$", 値):
        raise APIエラー(400, "顔写真の形式が正しくありません")
    if len(値) > 写真の最大サイズ:
        raise APIエラー(400, "顔写真のサイズが大きすぎます")
    return 値


def _チーム情報(リクエスト_: リクエスト) -> dict:
    行 = リクエスト_.db.execute("SELECT id, name, code FROM teams WHERE id = ?", (リクエスト_.チームID,)).fetchone()
    return dict(行)


# ---------- チーム作成・ログイン ----------


@ルート("POST", "/api/teams", 権限="公開")
def チームを作成(リクエスト_: リクエスト):
    本文 = リクエスト_.本文
    チーム名 = 文字列(本文, "team_name", "チーム名", 必須=True, 最大=50)
    氏名 = 文字列(本文, "name", "氏名", 必須=True, 最大=30)
    ログインID = _ログインIDを確認(文字列(本文, "login_id", "ログインID", 必須=True))
    パスワード = _パスワードを確認(str(本文.get("password", "")))
    db = リクエスト_.db
    時刻 = 現在時刻()
    コード = チームコードを発行(db)
    チームID = db.execute("INSERT INTO teams (name, code, created_at) VALUES (?, ?, ?)", (チーム名, コード, 時刻)).lastrowid
    ユーザーID = db.execute(
        """INSERT INTO users (team_id, login_id, name, role, password_hash, created_at)
           VALUES (?, ?, ?, 'coach', ?, ?)""",
        (チームID, ログインID, 氏名, パスワードをハッシュ化(パスワード), 時刻),
    ).lastrowid
    初期データ.チームの初期データを投入(db, チームID, ユーザーID)
    トークン = セッションを作成(db, ユーザーID)
    ユーザー = dict(db.execute("SELECT * FROM users WHERE id = ?", (ユーザーID,)).fetchone())
    return {"token": トークン, "user": 公開ユーザー情報(ユーザー), "team": {"id": チームID, "name": チーム名, "code": コード}}


@ルート("POST", "/api/login", 権限="公開")
def ログイン(リクエスト_: リクエスト):
    本文 = リクエスト_.本文
    コード = 文字列(本文, "team_code", "チームコード", 必須=True, 最大=10).upper()
    ログインID = 文字列(本文, "login_id", "ログインID", 必須=True, 最大=30).lower()
    パスワード = str(本文.get("password", ""))
    キー = f"{コード}:{ログインID}"
    現在 = time.time()
    with _失敗記録ロック:
        記録 = [t for t in _失敗記録.get(キー, []) if 現在 - t < ログイン停止秒数]
        _失敗記録[キー] = 記録
        if len(記録) >= ログイン失敗の上限:
            raise APIエラー(429, "ログインの失敗が続いたため、5分ほど待ってから再度お試しください")
    行 = リクエスト_.db.execute(
        """SELECT u.* FROM users u JOIN teams t ON t.id = u.team_id
           WHERE t.code = ? AND u.login_id = ? AND u.active = 1""",
        (コード, ログインID),
    ).fetchone()
    if 行 is None or not パスワードを照合(パスワード, 行["password_hash"]):
        with _失敗記録ロック:
            _失敗記録.setdefault(キー, []).append(現在)
        raise APIエラー(401, "チームコード・ログインID・パスワードのいずれかが違います")
    with _失敗記録ロック:
        _失敗記録.pop(キー, None)
    トークン = セッションを作成(リクエスト_.db, 行["id"])
    リクエスト_.ユーザー = dict(行)
    return {"token": トークン, "user": 公開ユーザー情報(dict(行)), "team": _チーム情報(リクエスト_)}


@ルート("POST", "/api/logout")
def ログアウト(リクエスト_: リクエスト):
    セッションを削除(リクエスト_.db, リクエスト_.トークン)
    return {"ok": True}


@ルート("GET", "/api/me")
def 自分の情報(リクエスト_: リクエスト):
    return {"user": 公開ユーザー情報(リクエスト_.ユーザー), "team": _チーム情報(リクエスト_)}


@ルート("PUT", "/api/me/password")
def パスワード変更(リクエスト_: リクエスト):
    現在 = str(リクエスト_.本文.get("current", ""))
    新 = _パスワードを確認(str(リクエスト_.本文.get("new", "")))
    if not パスワードを照合(現在, リクエスト_.ユーザー["password_hash"]):
        raise APIエラー(400, "現在のパスワードが違います")
    リクエスト_.db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (パスワードをハッシュ化(新), リクエスト_.ユーザー["id"]))
    ユーザーのセッションを全削除(リクエスト_.db, リクエスト_.ユーザー["id"])
    トークン = セッションを作成(リクエスト_.db, リクエスト_.ユーザー["id"])
    return {"token": トークン}


@ルート("PUT", "/api/team", 権限="コーチ")
def チーム名変更(リクエスト_: リクエスト):
    名前 = 文字列(リクエスト_.本文, "name", "チーム名", 必須=True, 最大=50)
    リクエスト_.db.execute("UPDATE teams SET name = ? WHERE id = ?", (名前, リクエスト_.チームID))
    return _チーム情報(リクエスト_)


# ---------- メンバー ----------


@ルート("GET", "/api/members")
def メンバー一覧(リクエスト_: リクエスト):
    行一覧 = リクエスト_.db.execute(
        """SELECT * FROM users WHERE team_id = ? AND active = 1
           ORDER BY role = 'player', CASE WHEN number GLOB '[0-9]*' THEN CAST(number AS INTEGER) ELSE 9999 END, name""",
        (リクエスト_.チームID,),
    ).fetchall()
    return [公開ユーザー情報(dict(行)) for 行 in 行一覧]


def _メンバー入力(リクエスト_: リクエスト, 既存: dict | None = None) -> dict:
    本文 = リクエスト_.本文
    既 = 既存 or {}
    return {
        "name": 文字列(本文, "name", "氏名", 必須=True, 最大=30, 既定=既.get("name", "")),
        "role": 選択(本文, "role", "役割", ("coach", "player"), 既定=既.get("role", "player")),
        "grade": 文字列(本文, "grade", "学年", 最大=10, 既定=既.get("grade", "")),
        "position": 文字列(本文, "position", "ポジション", 最大=20, 既定=既.get("position", "")),
        "number": 文字列(本文, "number", "背番号", 最大=3, 既定=既.get("number", "")),
        "photo": _写真を確認(str(本文.get("photo", 既.get("photo", "")) or "")),
    }


@ルート("POST", "/api/members", 権限="コーチ")
def メンバー追加(リクエスト_: リクエスト):
    値 = _メンバー入力(リクエスト_)
    ログインID = _ログインIDを確認(文字列(リクエスト_.本文, "login_id", "ログインID", 必須=True))
    パスワード = str(リクエスト_.本文.get("password") or "") or 仮パスワードを発行()
    _パスワードを確認(パスワード)
    重複 = リクエスト_.db.execute(
        "SELECT id, active FROM users WHERE team_id = ? AND login_id = ?", (リクエスト_.チームID, ログインID)
    ).fetchone()
    if 重複 is not None:
        raise APIエラー(400, "このログインIDはすでに使われています" + ("（退部済みメンバー）" if not 重複["active"] else ""))
    ユーザーID = リクエスト_.db.execute(
        """INSERT INTO users (team_id, login_id, name, role, grade, position, number, photo, password_hash, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (リクエスト_.チームID, ログインID, 値["name"], 値["role"], 値["grade"], 値["position"], 値["number"], 値["photo"], パスワードをハッシュ化(パスワード), 現在時刻()),
    ).lastrowid
    行 = dict(リクエスト_.db.execute("SELECT * FROM users WHERE id = ?", (ユーザーID,)).fetchone())
    return {"member": 公開ユーザー情報(行), "initial_password": パスワード}


def _コーチが残るか確認(リクエスト_: リクエスト, 対象ID: int) -> None:
    残り = リクエスト_.db.execute(
        "SELECT COUNT(*) FROM users WHERE team_id = ? AND role = 'coach' AND active = 1 AND id != ?",
        (リクエスト_.チームID, 対象ID),
    ).fetchone()[0]
    if 残り == 0:
        raise APIエラー(400, "コーチが1人もいなくなるため、この変更はできません")


@ルート("GET", "/api/members/{メンバーID}")
def メンバー詳細(リクエスト_: リクエスト, メンバーID: int):
    行 = チーム内の行(リクエスト_, "users", メンバーID, "メンバー")
    if not 行["active"]:
        raise APIエラー(404, "メンバーが見つかりません")
    return 公開ユーザー情報(行)


@ルート("PUT", "/api/members/{メンバーID}", 権限="コーチ")
def メンバー編集(リクエスト_: リクエスト, メンバーID: int):
    既存 = チーム内の行(リクエスト_, "users", メンバーID, "メンバー")
    値 = _メンバー入力(リクエスト_, 既存)
    if 既存["role"] == "coach" and 値["role"] != "coach":
        _コーチが残るか確認(リクエスト_, メンバーID)
    リクエスト_.db.execute(
        "UPDATE users SET name = ?, role = ?, grade = ?, position = ?, number = ?, photo = ? WHERE id = ?",
        (値["name"], 値["role"], 値["grade"], 値["position"], 値["number"], 値["photo"], メンバーID),
    )
    return 公開ユーザー情報(チーム内の行(リクエスト_, "users", メンバーID))


@ルート("DELETE", "/api/members/{メンバーID}", 権限="コーチ")
def メンバー退部(リクエスト_: リクエスト, メンバーID: int):
    既存 = チーム内の行(リクエスト_, "users", メンバーID, "メンバー")
    if メンバーID == リクエスト_.ユーザー["id"]:
        raise APIエラー(400, "自分自身は退部にできません")
    if 既存["role"] == "coach":
        _コーチが残るか確認(リクエスト_, メンバーID)
    # 記録（スタッツ・出欠など）を残すため削除ではなく無効化する
    リクエスト_.db.execute("UPDATE users SET active = 0 WHERE id = ?", (メンバーID,))
    ユーザーのセッションを全削除(リクエスト_.db, メンバーID)
    return {"ok": True}


@ルート("POST", "/api/members/{メンバーID}/reset-password", 権限="コーチ")
def パスワード再発行(リクエスト_: リクエスト, メンバーID: int):
    チーム内の行(リクエスト_, "users", メンバーID, "メンバー")
    パスワード = 仮パスワードを発行()
    リクエスト_.db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (パスワードをハッシュ化(パスワード), メンバーID))
    ユーザーのセッションを全削除(リクエスト_.db, メンバーID)
    return {"initial_password": パスワード}


# ---------- 連絡・掲示板 ----------


def _有効メンバー数(リクエスト_: リクエスト) -> int:
    return リクエスト_.db.execute("SELECT COUNT(*) FROM users WHERE team_id = ? AND active = 1", (リクエスト_.チームID,)).fetchone()[0]


@ルート("GET", "/api/posts")
def 投稿一覧(リクエスト_: リクエスト):
    種類 = リクエスト_.クエリ.get("kind", "")
    条件 = "p.team_id = ?"
    引数: list = [リクエスト_.ユーザー["id"], リクエスト_.チームID]
    if 種類 in ("お知らせ", "掲示板"):
        条件 += " AND p.kind = ?"
        引数.append(種類)
    行一覧 = リクエスト_.db.execute(
        f"""SELECT p.*, u.name AS author_name,
               (SELECT COUNT(*) FROM post_reads r JOIN users ru ON ru.id = r.user_id AND ru.active = 1 WHERE r.post_id = p.id) AS read_count,
               (SELECT COUNT(*) FROM post_comments c WHERE c.post_id = p.id) AS comment_count,
               EXISTS (SELECT 1 FROM post_reads r WHERE r.post_id = p.id AND r.user_id = ?) AS is_read
            FROM posts p LEFT JOIN users u ON u.id = p.author_id
            WHERE {条件} ORDER BY p.created_at DESC, p.id DESC LIMIT 200""",
        引数,
    ).fetchall()
    メンバー数 = _有効メンバー数(リクエスト_)
    return [{**dict(行), "member_count": メンバー数} for 行 in 行一覧]


@ルート("POST", "/api/posts")
def 投稿作成(リクエスト_: リクエスト):
    本文 = リクエスト_.本文
    種類 = 選択(本文, "kind", "種類", ("お知らせ", "掲示板"), 既定="掲示板")
    if 種類 == "お知らせ" and not リクエスト_.コーチか:
        raise APIエラー(403, "お知らせの配信はコーチのみ行えます")
    タイトル = 文字列(本文, "title", "タイトル", 必須=True, 最大=100)
    内容 = 文字列(本文, "body", "本文", 最大=最大文字数_長)
    時刻 = 現在時刻()
    投稿ID = リクエスト_.db.execute(
        "INSERT INTO posts (team_id, kind, title, body, author_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (リクエスト_.チームID, 種類, タイトル, 内容, リクエスト_.ユーザー["id"], 時刻),
    ).lastrowid
    リクエスト_.db.execute("INSERT INTO post_reads (post_id, user_id, read_at) VALUES (?, ?, ?)", (投稿ID, リクエスト_.ユーザー["id"], 時刻))
    return {"id": 投稿ID}


@ルート("GET", "/api/posts/{投稿ID}")
def 投稿詳細(リクエスト_: リクエスト, 投稿ID: int):
    投稿 = チーム内の行(リクエスト_, "posts", 投稿ID, "投稿")
    db = リクエスト_.db
    db.execute(
        "INSERT OR IGNORE INTO post_reads (post_id, user_id, read_at) VALUES (?, ?, ?)",
        (投稿ID, リクエスト_.ユーザー["id"], 現在時刻()),
    )
    作成者 = db.execute("SELECT name FROM users WHERE id = ?", (投稿["author_id"],)).fetchone()
    コメント = 行一覧を辞書に(
        db.execute(
            """SELECT c.id, c.body, c.created_at, c.user_id, u.name AS user_name FROM post_comments c
               LEFT JOIN users u ON u.id = c.user_id WHERE c.post_id = ? ORDER BY c.id""",
            (投稿ID,),
        ).fetchall()
    )
    既読 = 行一覧を辞書に(
        db.execute(
            """SELECT u.id, u.name, u.role, r.read_at FROM users u
               LEFT JOIN post_reads r ON r.user_id = u.id AND r.post_id = ?
               WHERE u.team_id = ? AND u.active = 1 ORDER BY r.read_at IS NULL DESC, u.role, u.name""",
            (投稿ID, リクエスト_.チームID),
        ).fetchall()
    )
    既読数 = sum(1 for 行 in 既読 if 行["read_at"])
    結果 = {**投稿, "author_name": 作成者["name"] if 作成者 else "", "comments": コメント, "read_count": 既読数, "member_count": len(既読)}
    if リクエスト_.コーチか:
        結果["reads"] = 既読  # 誰が読んだ／未読かはコーチだけに見せる
    return 結果


@ルート("DELETE", "/api/posts/{投稿ID}")
def 投稿削除(リクエスト_: リクエスト, 投稿ID: int):
    投稿 = チーム内の行(リクエスト_, "posts", 投稿ID, "投稿")
    if not リクエスト_.コーチか and 投稿["author_id"] != リクエスト_.ユーザー["id"]:
        raise APIエラー(403, "自分の投稿のみ削除できます")
    リクエスト_.db.execute("DELETE FROM posts WHERE id = ?", (投稿ID,))
    return {"ok": True}


@ルート("POST", "/api/posts/{投稿ID}/comments")
def コメント投稿(リクエスト_: リクエスト, 投稿ID: int):
    チーム内の行(リクエスト_, "posts", 投稿ID, "投稿")
    内容 = 文字列(リクエスト_.本文, "body", "コメント", 必須=True, 最大=1000)
    コメントID = リクエスト_.db.execute(
        "INSERT INTO post_comments (post_id, user_id, body, created_at) VALUES (?, ?, ?, ?)",
        (投稿ID, リクエスト_.ユーザー["id"], 内容, 現在時刻()),
    ).lastrowid
    return {"id": コメントID}


@ルート("DELETE", "/api/comments/{コメントID}")
def コメント削除(リクエスト_: リクエスト, コメントID: int):
    行 = リクエスト_.db.execute(
        """SELECT c.* FROM post_comments c JOIN posts p ON p.id = c.post_id
           WHERE c.id = ? AND p.team_id = ?""",
        (コメントID, リクエスト_.チームID),
    ).fetchone()
    if 行 is None:
        raise APIエラー(404, "コメントが見つかりません")
    if not リクエスト_.コーチか and 行["user_id"] != リクエスト_.ユーザー["id"]:
        raise APIエラー(403, "自分のコメントのみ削除できます")
    リクエスト_.db.execute("DELETE FROM post_comments WHERE id = ?", (コメントID,))
    return {"ok": True}


# ---------- ホーム ----------


@ルート("GET", "/api/home")
def ホーム(リクエスト_: リクエスト):
    from API_スキル import おすすめステップ  # 循環 import を避ける

    db = リクエスト_.db
    自分ID = リクエスト_.ユーザー["id"]
    チームID = リクエスト_.チームID
    本日 = 今日()
    二週間後 = (date.fromisoformat(本日) + timedelta(days=14)).isoformat()
    未読 = 行一覧を辞書に(
        db.execute(
            """SELECT p.id, p.title, p.kind, p.created_at FROM posts p
               WHERE p.team_id = ? AND p.kind = 'お知らせ'
                 AND NOT EXISTS (SELECT 1 FROM post_reads r WHERE r.post_id = p.id AND r.user_id = ?)
               ORDER BY p.created_at DESC LIMIT 20""",
            (チームID, 自分ID),
        ).fetchall()
    )
    予定 = 行一覧を辞書に(
        db.execute(
            f"""SELECT e.id, e.kind, e.title, e.date, e.start_time, e.end_time, e.place, e.published,
                   a.status AS my_status,
                   (SELECT COUNT(*) FROM attendance x JOIN users xu ON xu.id = x.user_id AND xu.active = 1
                      WHERE x.event_id = e.id AND x.status IN ('出席', '遅刻', '早退')) AS attend_count,
                   (SELECT COUNT(*) FROM attendance x JOIN users xu ON xu.id = x.user_id AND xu.active = 1
                      WHERE x.event_id = e.id) AS answered_count
                FROM events e LEFT JOIN attendance a ON a.event_id = e.id AND a.user_id = ?
                WHERE e.team_id = ? AND e.date BETWEEN ? AND ? {'' if リクエスト_.コーチか else 'AND e.published = 1'}
                ORDER BY e.date, e.start_time LIMIT 10""",
            (自分ID, チームID, 本日, 二週間後),
        ).fetchall()
    )
    目標 = 行一覧を辞書に(
        db.execute(
            """SELECT id, scope, content, deadline, progress FROM goals
               WHERE team_id = ? AND status = '進行中' AND (scope = 'チーム' OR user_id = ?)
               ORDER BY deadline = '', deadline LIMIT 5""",
            (チームID, 自分ID),
        ).fetchall()
    )
    結果 = {
        "team": _チーム情報(リクエスト_),
        "user": 公開ユーザー情報(リクエスト_.ユーザー),
        "unread_notices": 未読,
        "upcoming": 予定,
        "goals": 目標,
        "member_count": _有効メンバー数(リクエスト_),
    }
    if リクエスト_.コーチか:
        結果["step_reports"] = 行一覧を辞書に(
            db.execute(
                """SELECT r.id, r.date, r.self_rating, r.cleared, r.comment, u.id AS player_id, u.name AS player_name, d.title
                   FROM step_reports r JOIN users u ON u.id = r.player_id JOIN drill_steps d ON d.id = r.drill_id
                   WHERE r.team_id = ? AND u.active = 1 ORDER BY r.created_at DESC LIMIT 5""",
                (チームID,),
            ).fetchall()
        )
    else:
        結果["steps"] = おすすめステップ(リクエスト_, 自分ID)[:3]
        結果["unconfirmed_feedback"] = db.execute(
            "SELECT COUNT(*) FROM feedback WHERE player_id = ? AND confirmed_at = ''", (自分ID,)
        ).fetchone()[0]
    return 結果
