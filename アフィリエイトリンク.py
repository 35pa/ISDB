"""Amazonアソシエイトのアフィリエイトリンク生成。

PA-API（商品情報API）は売上実績が無いと使えないため、
ASIN と トラッキングID だけで組み立てられる標準形式のリンクを使う。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_ASIN形式 = re.compile(r"^[A-Z0-9]{10}$")


@dataclass(frozen=True)
class 商品:
    asin: str
    商品名: str
    ジャンル: str = ""
    ターゲット: str = ""
    口調: str = ""
    特徴: str = ""
    短縮URL: str = ""

    def __post_init__(self) -> None:
        if not _ASIN形式.match(self.asin):
            raise ValueError(f"ASINの形式が不正です: {self.asin!r}（英数字10桁）")


def アフィリエイトリンク作成(asin: str, トラッキングID: str) -> str:
    """https://www.amazon.co.jp/dp/ASIN?tag=xxxx-22 形式のリンクを返す。"""
    asin = asin.strip().upper()
    if not _ASIN形式.match(asin):
        raise ValueError(f"ASINの形式が不正です: {asin!r}")
    トラッキングID = トラッキングID.strip()
    if not トラッキングID:
        raise ValueError("AMAZON_ASSOCIATE_TAG（トラッキングID）が未設定です")
    return f"https://www.amazon.co.jp/dp/{asin}?tag={トラッキングID}&linkCode=ll1"


def 商品リンク(商品_: 商品, トラッキングID: str) -> str:
    """短縮URL（amzn.to）が登録済みならそれを優先し、無ければ標準リンクを作る。"""
    if 商品_.短縮URL.strip():
        return 商品_.短縮URL.strip()
    return アフィリエイトリンク作成(商品_.asin, トラッキングID)
