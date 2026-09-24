"""能力値診断・スキルレベル判定・ステップアップ練習メニュー決定のロジック（DB に依存しない純粋関数）。

- 診断方式は「コーチ評価」「自己評価」「スタッツ自動算出」の3つ。揃っている分だけで重み付き平均を取る
- レベルは総合値から 基礎／初級／中級／上級／プロ の5段階で判定
- 総合値が低いスキルほど優先度が高い（次に伸ばすべき項目）
- ドリルは スキル×レベル ごとに段階順に並び、次ステップIDでつながる。完了したら自動で次へ進む
"""

from __future__ import annotations

from typing import Iterable

レベル一覧 = ("基礎", "初級", "中級", "上級", "プロ")
レベル境界 = {"初級": 20, "中級": 40, "上級": 60, "プロ": 80}  # この値以上でそのレベル（基礎は 0 から）
評価元の重み = {"コーチ": 0.5, "スタッツ": 0.3, "自己評価": 0.2}
優先項目の数 = 3
自己評価の差の警告値 = 20
スタッツ算出に必要な試合数 = 2
スタッツ算出の対象試合数 = 10


def レベル判定(値: float | None) -> str:
    if 値 is None:
        return "未診断"
    for レベル in reversed(レベル一覧[1:]):
        if 値 >= レベル境界[レベル]:
            return レベル
    return レベル一覧[0]


def レベルの目安() -> list[dict]:
    """画面表示用：各レベルの数値範囲（下限〜上限）。"""
    下限一覧 = [0] + [レベル境界[レベル] for レベル in レベル一覧[1:]]
    上限一覧 = [下限 - 1 for 下限 in 下限一覧[1:]] + [100]
    return [{"name": 名前, "min": 下限, "max": 上限} for 名前, 下限, 上限 in zip(レベル一覧, 下限一覧, 上限一覧)]


def _線形換算(値: float, 下限: float, 上限: float, 最低点: int = 10, 最高点: int = 95) -> int:
    """下限→最低点、上限→最高点 に線形で当てはめ、範囲外は丸める。"""
    if 上限 == 下限:
        return 最低点
    割合 = (値 - 下限) / (上限 - 下限)
    割合 = max(0.0, min(1.0, 割合))
    return round(最低点 + (最高点 - 最低点) * 割合)


def スタッツから能力値(スキル名: str, スタッツ一覧: list[dict]) -> int | None:
    """直近の試合スタッツからスキル値（0〜100）を自動算出する。算出できないスキルは None。

    スタッツ一覧は新しい順。対象は直近 スタッツ算出の対象試合数 試合。
    """
    対象 = スタッツ一覧[:スタッツ算出の対象試合数]
    試合数 = len(対象)
    if 試合数 < スタッツ算出に必要な試合数:
        return None

    def 合計(キー: str) -> int:
        return sum(int(行.get(キー) or 0) for 行 in 対象)

    if スキル名 == "シュート":
        試投 = 合計("fga")
        if 試投 < 10:
            return None
        実効成功率 = (合計("fgm") + 0.5 * 合計("tpm")) / 試投  # eFG%
        点 = _線形換算(実効成功率, 0.25, 0.55)
        if 合計("fta") >= 5:
            フリースロー率 = 合計("ftm") / 合計("fta")
            点 = round(点 * 0.8 + _線形換算(フリースロー率, 0.4, 0.85) * 0.2)
        return 点
    if スキル名 == "パス":
        アシスト = 合計("assists") / 試合数
        ターンオーバー = 合計("turnovers") / 試合数
        点 = _線形換算(アシスト, 0, 5)
        if アシスト + ターンオーバー > 0:
            比率 = アシスト / max(ターンオーバー, 0.5)
            点 = round(点 * 0.7 + _線形換算(比率, 0.5, 2.5) * 0.3)
        return 点
    if スキル名 == "リバウンド":
        return _線形換算(合計("rebounds") / 試合数, 0, 10)
    if スキル名 == "ディフェンス":
        return _線形換算((合計("steals") + 合計("blocks")) / 試合数, 0, 4)
    if スキル名 == "ドリブル":
        # ボールを扱った結果（アシスト＋ターンオーバー）のうち、ミスしなかった割合で判定
        扱った回数 = 合計("assists") + 合計("turnovers")
        if 扱った回数 < 試合数:
            return None
        return _線形換算(合計("assists") / 扱った回数, 0.3, 0.8)
    return None


