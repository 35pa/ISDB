"""Claude API で X 投稿文を生成する。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import anthropic

from アフィリエイトリンク import 商品

既定モデル = "claude-opus-5"

# X の文字数制限: 全角1文字=2ポイント、上限280ポイント、URLは一律23ポイント。
# 【PR】＋改行＋ハッシュタグ＋URL の分を差し引き、本文は全角90文字以内に抑える。
本文の最大文字数 = 90

システムプロンプト = """あなたは日本語のSNSマーケターです。Amazonの商品をX（旧Twitter）で紹介する投稿文を書きます。

守ること:
- 読者にとっての具体的なメリットを1つに絞り、体験談風に自然な口語で書く
- 誇大表現・断定的な効果効能・「最安」「必ず」などの表現は使わない
- 絵文字は最大2個まで
- 商品名は必ず含める
- 本文は全角{最大}文字以内（厳守）。URL・ハッシュタグ・「PR」表記は本文に含めない（別途付与する）
- ハッシュタグは2〜3個。日本語で、商品ジャンルに関するもの
- 過去の投稿と似た切り口・言い回しを避ける
""".format(最大=本文の最大文字数)

出力スキーマ = {
    "type": "object",
    "properties": {
        "本文": {"type": "string", "description": "投稿本文（URL・ハッシュタグを含まない）"},
        "ハッシュタグ": {
            "type": "array",
            "items": {"type": "string"},
            "description": "先頭の#を含まないハッシュタグ語",
        },
    },
    "required": ["本文", "ハッシュタグ"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class 生成結果:
    本文: str
    ハッシュタグ: list[str]


def _ユーザープロンプト(商品_: 商品, 過去投稿: list[str]) -> str:
    過去 = "\n".join(f"- {t}" for t in 過去投稿[-5:]) or "（なし）"
    return (
        "次の商品を紹介する投稿文を1つ作ってください。\n\n"
        f"商品名: {商品_.商品名}\n"
        f"カテゴリ: {商品_.カテゴリ}\n"
        f"特徴: {商品_.特徴}\n"
        f"価格帯: {商品_.価格帯}\n\n"
        f"最近の投稿（切り口の重複を避ける）:\n{過去}"
    )


def _呼び出し(client: anthropic.Anthropic, モデル: str, メッセージ: list[dict], フォールバック: bool):
    引数 = dict(
        model=モデル,
        max_tokens=4096,
        system=システムプロンプト,
        messages=メッセージ,
        output_config={"format": {"type": "json_schema", "schema": 出力スキーマ}},
    )
    if フォールバック:
        # 安全分類器が拒否した場合にサーバー側で別モデルへ自動フォールバック
        return client.beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **引数
        )
    return client.messages.create(**引数)


def 投稿文を生成(商品_: 商品, 過去投稿: list[str] | None = None, *, モデル: str | None = None) -> 生成結果:
    """Claude に投稿本文とハッシュタグを生成させる。"""
    client = anthropic.Anthropic()
    モデル = モデル or os.environ.get("CLAUDE_MODEL") or 既定モデル
    メッセージ = [{"role": "user", "content": _ユーザープロンプト(商品_, 過去投稿 or [])}]

    try:
        response = _呼び出し(client, モデル, メッセージ, フォールバック=True)
    except anthropic.BadRequestError:
        # フォールバック機能が使えない環境（ベータ未対応など）では通常呼び出しに切り替える
        response = _呼び出し(client, モデル, メッセージ, フォールバック=False)

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude が生成を拒否しました（stop_reason=refusal）")

    テキスト = next(b.text for b in response.content if b.type == "text")
    データ = json.loads(テキスト)
    本文 = str(データ["本文"]).strip()
    タグ = [str(t).strip().lstrip("#") for t in データ["ハッシュタグ"] if str(t).strip()]
    if not 本文:
        raise RuntimeError("Claude の出力に本文がありません")
    return 生成結果(本文=本文, ハッシュタグ=タグ)
