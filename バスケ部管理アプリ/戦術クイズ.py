"""戦術の理解度クイズ：問題の種類・タップ問題の採点・図からの「移動先タップ問題」の自動作成（DB に依存しない純粋関数）。

問題の種類
- 選択     ：ふつうの選択問題（コマを指定すると、そのコマを線つきで見せる）
- 次の動き ：コマを途中で止めて「次の動き」を選ぶ。対象の選手の線（答え）は隠して見せる
- 移動先   ：対象の選手がこのあとどこへ動くかを、図をタップして答える（正解は次のコマの位置）
- 位置     ：対象の選手を図から消し、その選手が立つ位置をタップして答える

ポジション（position）は図の選手ID（O1〜O5＝味方、X1〜X5＝相手）をカンマ区切りで持つ。空なら全員向けの問題。
タップ問題は、最初のIDの選手が対象になる。
"""

from __future__ import annotations

import math

問題の種類 = ("選択", "次の動き", "移動先", "位置")
タップの種類 = ("移動先", "位置")
コマが必要な種類 = ("次の動き", "移動先", "位置")
正解の半径 = 50  # タップ問題の正解の範囲（図の単位。選手の丸の半径が16）
自動作成の最小移動 = 60  # これより短い移動は問題にしない
線を持つ距離 = 30  # 線の始点がこの距離以内なら、その選手の線とみなす


def 位置の一覧(位置: str) -> list[str]:
    return [p.strip() for p in (位置 or "").split(",") if p.strip()]


def 選手名(選手ID: str) -> str:
    """O3 → 3番、X4 → X4。"""
    if 選手ID.startswith("O"):
        return f"{選手ID[1:]}番"
    return 選手ID


def タップ判定(目標: dict, x: float, y: float) -> bool:
    return math.hypot(x - 目標["x"], y - 目標["y"]) <= 目標["r"]


def 選手の線(コマ: dict, 選手: dict) -> list[dict]:
    """そのコマで、選手から始まる線（その選手の動き・パス・スクリーン）。"""
    return [
        線 for 線 in コマ.get("lines", [])
        if 線["points"] and math.hypot(線["points"][0][0] - 選手["x"], 線["points"][0][1] - 選手["y"]) <= 線を持つ距離
    ]


def _問題文(名前: str, 線一覧: list[dict], 先: dict) -> str:
    """選手の線のうち、終点が移動先に一番近い線の種類で聞き方を変える（ドリブル・スクリーン・パスの後の移動）。"""
    動き = [線 for 線 in 線一覧 if 線["type"] != "pass"]
    主 = min(動き, key=lambda 線: math.hypot(線["points"][-1][0] - 先["x"], 線["points"][-1][1] - 先["y"]), default=None)
    if 主 is not None and 主["type"] == "dribble":
        return f"{名前}はこのあとドリブルでどこへ進む？進む先をタップしよう"
    if 主 is not None and 主["type"] == "screen":
        return f"{名前}はこのあとどこへスクリーンをかけに行く？その位置をタップしよう"
    if any(線["type"] == "pass" for 線 in 線一覧):
        return f"{名前}はパスをした後どこへ動く？動く先をタップしよう"
    return f"{名前}はこのあとどこへ動く？動く先をタップしよう"


def 移動先の問題を作る(図: dict, 種別: str, 上限: int | None = None) -> list[dict]:
    """コマとコマの間で大きく動いた選手ごとに「移動先タップ問題」を作る。

    オフェンスの戦術は味方（O）、ディフェンスの戦術は相手（X）の選手が対象。
    上限があるときは移動の大きい順に選び、並びはコマ順・選手順にそろえる。
    """
    チーム = "O" if 種別 == "オフェンス" else "X"
    コマ一覧 = 図.get("frames", [])
    候補 = []
    for i, (今, 次) in enumerate(zip(コマ一覧, コマ一覧[1:])):
        次の位置 = {p["id"]: p for p in 次["players"]}
        for 選手 in 今["players"]:
            先 = 次の位置.get(選手["id"])
            if 選手["team"] != チーム or 先 is None:
                continue
            距離 = math.hypot(先["x"] - 選手["x"], 先["y"] - 選手["y"])
            if 距離 < 自動作成の最小移動:
                continue
            説明 = 今.get("note", "")
            候補.append(
                (
                    距離,
                    {
                        "quiz_type": "移動先",
                        "position": 選手["id"],
                        "frame": i,
                        "target": {"x": 先["x"], "y": 先["y"], "r": 正解の半径},
                        "question": _問題文(選手名(選手["id"]), 選手の線(今, 選手), 先),
                        "choices": [],
                        "answer_index": 0,
                        "explanation": f"緑の円が正解の位置。{説明}" if 説明 else "緑の円が正解の位置。",
                    },
                )
            )
    if 上限 is not None:
        候補 = sorted(候補, key=lambda c: -c[0])[:上限]
    return [問 for _, 問 in sorted(候補, key=lambda c: (c[1]["frame"], c[1]["position"]))]


def 問題の鍵(問: dict) -> tuple:
    """同じ問題かどうかの判定に使う（標準データの追加・自動作成の重複防止）。"""
    return (問.get("quiz_type") or "選択", 問["question"], 問.get("frame"), 問.get("position") or "")
