"""API のルート登録・入力チェック・権限チェックの共通部品。

各 API_*.py は @ルート で処理を登録する。処理は (リクエスト, **URLパラメータ) を受け取り、JSON にできる値を返す。
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

最大文字数_短 = 100
最大文字数_長 = 5000


class APIエラー(Exception):
    def __init__(self, ステータス: int, メッセージ: str):
        super().__init__(メッセージ)
        self.ステータス = ステータス
        self.メッセージ = メッセージ


@dataclass
class リクエスト:
    メソッド: str
    パス: str
    クエリ: dict[str, str]
    本文: dict[str, Any]
    db: sqlite3.Connection
    ユーザー: dict | None = None
    トークン: str = ""
    追加ヘッダー: dict[str, str] = field(default_factory=dict)

    @property
    def チームID(self) -> int:
        return self.ユーザー["team_id"]

    @property
    def コーチか(self) -> bool:
        return self.ユーザー is not None and self.ユーザー["role"] == "coach"


@dataclass
class ルート情報:
    メソッド: str
    パターン: re.Pattern
    処理: Callable
    権限: str  # "公開" / "ログイン" / "コーチ"


ルート一覧: list[ルート情報] = []


def ルート(メソッド: str, パス: str, 権限: str = "ログイン"):
    """パスの {name} は数値IDとして受け取る。"""
    正規表現 = "^" + re.sub(r"\{(\w+)\}", r"(?P<\1>\\d+)", パス) + "$"

    def 登録(処理: Callable) -> Callable:
        ルート一覧.append(ルート情報(メソッド, re.compile(正規表現), 処理, 権限))
        return 処理

    return 登録


def 振り分け(リクエスト_: リクエスト) -> Any:
    パスは一致 = False
    for 情報 in ルート一覧:
        一致 = 情報.パターン.match(リクエスト_.パス)
        if not 一致:
            continue
        パスは一致 = True
        if 情報.メソッド != リクエスト_.メソッド:
            continue
        if 情報.権限 != "公開" and リクエスト_.ユーザー is None:
            raise APIエラー(401, "ログインしてください")
        if 情報.権限 == "コーチ" and not リクエスト_.コーチか:
            raise APIエラー(403, "この操作はコーチのみ行えます")
        引数 = {名前: int(値) for 名前, 値 in 一致.groupdict().items()}
        return 情報.処理(リクエスト_, **引数)
    if パスは一致:
        raise APIエラー(405, "この操作には対応していません")
    raise APIエラー(404, "見つかりません")


# ---------- 入力チェック ----------


def 文字列(本文: dict, キー: str, 名前: str, 必須: bool = False, 最大: int = 最大文字数_短, 既定: str = "") -> str:
    値 = 本文.get(キー, 既定)
    if 値 is None:
        値 = ""
    if not isinstance(値, (str, int, float)):
        raise APIエラー(400, f"{名前}の形式が正しくありません")
    値 = str(値).strip()
    if 必須 and not 値:
        raise APIエラー(400, f"{名前}を入力してください")
    if len(値) > 最大:
        raise APIエラー(400, f"{名前}は{最大}文字以内で入力してください")
    return 値


def 整数(本文: dict, キー: str, 名前: str, 最小: int = 0, 最大: int = 1_000_000, 既定: int | None = 0) -> int:
    値 = 本文.get(キー, 既定)
    if 値 in (None, ""):
        if 既定 is None:
            raise APIエラー(400, f"{名前}を入力してください")
        値 = 既定
    try:
        数 = int(値)
    except (TypeError, ValueError):
        raise APIエラー(400, f"{名前}は数字で入力してください") from None
    if isinstance(値, float) and not float(値).is_integer():
        raise APIエラー(400, f"{名前}は整数で入力してください")
    if not 最小 <= 数 <= 最大:
        raise APIエラー(400, f"{名前}は{最小}〜{最大}の範囲で入力してください")
    return 数


def 日付(本文: dict, キー: str, 名前: str, 必須: bool = True) -> str:
    値 = 文字列(本文, キー, 名前, 必須=必須, 最大=10)
    if not 値:
        return ""
    try:
        return date.fromisoformat(値).isoformat()
    except ValueError:
        raise APIエラー(400, f"{名前}は YYYY-MM-DD 形式で入力してください") from None


def 時刻(本文: dict, キー: str, 名前: str) -> str:
    値 = 文字列(本文, キー, 名前, 最大=5)
    if 値 and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", 値):
        raise APIエラー(400, f"{名前}は HH:MM 形式で入力してください")
    return 値


def 選択(本文: dict, キー: str, 名前: str, 候補: tuple[str, ...], 既定: str | None = None) -> str:
    値 = 本文.get(キー, 既定)
    if 値 not in 候補:
        raise APIエラー(400, f"{名前}は {' / '.join(候補)} から選んでください")
    return 値


def 真偽(本文: dict, キー: str, 既定: bool = False) -> int:
    値 = 本文.get(キー, 既定)
    return 1 if 値 in (True, 1, "1", "true", "on") else 0


def URL(本文: dict, キー: str, 名前: str) -> str:
    値 = 文字列(本文, キー, 名前, 最大=1000)
    if 値 and not re.match(r"^https?://", 値):
        raise APIエラー(400, f"{名前}は http:// または https:// で始まるURLを入力してください")
    return 値


# ---------- チーム内データの取得・権限 ----------


def チーム内の行(リクエスト_: リクエスト, テーブル: str, ID: int, 名前: str = "データ") -> dict:
    """自チームの行だけを返す。他チームのIDを指定しても「見つからない」扱いにする。"""
    行 = リクエスト_.db.execute(f"SELECT * FROM {テーブル} WHERE id = ? AND team_id = ?", (ID, リクエスト_.チームID)).fetchone()
    if 行 is None:
        raise APIエラー(404, f"{名前}が見つかりません")
    return dict(行)


def 選手を確認(リクエスト_: リクエスト, 選手ID: int, 本人以外も閲覧可: bool = False) -> dict:
    """自チームの選手であることを確認。選手ユーザーは本人のデータだけ扱える。"""
    行 = リクエスト_.db.execute(
        "SELECT * FROM users WHERE id = ? AND team_id = ? AND role = 'player'", (選手ID, リクエスト_.チームID)
    ).fetchone()
    if 行 is None:
        raise APIエラー(404, "選手が見つかりません")
    if not リクエスト_.コーチか and not 本人以外も閲覧可 and 選手ID != リクエスト_.ユーザー["id"]:
        raise APIエラー(403, "他の選手の情報は見られません")
    return dict(行)


def 公開ユーザー情報(行: dict) -> dict:
    return {キー: 行[キー] for キー in ("id", "team_id", "login_id", "name", "role", "grade", "position", "number", "photo", "active")}
