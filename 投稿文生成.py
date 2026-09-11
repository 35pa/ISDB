"""Claude API で X 投稿文の候補を複数生成し、伸びる確率で採点する。

プロンプト本体は プロンプト.md（動画で言う「4つの変数」を差し込む雛形）。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import anthropic

from アフィリエイトリンク import 商品

既定モデル = "claude-opus-5"
候補数 = 3

# X の文字数制限: 全角1文字=2ポイント、上限280ポイント。
# 本文にはURLを入れない（リプライに貼る）ので、ハッシュタグ分を残して全角110文字以内。
本文の最大文字数 = 110

プロンプトファイル = Path(__file__).resolve().parent / "プロンプト.md"

出力スキーマ = {
    "type": "object",
    "properties": {
        "ターゲットの本音の悩み": {"type": "array", "items": {"type": "string"}},
        "候補": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "切り口": {"type": "string"},
                    "本文": {"type": "string", "description": "投稿本文（URL・ハッシュタグ・PR表記を含まない）"},
                    "ハッシュタグ": {"type": "array", "items": {"type": "string"}},
                    "誘導文": {"type": "string", "description": "リンクを貼るリプライに添える一言"},
                    "伸びる確率": {"type": "integer", "minimum": 0, "maximum": 100},
                    "採点": {
                        "type": "object",
                        "properties": {
                            "共感度": {"type": "integer", "minimum": 0, "maximum": 25},
                            "具体性": {"type": "integer", "minimum": 0, "maximum": 25},
                            "クリック誘導": {"type": "integer", "minimum": 0, "maximum": 25},
                            "拡散性": {"type": "integer", "minimum": 0, "maximum": 25},
                        },
                        "required": ["共感度", "具体性", "クリック誘導", "拡散性"],
                        "additionalProperties": False,
                    },
                    "採点理由": {"type": "string"},
                },
                "required": ["切り口", "本文", "ハッシュタグ", "誘導文", "伸びる確率", "採点", "採点理由"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["ターゲットの本音の悩み", "候補"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class 投稿候補:
    切り口: str
    本文: str
    ハッシュタグ: list[str]
    誘導文: str
    伸びる確率: int
    採点: dict[str, int] = field(default_factory=dict)
    採点理由: str = ""


@dataclass(frozen=True)
class 生成結果:
    候補: list[投稿候補]
    本音の悩み: list[str] = field(default_factory=list)

    @property
    def 最良(self) -> 投稿候補:
        return max(self.候補, key=lambda c: c.伸びる確率)


def プロンプトを組み立て(商品_: 商品, 過去投稿: list[str], 雛形: str | None = None) -> str:
    雛形 = 雛形 if 雛形 is not None else プロンプトファイル.read_text(encoding="utf-8")
    本文 = 雛形.format(
        ジャンル=商品_.ジャンル or "（指定なし）",
        ターゲット=商品_.ターゲット or "（指定なし）",
        商品名=商品_.商品名,
        特徴=商品_.特徴 or "（不明。商品名から推測）",
        口調=商品_.口調 or "丁寧系",
        候補数=候補数,
        最大文字数=本文の最大文字数,
    )
    過去 = "\n".join(f"- {t}" for t in 過去投稿[-5:]) or "（なし）"
    return f"{本文}\n\n## 過去の投稿（切り口の重複を避ける）\n{過去}"


def _呼び出し(client: anthropic.Anthropic, モデル: str, プロンプト: str, フォールバック: bool):
    引数 = dict(
        model=モデル,
        max_tokens=8192,
        messages=[{"role": "user", "content": プロンプト}],
        output_config={"format": {"type": "json_schema", "schema": 出力スキーマ}},
    )
    if フォールバック:
        # 安全分類器が拒否した場合にサーバー側で別モデルへ自動フォールバック
        return client.beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **引数
        )
    return client.messages.create(**引数)


def 応答を解釈(テキスト: str) -> 生成結果:
    データ = json.loads(テキスト)
    候補 = []
    for c in データ.get("候補", []):
        本文 = str(c.get("本文", "")).strip()
        if not 本文:
            continue
        候補.append(
            投稿候補(
                切り口=str(c.get("切り口", "")).strip(),
                本文=本文,
                ハッシュタグ=[str(t).strip().lstrip("#") for t in c.get("ハッシュタグ", []) if str(t).strip()],
                誘導文=str(c.get("誘導文", "")).strip() or "気になった人はここからチェックしてみてね👇",
                伸びる確率=int(c.get("伸びる確率", 0)),
                採点={k: int(v) for k, v in (c.get("採点") or {}).items()},
                採点理由=str(c.get("採点理由", "")).strip(),
            )
        )
    if not 候補:
        raise RuntimeError("Claude の出力に投稿候補がありません")
    return 生成結果(候補=候補, 本音の悩み=[str(x) for x in データ.get("ターゲットの本音の悩み", [])])


def 投稿文を生成(商品_: 商品, 過去投稿: list[str] | None = None, *, モデル: str | None = None) -> 生成結果:
    """Claude に投稿候補を複数生成させ、採点付きで返す。"""
    client = anthropic.Anthropic()
    モデル = モデル or os.environ.get("CLAUDE_MODEL") or 既定モデル
    プロンプト = プロンプトを組み立て(商品_, 過去投稿 or [])

    try:
        response = _呼び出し(client, モデル, プロンプト, フォールバック=True)
    except anthropic.BadRequestError:
        # フォールバック機能が使えない環境（ベータ未対応など）では通常呼び出しに切り替える
        response = _呼び出し(client, モデル, プロンプト, フォールバック=False)

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude が生成を拒否しました（stop_reason=refusal）")

    テキスト = next(b.text for b in response.content if b.type == "text")
    return 応答を解釈(テキスト)