def 総合値(評価: dict[str, int | None]) -> int | None:
    """評価元ごとの値（None は未入力）を重み付き平均する。1つもなければ None。"""
    重み合計 = 0.0
    加重和 = 0.0
    for 評価元, 重み in 評価元の重み.items():
        値 = 評価.get(評価元)
        if 値 is None:
            continue
        重み合計 += 重み
        加重和 += 重み * 値
    if 重み合計 == 0:
        return None
    return round(加重和 / 重み合計)


def スキル診断(カテゴリ一覧: list[dict], 最新評価: dict[int, dict[str, int]], スタッツ一覧: list[dict]) -> list[dict]:
    """カテゴリごとに 各評価元の値・総合値・レベル・優先順位 をまとめる。

    最新評価: {カテゴリID: {"コーチ": 値, "自己評価": 値}}
    """
    結果 = []
    for カテゴリ in カテゴリ一覧:
        評価 = dict(最新評価.get(カテゴリ["id"], {}))
        評価["スタッツ"] = スタッツから能力値(カテゴリ["name"], スタッツ一覧)
        値 = 総合値(評価)
        コーチ = 評価.get("コーチ")
        自己 = 評価.get("自己評価")
        差 = None if コーチ is None or 自己 is None else 自己 - コーチ
        結果.append(
            {
                "category_id": カテゴリ["id"],
                "name": カテゴリ["name"],
                "coach": コーチ,
                "self": 自己,
                "stats": 評価["スタッツ"],
                "value": 値,
                "level": レベル判定(値),
                "gap": 差,
                "gap_warning": 差 is not None and abs(差) >= 自己評価の差の警告値,
                "priority": None,
            }
        )
    診断済み = sorted((行 for 行 in 結果 if 行["value"] is not None), key=lambda 行: (行["value"], 行["category_id"]))
    for 順位, 行 in enumerate(診断済み[:優先項目の数], start=1):
        行["priority"] = 順位
    return 結果


def ドリルを段階順に並べる(ドリル一覧: Iterable[dict]) -> list[dict]:
    """1カテゴリ分のドリルを段階順（基礎→初級→中級→上級→プロ、各レベル内はステップ番号順）に並べる。

    次ステップIDが設定されていればそのつながりを優先し、つながっていないものはレベル・番号順で後ろに付ける。
    """
    ドリル = list(ドリル一覧)
    if not ドリル:
        return []
    基本順 = sorted(ドリル, key=lambda d: (レベル一覧.index(d["level"]), d["step_no"], d["id"]))
    ID対応 = {d["id"]: d for d in ドリル}
    参照される = {d["next_step_id"] for d in ドリル if d.get("next_step_id") in ID対応}
    並び: list[dict] = []
    済み: set[int] = set()
    for 先頭 in 基本順:
        if 先頭["id"] in 済み or 先頭["id"] in 参照される:
            continue
        現在 = 先頭
        while 現在 is not None and 現在["id"] not in 済み:
            並び.append(現在)
            済み.add(現在["id"])
            現在 = ID対応.get(現在.get("next_step_id"))
    for d in 基本順:  # 循環参照などで取り残されたもの
        if d["id"] not in 済み:
            並び.append(d)
            済み.add(d["id"])
    return 並び


def 現在のステップ(
    段階順ドリル: list[dict],
    進捗: dict[int, str],
    レベル: str,
    上書きドリルID: int | None = None,
) -> dict | None:
    """次に取り組むべきドリルを決める。

    - コーチの上書き指定があり、まだ完了していなければそれを優先
    - 診断レベルより下のレベルのドリルは飛ばす（未診断なら基礎から）
    - 完了済みを飛ばし、最初の未完了ドリルを返す。全部完了なら None
    """
    if 上書きドリルID is not None and 進捗.get(上書きドリルID) != "完了":
        for d in 段階順ドリル:
            if d["id"] == 上書きドリルID:
                return d
    開始レベル = レベル一覧.index(レベル) if レベル in レベル一覧 else 0
    for d in 段階順ドリル:
        if レベル一覧.index(d["level"]) < 開始レベル:
            continue
        if 進捗.get(d["id"]) != "完了":
            return d
    return None


def 次のドリル(段階順ドリル: list[dict], ドリルID: int) -> dict | None:
    for 位置, d in enumerate(段階順ドリル):
        if d["id"] == ドリルID:
            return 段階順ドリル[位置 + 1] if 位置 + 1 < len(段階順ドリル) else None
    return None
