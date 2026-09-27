"""スタッツの自動集計・シュートチャート・成長記録カレンダーの計算（DB に依存しない純粋関数）。"""

from __future__ import annotations

import calendar
import json

シュートエリア = (
    "ゴール下",
    "ペイント",
    "ミドル左",
    "ミドル正面",
    "ミドル右",
    "3P左コーナー",
    "3P左ウイング",
    "3Pトップ",
    "3P右ウイング",
    "3P右コーナー",
)
数値項目 = (
    "minutes",
    "points",
    "rebounds",
    "assists",
    "steals",
    "blocks",
    "turnovers",
    "fgm",
    "fga",
    "tpm",
    "tpa",
    "ftm",
    "fta",
)


def 成功率(成功: int, 試投: int) -> float | None:
    return round(成功 / 試投 * 100, 1) if 試投 else None


def エリア内訳を検証(内訳: dict | str | None) -> dict[str, dict[str, int]]:
    """{エリア名: {"a": 試投, "m": 成功}} を正規化する。未知のエリアや不正値はエラー。"""
    if not 内訳:
        return {}
    if isinstance(内訳, str):
        内訳 = json.loads(内訳)
    if not isinstance(内訳, dict):
        raise ValueError("シュートエリアの形式が不正です")
    結果 = {}
    for エリア, 値 in 内訳.items():
        if エリア not in シュートエリア:
            raise ValueError(f"不明なシュートエリアです: {エリア}")
        試投 = int(値.get("a", 0))
        成功 = int(値.get("m", 0))
        if 試投 < 0 or 成功 < 0 or 成功 > 試投:
            raise ValueError(f"{エリア} の成功数は 0 以上・試投数以下にしてください")
        if 試投:
            結果[エリア] = {"a": 試投, "m": 成功}
    return 結果


def スタッツを集計(スタッツ一覧: list[dict]) -> dict:
    """選手1人分のスタッツ（任意の順）から 合計・1試合平均・成功率・エリア別成功率・推移 を求める。"""
    試合数 = len(スタッツ一覧)
    合計 = {キー: sum(int(行.get(キー) or 0) for 行 in スタッツ一覧) for キー in 数値項目}
    平均 = {キー: round(合計[キー] / 試合数, 1) if 試合数 else 0 for キー in 数値項目}
    エリア合計 = {エリア: {"a": 0, "m": 0} for エリア in シュートエリア}
    for 行 in スタッツ一覧:
        for エリア, 値 in エリア内訳を検証(行.get("zones")).items():
            エリア合計[エリア]["a"] += 値["a"]
            エリア合計[エリア]["m"] += 値["m"]
    シュートチャート = [
        {"zone": エリア, "a": 値["a"], "m": 値["m"], "pct": 成功率(値["m"], 値["a"])}
        for エリア, 値 in エリア合計.items()
    ]
    推移 = [
        {
            "date": 行["date"],
            "label": 行.get("label", ""),
            "points": int(行.get("points") or 0),
            "rebounds": int(行.get("rebounds") or 0),
            "assists": int(行.get("assists") or 0),
            "fg_pct": 成功率(int(行.get("fgm") or 0), int(行.get("fga") or 0)),
        }
        for 行 in sorted(スタッツ一覧, key=lambda 行: (行["date"], 行.get("id", 0)))
    ]
    return {
        "games": 試合数,
        "totals": 合計,
        "averages": 平均,
        "fg_pct": 成功率(合計["fgm"], 合計["fga"]),
        "tp_pct": 成功率(合計["tpm"], 合計["tpa"]),
        "ft_pct": 成功率(合計["ftm"], 合計["fta"]),
        "shot_chart": シュートチャート,
        "trend": 推移,
    }


def 得点を検算(行: dict) -> int:
    """成功数から得点を計算する（2P×2 + 3P×3 + FT×1）。"""
    return (int(行.get("fgm") or 0) - int(行.get("tpm") or 0)) * 2 + int(行.get("tpm") or 0) * 3 + int(行.get("ftm") or 0)


def 成長記録カレンダー(年: int, 月: int, 出欠: list[dict], ステップ報告: list[dict], 自主練: list[dict]) -> dict:
    """月カレンダーの各日に 練習参加・ステップ報告・自主練 を集約し、活動量（0〜3）を付ける。"""
    日数 = calendar.monthrange(年, 月)[1]
    日付一覧 = [f"{年:04d}-{月:02d}-{日:02d}" for 日 in range(1, 日数 + 1)]
    日ごと = {日付: {"date": 日付, "attended": [], "steps": [], "self_practice": [], "level": 0} for 日付 in 日付一覧}
    for 行 in 出欠:
        if 行["date"] in 日ごと and 行["status"] in ("出席", "遅刻", "早退"):
            日ごと[行["date"]]["attended"].append({"title": 行["title"], "kind": 行["kind"], "status": 行["status"]})
    for 行 in ステップ報告:
        if 行["date"] in 日ごと:
            日ごと[行["date"]]["steps"].append({"title": 行["title"], "cleared": bool(行["cleared"])})
    for 行 in 自主練:
        if 行["date"] in 日ごと:
            日ごと[行["date"]]["self_practice"].append({"id": 行["id"], "minutes": 行["minutes"], "content": 行["content"]})
    活動日数 = 0
    for 日 in 日ごと.values():
        活動 = bool(日["attended"]) + bool(日["steps"]) + bool(日["self_practice"])
        日["level"] = 活動
        活動日数 += 活動 > 0
    連続 = 最長連続 = 0
    for 日付 in 日付一覧:
        連続 = 連続 + 1 if 日ごと[日付]["level"] else 0
        最長連続 = max(最長連続, 連続)
    return {
        "year": 年,
        "month": 月,
        "first_weekday": calendar.monthrange(年, 月)[0],  # 0=月曜
        "days": list(日ごと.values()),
        "active_days": 活動日数,
        "longest_streak": 最長連続,
        "self_practice_minutes": sum(int(行["minutes"] or 0) for 行 in 自主練 if 行["date"] in 日ごと),
    }
