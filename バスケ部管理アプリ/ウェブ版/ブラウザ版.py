"""ブラウザ版（お試し版）の入口：サーバーの代わりに、ブラウザの中（Pyodide）で API を実行する。

- API の処理はサーバー版とまったく同じ（API_*.py をそのまま使う）
- データベースはメモリ上に置き、変更のたびに中身（バイト列）を JavaScript 側へ渡して端末に保存する
- 初回はデモ用チーム（サンプルデータ入り）を作る
"""

from __future__ import annotations

import json
import sqlite3
import traceback
from urllib.parse import parse_qs, unquote, urlsplit

import API_スキル  # noqa: F401  ルート登録のために読み込む
import API_チーム運営  # noqa: F401
import API_戦術  # noqa: F401
import API_選手カルテ  # noqa: F401
import API_練習  # noqa: F401
import データベース
import 認証
from ルーティング import APIエラー, リクエスト, 振り分け

# パスワードのハッシュ計算は端末内だけで使うので軽くする（スマホで待たされないように）
認証.反復回数 = 20_000

db: sqlite3.Connection | None = None


def 開始(保存データ=None) -> str:
    """保存データ（JavaScript の Uint8Array または bytes）があれば読み込み、なければデモ用チームを作る。案内文を返す。"""
    global db
    if db is not None:
        db.close()
    db = データベース.接続(":memory:")
    if 保存データ is not None and hasattr(保存データ, "to_bytes"):
        保存データ = 保存データ.to_bytes()
    if 保存データ:
        db.deserialize(bytes(保存データ))
        db.execute("PRAGMA foreign_keys = ON")
        データベース.初期化(db)  # 古い版で保存したデータも今の形にそろえる
        return ""
    データベース.初期化(db)
    import デモデータ

    return デモデータ.デモチームを作成(db)


def 中身() -> bytes:
    return db.serialize()


def API実行(メソッド: str, URL: str, 本文の文字列: str, トークン: str) -> str:
    """結果を JSON 文字列 {"status": 数, "body": 値} で返す。"""
    分解 = urlsplit(URL)
    クエリ = {キー: 値[0] for キー, 値 in parse_qs(分解.query).items()}
    try:
        本文 = json.loads(本文の文字列) if 本文の文字列 else {}
        if not isinstance(本文, dict):
            raise ValueError
    except ValueError:
        return json.dumps({"status": 400, "body": {"error": "送信データの形式が正しくありません"}}, ensure_ascii=False)
    try:
        ユーザー = 認証.セッションからユーザー(db, トークン)
        結果 = 振り分け(リクエスト(メソッド, unquote(分解.path), クエリ, 本文, db, ユーザー, トークン))
        db.commit()
        状態, 値 = 200, 結果
    except APIエラー as エラー:
        db.rollback()
        状態, 値 = エラー.ステータス, {"error": エラー.メッセージ}
    except sqlite3.IntegrityError:
        db.rollback()
        状態, 値 = 400, {"error": "入力内容が他のデータと矛盾しています"}
    except Exception:
        db.rollback()
        traceback.print_exc()
        状態, 値 = 500, {"error": "エラーが発生しました"}
    return json.dumps({"status": 状態, "body": 値}, ensure_ascii=False)
