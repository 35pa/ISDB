"""Amazonアフィリエイト商品を Claude で文章化し X に自動投稿するメインスクリプト。

使い方:
  python 自動投稿.py            # 商品を1つ選んで投稿
  python 自動投稿.py --dry-run  # 投稿せず文面を表示するだけ
  python 自動投稿.py --asin B0XXXXXXXX  # 商品を指定して投稿
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from X投稿 import Xに投稿, 投稿文を組み立て
from アフィリエイトリンク import 商品, 商品リンク
from 投稿文生成 import 投稿文を生成

ルート = Path(__file__).resolve().parent
商品リストファイル = ルート / "商品リスト.csv"
投稿履歴ファイル = ルート / "投稿履歴.json"
日本時間 = timezone(timedelta(hours=9))


def 商品リストを読む(パス: Path | None = None) -> list[商品]:
    パス = パス or 商品リストファイル
    with パス.open(encoding="utf-8-sig", newline="") as f:
        行 = list(csv.DictReader(f))
    商品達 = []
    for r in 行:
        if not (r.get("ASIN") or "").strip():
            continue
        商品達.append(
            商品(
                asin=r["ASIN"].strip().upper(),
                商品名=(r.get("商品名") or "").strip(),
                カテゴリ=(r.get("カテゴリ") or "").strip(),
                特徴=(r.get("特徴") or "").strip(),
                価格帯=(r.get("価格帯") or "").strip(),
                短縮URL=(r.get("短縮URL") or "").strip(),
            )
        )
    if not 商品達:
        raise RuntimeError(f"{パス.name} に商品がありません")
    return 商品達


def 投稿履歴を読む(パス: Path | None = None) -> list[dict]:
    パス = パス or 投稿履歴ファイル
    if not パス.exists():
        return []
    return json.loads(パス.read_text(encoding="utf-8") or "[]")


def 投稿履歴を保存(履歴: list[dict], パス: Path | None = None) -> None:
    パス = パス or 投稿履歴ファイル
    パス.write_text(json.dumps(履歴, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def 次の商品を選ぶ(商品達: list[商品], 履歴: list[dict], 再投稿までの日数: int, 今: datetime) -> 商品:
    """最も長く投稿していない商品を選ぶ（未投稿を最優先、同順位はCSVの並び順）。"""
    最終投稿: dict[str, datetime] = {}
    for h in 履歴:
        t = datetime.fromisoformat(h["投稿日時"])
        if h["asin"] not in 最終投稿 or t > 最終投稿[h["asin"]]:
            最終投稿[h["asin"]] = t

    候補 = sorted(
        enumerate(商品達),
        key=lambda x: (最終投稿.get(x[1].asin, datetime.min.replace(tzinfo=timezone.utc)), x[0]),
    )
    先頭 = 候補[0][1]
    最終 = 最終投稿.get(先頭.asin)
    if 最終 and 今 - 最終 < timedelta(days=再投稿までの日数):
        raise RuntimeError(
            f"全商品が {再投稿までの日数} 日以内に投稿済みです。商品リストを増やすか 再投稿までの日数 を下げてください"
        )
    return 先頭


def 実行(*, dry_run: bool, asin: str | None) -> int:
    load_dotenv(ルート / ".env")
    dry_run = dry_run or os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    再投稿までの日数 = int(os.environ.get("再投稿までの日数", "7"))
    トラッキングID = os.environ.get("AMAZON_ASSOCIATE_TAG", "")

    商品達 = 商品リストを読む()
    履歴 = 投稿履歴を読む()
    今 = datetime.now(日本時間)

    if asin:
        対象 = next((p for p in 商品達 if p.asin == asin.upper()), None)
        if 対象 is None:
            raise RuntimeError(f"ASIN {asin} は商品リストにありません")
    else:
        対象 = 次の商品を選ぶ(商品達, 履歴, 再投稿までの日数, 今)

    url = 商品リンク(対象, トラッキングID)
    過去投稿 = [h["本文"] for h in 履歴 if h["asin"] == 対象.asin]
    生成 = 投稿文を生成(対象, 過去投稿)
    投稿 = 投稿文を組み立て(生成.本文, 生成.ハッシュタグ, url)

    print("=== 投稿内容 ===")
    print(投稿)
    print("================")

    if dry_run:
        print("DRY_RUN のため X には投稿しません")
        return 0

    投稿ID = Xに投稿(投稿)
    履歴.append(
        {
            "asin": 対象.asin,
            "商品名": 対象.商品名,
            "投稿日時": 今.isoformat(timespec="seconds"),
            "投稿ID": 投稿ID,
            "本文": 生成.本文,
            "投稿全文": 投稿,
        }
    )
    投稿履歴を保存(履歴)
    print(f"投稿完了: https://x.com/i/web/status/{投稿ID}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Amazonアフィリエイト × Claude × X 自動投稿")
    parser.add_argument("--dry-run", action="store_true", help="投稿せず文面の表示のみ")
    parser.add_argument("--asin", help="投稿する商品のASINを指定")
    args = parser.parse_args(argv)
    try:
        return 実行(dry_run=args.dry_run, asin=args.asin)
    except Exception as e:  # noqa: BLE001
        print(f"エラー: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
