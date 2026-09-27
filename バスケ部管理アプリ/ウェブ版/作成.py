"""ウェブ版（お試し版）を組み立てる。サーバーなしでブラウザだけで動く版を「ウェブ版/出力」に作る。

使い方:  python ウェブ版/作成.py

出力（「出力/公開」フォルダ。Git には入れない。この中身をそのまま公開する）
- バスケ部ノート.html … ページ本体（CSS・起動処理・アプリの JavaScript を1つにまとめたもの）
- アプリ.zip.txt      … サーバーの Python ファイル（ブラウザの中で動かす）
- pyodide/            … ブラウザで Python を動かす部品（Pyodide）
公開先は .zip などの圧縮ファイルを置けないため、圧縮ファイルは Base64 の文字にして「〜.txt」で置き、
起動処理.js が読み込むときに元に戻す。

必要なもの: Python 3.11 以上、Node.js（npx で esbuild を使う）、インターネット接続（初回のみ Pyodide を取得）
ページ本体は <html>・<head>・<body> を書かない形（公開先が外側を付ける）。手元で試すときは同じフォルダの「確認用.html」を使う（公開はしない）。
"""

from __future__ import annotations

import base64
import io
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ここ = Path(__file__).resolve().parent
アプリのフォルダ = ここ.parent
出力 = ここ / "出力"
部品置き場 = 出力 / "部品"  # 取得した Pyodide（次回から再利用）
公開 = 出力 / "公開"
Pyodideの版 = "0.27.7"
esbuildの版 = "0.24.2"
# 必要な Pyodide の部品。コア（npm の pyodide パッケージ）と、別配布の sqlite3・hashlib（公式リリースから取り出す）
コアの部品 = ("pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json")
追加の部品 = ("sqlite3-", "hashlib-", "openssl-")
除くPython = {"サーバー.py"}


def _取得(URL: str) -> urllib.request.addinfourl:
    return urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "basket-note-build"}), timeout=600)


def Pyodideを用意() -> None:
    置き場 = 部品置き場
    置き場.mkdir(parents=True, exist_ok=True)
    if not all((置き場 / 名前).exists() for 名前 in コアの部品):
        print("Pyodide（コア）を取得しています…")
        with _取得(f"https://registry.npmjs.org/pyodide/-/pyodide-{Pyodideの版}.tgz") as 応答:
            with tarfile.open(fileobj=io.BytesIO(応答.read()), mode="r:gz") as 圧縮:
                for 名前 in コアの部品:
                    (置き場 / 名前).write_bytes(圧縮.extractfile(f"package/{名前}").read())
    if not all(any(p.name.startswith(先頭) for p in 置き場.iterdir()) for 先頭 in 追加の部品):
        print("Pyodide（sqlite3・hashlib）を取得しています…（公式リリースから必要な部品だけ取り出すので数分かかります）")
        URL = f"https://github.com/pyodide/pyodide/releases/download/{Pyodideの版}/pyodide-{Pyodideの版}.tar.bz2"
        with _取得(URL) as 応答, tarfile.open(fileobj=応答, mode="r|bz2") as 圧縮:
            for 項目 in 圧縮:
                名前 = 項目.name.rsplit("/", 1)[-1]
                if 項目.isfile() and 名前.startswith(追加の部品) and not 名前.endswith(".metadata"):
                    (置き場 / 名前).write_bytes(圧縮.extractfile(項目).read())


def _文字にして置く(中身: bytes, 置き先: Path) -> None:
    置き先.parent.mkdir(parents=True, exist_ok=True)
    置き先.write_text(base64.b64encode(中身).decode("ascii"), encoding="ascii")


def 部品を公開用に置く() -> None:
    for パス in sorted(部品置き場.iterdir()):
        if パス.suffix in (".zip", ".whl"):
            _文字にして置く(パス.read_bytes(), 公開 / "pyodide" / f"{パス.name}.txt")
        elif パス.suffix in (".wasm", ".json"):
            shutil.copyfile(パス, 公開 / "pyodide" / パス.name)


def Pythonをまとめる() -> None:
    バッファ = io.BytesIO()
    with zipfile.ZipFile(バッファ, "w", zipfile.ZIP_DEFLATED) as 圧縮:
        for パス in sorted(アプリのフォルダ.glob("*.py")):
            if パス.name in 除くPython or パス.name.startswith("テスト_"):
                continue
            圧縮.write(パス, パス.name)
        圧縮.write(ここ / "ブラウザ版.py", "ブラウザ版.py")
    _文字にして置く(バッファ.getvalue(), 公開 / "アプリ.zip.txt")


def JavaScriptをまとめる() -> str:
    """公開/アプリ.js から読み込む全画面を1つのスクリプトにまとめる（画面ごとの遅延読み込みも取り込む）。"""
    結果 = subprocess.run(
        ["npx", "--yes", f"esbuild@{esbuildの版}", str(アプリのフォルダ / "公開" / "アプリ.js"),
         "--bundle", "--format=iife", "--charset=utf8", "--minify", "--target=es2020,safari15", "--log-level=warning"],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if 結果.returncode != 0:
        sys.exit(f"JavaScript をまとめられませんでした:\n{結果.stderr}")
    return 結果.stdout


def ページを作る(アプリのJS: str) -> None:
    def 埋め込み用(文字列: str) -> str:
        return 文字列.replace("</script", "<\\/script").replace("</style", "<\\/style")

    ページ = (ここ / "ページ.html").read_text(encoding="utf-8")
    ページ = ページ.replace("/*スタイル*/", 埋め込み用((アプリのフォルダ / "公開" / "スタイル.css").read_text(encoding="utf-8")))
    ページ = ページ.replace("/*Pyodideの版*/", Pyodideの版)
    ページ = ページ.replace("/*起動処理*/", 埋め込み用((ここ / "起動処理.js").read_text(encoding="utf-8")))
    ページ = ページ.replace("/*アプリ*/", 埋め込み用(アプリのJS))
    (公開 / "バスケ部ノート.html").write_text(ページ, encoding="utf-8")
    # 手元で試すための外枠つきのページ（公開先が付ける <html> などを自分で付ける）
    (公開 / "確認用.html").write_text(
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head><body>'
        + ページ + "</body></html>",
        encoding="utf-8",
    )


def main() -> None:
    shutil.rmtree(公開, ignore_errors=True)
    (公開 / "pyodide").mkdir(parents=True)
    Pyodideを用意()
    部品を公開用に置く()
    Pythonをまとめる()
    ページを作る(JavaScriptをまとめる())
    for パス in sorted(p for p in 公開.rglob("*") if p.is_file()):
        print(f"  {パス.relative_to(公開)}  {パス.stat().st_size / 1_000_000:.1f}MB")
    print(f"できました: {公開}")


if __name__ == "__main__":
    if not shutil.which("npx"):
        sys.exit("Node.js（npx）が必要です")
    main()
