"""パスワードのハッシュ化・ログインセッション・チームコード発行。"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta

from データベース import 日本時間

反復回数 = 200_000
セッション有効日数 = 30
チームコード文字 = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 見間違えやすい I O 0 1 を除外


def パスワードをハッシュ化(パスワード: str) -> str:
    塩 = secrets.token_hex(16)
    値 = hashlib.pbkdf2_hmac("sha256", パスワード.encode(), bytes.fromhex(塩), 反復回数).hex()
    return f"pbkdf2_sha256${反復回数}${塩}${値}"


def パスワードを照合(パスワード: str, 保存値: str) -> bool:
    try:
        方式, 回数, 塩, 値 = 保存値.split("$")
    except ValueError:
        return False
    if 方式 != "pbkdf2_sha256":
        return False
    計算値 = hashlib.pbkdf2_hmac("sha256", パスワード.encode(), bytes.fromhex(塩), int(回数)).hex()
    return hmac.compare_digest(計算値, 値)


def _トークンのハッシュ(トークン: str) -> str:
    return hashlib.sha256(トークン.encode()).hexdigest()


def セッションを作成(接続先: sqlite3.Connection, ユーザーID: int) -> str:
    トークン = secrets.token_urlsafe(32)
    期限 = (datetime.now(日本時間) + timedelta(days=セッション有効日数)).isoformat(timespec="seconds")
    接続先.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (_トークンのハッシュ(トークン), ユーザーID, 期限),
    )
    return トークン


def セッションからユーザー(接続先: sqlite3.Connection, トークン: str) -> dict | None:
    if not トークン:
        return None
    行 = 接続先.execute(
        """SELECT u.*, s.expires_at FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token_hash = ? AND u.active = 1""",
        (_トークンのハッシュ(トークン),),
    ).fetchone()
    if 行 is None:
        return None
    if datetime.fromisoformat(行["expires_at"]) < datetime.now(日本時間):
        セッションを削除(接続先, トークン)
        return None
    return dict(行)


def セッションを削除(接続先: sqlite3.Connection, トークン: str) -> None:
    接続先.execute("DELETE FROM sessions WHERE token_hash = ?", (_トークンのハッシュ(トークン),))


def ユーザーのセッションを全削除(接続先: sqlite3.Connection, ユーザーID: int) -> None:
    接続先.execute("DELETE FROM sessions WHERE user_id = ?", (ユーザーID,))


def チームコードを発行(接続先: sqlite3.Connection) -> str:
    while True:
        コード = "".join(secrets.choice(チームコード文字) for _ in range(6))
        if 接続先.execute("SELECT 1 FROM teams WHERE code = ?", (コード,)).fetchone() is None:
            return コード


def 仮パスワードを発行() -> str:
    return "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(8))
