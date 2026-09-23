"""バスケ部管理アプリのサーバー（Python 標準ライブラリのみで動作）。

使い方:
  python サーバー.py                 # http://localhost:8000 で起動
  python サーバー.py --demo          # デモ用チーム（サンプルデータ入り）も作成して起動
  python サーバー.py --port 8080 --db データ/本番.sqlite3
  python サーバー.py --demo --open   # 起動後にブラウザを自動で開く（起動ファイルが使う）
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import socket
import sqlite3
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import API_スキル  # noqa: F401  ルート登録のために読み込む
import API_チーム運営  # noqa: F401
import API_戦術  # noqa: F401
import API_選手カルテ  # noqa: F401
import API_練習  # noqa: F401
import データベース
from ルーティング import APIエラー, リクエスト, 振り分け
from 認証 import セッションからユーザー

ルート = Path(__file__).resolve().parent
公開フォルダ = ルート / "公開"
既定のDB = ルート / "データ" / "バスケ部.sqlite3"
本文の上限 = 2_000_000

mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("image/svg+xml", ".svg")

セキュリティヘッダー = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    ),
}


class アプリ:
    """DB 接続と排他制御をまとめたもの。部活規模のアクセス量なので、API 処理は1件ずつ直列に実行する。"""

    def __init__(self, DBパス: str | Path):
        if str(DBパス) != ":memory:":
            Path(DBパス).parent.mkdir(parents=True, exist_ok=True)
        self.db = データベース.接続(DBパス)
        データベース.初期化(self.db)
        self.ロック = threading.Lock()

    def API実行(self, メソッド: str, パス: str, クエリ: dict, 本文: dict, トークン: str) -> tuple[int, object]:
        with self.ロック:
            try:
                ユーザー = セッションからユーザー(self.db, トークン)
                要求 = リクエスト(メソッド, パス, クエリ, 本文, self.db, ユーザー, トークン)
                結果 = 振り分け(要求)
                self.db.commit()
                return 200, 結果
            except APIエラー as エラー:
                self.db.rollback()
                return エラー.ステータス, {"error": エラー.メッセージ}
            except sqlite3.IntegrityError:
                self.db.rollback()
                return 400, {"error": "入力内容が他のデータと矛盾しています"}
            except Exception:
                self.db.rollback()
                traceback.print_exc()
                return 500, {"error": "サーバーでエラーが発生しました"}


def ハンドラーを作成(アプリ_: アプリ) -> type[BaseHTTPRequestHandler]:
    class ハンドラー(BaseHTTPRequestHandler):
        server_version = "BasketClub/1.0"
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            if not getattr(self.server, "静か", False):
                super().log_message(format, *args)

        def _送信(self, ステータス: int, 本文: bytes, 種類: str, 追加: dict | None = None) -> None:
            self.send_response(ステータス)
            self.send_header("Content-Type", 種類)
            self.send_header("Content-Length", str(len(本文)))
            for キー, 値 in {**セキュリティヘッダー, **(追加 or {})}.items():
                self.send_header(キー, 値)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(本文)

        def _JSON送信(self, ステータス: int, データ: object) -> None:
            self._送信(ステータス, json.dumps(データ, ensure_ascii=False).encode(), "application/json; charset=utf-8", {"Cache-Control": "no-store"})

        def _API(self, メソッド: str) -> None:
            分解 = urlsplit(self.path)
            クエリ = {キー: 値[0] for キー, 値 in parse_qs(分解.query).items()}
            本文: dict = {}
            if メソッド in ("POST", "PUT"):
                try:
                    長さ = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    長さ = -1
                if 長さ < 0 or 長さ > 本文の上限:
                    self._JSON送信(413, {"error": "送信データが大きすぎます"})
                    self.close_connection = True
                    return
                生 = self.rfile.read(長さ) if 長さ else b""
                if 生:
                    try:
                        本文 = json.loads(生)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        self._JSON送信(400, {"error": "送信データの形式が正しくありません"})
                        return
                    if not isinstance(本文, dict):
                        self._JSON送信(400, {"error": "送信データの形式が正しくありません"})
                        return
            認可 = self.headers.get("Authorization", "")
            トークン = 認可[7:].strip() if 認可.startswith("Bearer ") else ""
            ステータス, 結果 = アプリ_.API実行(メソッド, unquote(分解.path), クエリ, 本文, トークン)
            self._JSON送信(ステータス, 結果)

        def _静的ファイル(self) -> None:
            パス = unquote(urlsplit(self.path).path)
            if パス in ("", "/"):
                パス = "/index.html"
            try:
                対象 = (公開フォルダ / パス.lstrip("/")).resolve()
            except (OSError, ValueError):
                対象 = None
            if 対象 is None or not 対象.is_relative_to(公開フォルダ) or not 対象.is_file():
                # 画面遷移（#/...）はクライアント側なので、未知のパスはトップへ
                self._送信(404, "見つかりません".encode(), "text/plain; charset=utf-8")
                return
            種類 = mimetypes.guess_type(対象.name)[0] or "application/octet-stream"
            if 種類.startswith("text/") or 種類 in ("application/json", "application/manifest+json", "image/svg+xml"):
                種類 += "; charset=utf-8"
            追加 = {"Cache-Control": "no-cache"}
            if 対象.name == "オフライン対応.js":
                追加["Service-Worker-Allowed"] = "/"
            self._送信(200, 対象.read_bytes(), 種類, 追加)

        def do_GET(self) -> None:  # noqa: N802
            if self.path.startswith("/api/"):
                self._API("GET")
            else:
                self._静的ファイル()

        def do_HEAD(self) -> None:  # noqa: N802
            self._静的ファイル()

        def do_POST(self) -> None:  # noqa: N802
            self._API("POST") if self.path.startswith("/api/") else self._JSON送信(404, {"error": "見つかりません"})

        def do_PUT(self) -> None:  # noqa: N802
            self._API("PUT") if self.path.startswith("/api/") else self._JSON送信(404, {"error": "見つかりません"})

        def do_DELETE(self) -> None:  # noqa: N802
            self._API("DELETE") if self.path.startswith("/api/") else self._JSON送信(404, {"error": "見つかりません"})

    return ハンドラー


def サーバーを作成(DBパス: str | Path, ホスト: str = "0.0.0.0", ポート: int = 8000, 静か: bool = False) -> tuple[ThreadingHTTPServer, アプリ]:
    アプリ_ = アプリ(DBパス)
    サーバー = ThreadingHTTPServer((ホスト, ポート), ハンドラーを作成(アプリ_))
    サーバー.静か = 静か
    サーバー.daemon_threads = True
    return サーバー, アプリ_


def _LANのIPアドレス() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 80))  # 実際には送信しない（経路の確認だけ）
            return s.getsockname()[0]
    except OSError:
        return None


def main() -> int | None:
    引数 = argparse.ArgumentParser(description="バスケ部管理アプリのサーバー")
    引数.add_argument("--host", default="0.0.0.0", help="待ち受けアドレス（既定: 0.0.0.0 = 同じWi-Fiのスマホからも接続可）")
    引数.add_argument("--port", type=int, default=8000, help="ポート番号（既定: 8000）")
    引数.add_argument("--db", default=str(既定のDB), help="データベースファイルの場所")
    引数.add_argument("--demo", action="store_true", help="デモ用チームとサンプルデータを作成する")
    引数.add_argument("--open", action="store_true", help="起動後にブラウザで自動的に開く（ポートが使用中なら空いている番号を探す）")
    設定 = 引数.parse_args()

    # --open（起動ファイルからの実行）のときは、ポートが使用中でも次の番号で起動する
    試す数 = 10 if 設定.open else 1
    for ずらし in range(試す数):
        try:
            サーバー, アプリ_ = サーバーを作成(設定.db, 設定.host, 設定.port + ずらし)
            設定.port += ずらし
            break
        except OSError:
            if ずらし == 試す数 - 1:
                print(f"ポート {設定.port} は使用中です。--port 8080 のように別の番号を指定してください")
                return 1
    if 設定.demo:
        import デモデータ

        with アプリ_.ロック:
            案内 = デモデータ.デモチームを作成(アプリ_.db)
        print(案内)
    print(f"起動しました: http://localhost:{設定.port}")
    LAN = _LANのIPアドレス()
    if LAN and 設定.host in ("0.0.0.0", ""):
        print(f"同じWi-Fiのスマホからは: http://{LAN}:{設定.port}")
    print("終了するには Ctrl + C（またはこの画面を閉じる）")
    if 設定.open:
        threading.Timer(1.0, webbrowser.open, args=(f"http://localhost:{設定.port}",)).start()
    try:
        サーバー.serve_forever()
    except KeyboardInterrupt:
        print("\n終了しました")
    finally:
        サーバー.server_close()


if __name__ == "__main__":
    sys.exit(main())
