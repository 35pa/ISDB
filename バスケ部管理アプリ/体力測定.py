"""体力測定：身長・体重・到達点などの実測値を記録し、基礎体力のスコア（0〜100）に換算する（DB に依存しない純粋関数）。

- 基礎体力は「クリア条件を満たしたか」ではなく、最新の測定値からスコアを出してレーダーチャートに反映する
- 各項目は「0点になる値」「100点になる値」の間を比例で換算し、範囲外は0点・100点で止める
- 基礎体力スコア＝測った項目のスコアの平均（測っていない項目は含めない）
- 垂直跳びは「最高到達点 − 指高」で、同じ日に両方を測ったときに計算する
- 身長・指高は記録のみ（最高到達点に含まれるので、二重に数えないようスコアにはしない）
"""

from __future__ import annotations

# (キー, 名前, 単位, 小数の桁数, 0点の値, 100点の値, 測り方)
# 0点・100点の値が None の項目は記録のみ。0点の値が100点の値より大きい項目は「小さいほどよい」（タイム）
測定項目 = [
    ("height", "身長", "cm", 1, None, None,
     "裸足でかかと・お尻・背中を壁につけ、あごを引いてまっすぐ立つ。頭のてっぺんの高さを測る。"),
    ("weight", "体重（体の強さ）", "kg", 1, 40, 100,
     "練習前に体重計で測る。当たり負けしない体の強さの目安として使う。"),
    ("standing_reach", "指高", "cm", 0, None, None,
     "立って片手を伸ばした高さ。壁の横に裸足で立ち、壁側の手をまっすぐ上に伸ばす。かかとを上げずに届く一番高い指先の位置を床から測る。"),
    ("jump_reach", "最高到達点", "cm", 0, 230, 340,
     "指高と同じ壁で、その場から腕を振って真上に跳び（助走なし）、一番高い点にタッチする。床からの高さを測る。3回跳んで最高記録。"),
    ("vertical_jump", "垂直跳び", "cm", 0, 20, 90,
     "入力しなくてよい。同じ日に測った「最高到達点 − 指高」で自動計算する。"),
    ("standing_long_jump", "立ち幅跳び", "cm", 0, 150, 300,
     "ラインにつま先をそろえ、腕を振って両足で前へ跳び、両足で着地。ラインから、着地した一番後ろのかかとまでを測る。3回跳んで最高記録。"),
    ("pro_agility", "プロアジリティ", "秒", 2, 6.2, 4.2,
     "5-10-5のシャトル走。中央のラインと左右5mにライン。中央から左へ5m→右へ10m→左へ5mを全力で走り、ラインは手でタッチ。右スタート・左スタートを測り、よいほうを記録。"),
    ("shuttle_17", "17往復シャトル", "秒", 1, 80, 50,
     "サイドラインからサイドライン（15m）を17回走る（片道で1回・合計255m）。ラインは足で踏む。1本の記録を入力。"),
]

項目 = {キー: {"key": キー, "name": 名前, "unit": 単位, "digits": 桁, "zero": 零点, "full": 満点, "how": 測り方}
        for キー, 名前, 単位, 桁, 零点, 満点, 測り方 in 測定項目}
計算で出す項目 = {"vertical_jump"}
入力する項目 = tuple(キー for キー, *_ in 測定項目 if キー not in 計算で出す項目)
入力範囲 = {
    "height": (80, 250), "weight": (15, 200), "standing_reach": (100, 330), "jump_reach": (100, 400),
    "standing_long_jump": (30, 400), "pro_agility": (3.0, 15.0), "shuttle_17": (30.0, 200.0),
}
測定で決めるスキル = "基礎体力"


def 項目スコア(キー: str, 値: float | None) -> int | None:
    """実測値を0〜100に換算する。記録のみの項目や未測定は None。"""
    定義 = 項目[キー]
    if 値 is None or 定義["zero"] is None:
        return None
    零点, 満点 = 定義["zero"], 定義["full"]
    割合 = (値 - 零点) / (満点 - 零点)
    return round(100 * max(0.0, min(1.0, 割合)))


def 最新の測定値(記録一覧: list[dict]) -> dict[str, dict]:
    """記録（{"item", "value", "measured_on"}）から、項目ごとの最新値を返す。垂直跳びは同じ日の到達点と指高から計算する。"""
    並び = sorted(記録一覧, key=lambda r: (r["measured_on"], r.get("id") or 0))
    最新: dict[str, dict] = {}
    日別: dict[str, dict[str, float]] = {}
    for 行 in 並び:
        最新[行["item"]] = {"value": 行["value"], "measured_on": 行["measured_on"]}
        日別.setdefault(行["measured_on"], {})[行["item"]] = 行["value"]
    for 日, 値 in sorted(日別.items()):
        if "jump_reach" in 値 and "standing_reach" in 値 and 値["jump_reach"] >= 値["standing_reach"]:
            最新["vertical_jump"] = {"value": 値["jump_reach"] - 値["standing_reach"], "measured_on": 日}
    return 最新


def 基礎体力の評価(記録一覧: list[dict]) -> dict:
    """項目ごとの最新値・スコアと、基礎体力スコア（採点する項目の平均）を返す。"""
    最新 = 最新の測定値(記録一覧)
    内訳 = []
    for キー, *_ in 測定項目:
        定義 = 項目[キー]
        値 = 最新.get(キー)
        内訳.append(
            {
                **定義,
                "value": round(値["value"], 定義["digits"]) if 値 else None,
                "measured_on": 値["measured_on"] if 値 else None,
                "score": 項目スコア(キー, 値["value"]) if 値 else None,
                "scored": 定義["zero"] is not None,
                "derived": キー in 計算で出す項目,
            }
        )
    点 = [行["score"] for 行 in 内訳 if 行["score"] is not None]
    return {"score": round(sum(点) / len(点)) if 点 else None, "items": 内訳, "scored_count": len(点)}
