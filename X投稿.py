"""X (旧Twitter) API v2 への投稿と、文字数（重み付き）の計算。"""

from __future__ import annotations

import os
import re

import tweepy

上限ポイント = 280
URLポイント = 23
_URL形式 = re.compile(r"https?://\S+")

# twitter-text の重み付け: 以下の範囲の文字は1ポイント、それ以外（日本語など）は2ポイント
_1ポイント範囲 = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))


def 文字数ポイント(テキスト: str) -> int:
    """X の投稿制限に用いる重み付き文字数を返す。URLは一律23ポイント。"""
    合計 = 0
    残り = テキスト
    for url in _URL形式.findall(テキスト):
        合計 += URLポイント
        残り = 残り.replace(url, "", 1)
    for 文字 in 残り:
        cp = ord(文字)
        合計 += 1 if any(a <= cp <= b for a, b in _1ポイント範囲) else 2
    return 合計


def 本文を組み立て(本文: str, ハッシュタグ: list[str]) -> str:
    """本文 + ハッシュタグ + #PR を1本目の投稿にまとめ、上限内に収める（URLはリプライに貼る）。"""
    本文 = 本文.strip()
    タグ = [t for t in ハッシュタグ if t and t.upper() != "PR"]
    while True:
        タグ行 = " ".join(f"#{t}" for t in タグ + ["PR"])
        投稿 = f"{本文}\n\n{タグ行}"
        if 文字数ポイント(投稿) <= 上限ポイント:
            return 投稿
        if タグ:
            タグ = タグ[:-1]
            continue
        if len(本文) <= 10:
            raise ValueError("本文を短縮しても投稿上限に収まりません")
        本文 = 本文.rstrip("…")[:-1].rstrip() + "…"


def リンク投稿を組み立て(誘導文: str, url: str) -> str:
    """2本目（リプライ）: 誘導文 + 【PR】 + アフィリエイトリンク。"""
    誘導文 = 誘導文.strip()
    while True:
        投稿 = f"{誘導文}\n【PR】\n{url}" if 誘導文 else f"【PR】\n{url}"
        if 文字数ポイント(投稿) <= 上限ポイント:
            return 投稿
        誘導文 = 誘導文.rstrip("…")[:-1].rstrip() + "…" if len(誘導文) > 1 else ""


def Xクライアント() -> tweepy.Client:
    必須 = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    欠落 = [k for k in 必須 if not os.environ.get(k)]
    if 欠落:
        raise RuntimeError(f"環境変数が未設定です: {', '.join(欠落)}")
    return tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def Xに投稿(テキスト: str, 返信先ID: str | None = None, client: tweepy.Client | None = None) -> str:
    """投稿して投稿IDを返す。返信先IDを渡すとリプライとして投稿する。"""
    if 文字数ポイント(テキスト) > 上限ポイント:
        raise ValueError("投稿が文字数上限を超えています")
    client = client or Xクライアント()
    応答 = client.create_tweet(text=テキスト, in_reply_to_tweet_id=返信先ID)
    return str(応答.data["id"])


def スレッド投稿(本文投稿: str, リンク投稿: str) -> tuple[str, str]:
    """1本目に本文、そのリプライにリンクを投稿し、両方のIDを返す。"""
    client = Xクライアント()
    本文ID = Xに投稿(本文投稿, client=client)
    リンクID = Xに投稿(リンク投稿, 返信先ID=本文ID, client=client)
    return 本文ID, リンクID
