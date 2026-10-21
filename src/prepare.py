"""取得データを大阪市の中古マンションに絞り、分析用の1行1取引の表に整形する。

入力は次のどちらでもよい:
- data/raw/*.json  … src.fetch で取得したAPIレスポンス
- data/raw/*.csv   … 不動産情報ライブラリの画面からダウンロードしたCSV（Shift_JIS）

使い方:
    python -m src.prepare
出力: data/processed/osaka_city_condos.csv
"""

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_PATH = ROOT / "data" / "processed" / "osaka_city_condos.csv"

# APIの英語フィールド名と、ダウンロードCSVの日本語列名を共通の名前にそろえる
COLUMN_MAP = {
    "Type": "type",
    "種類": "type",
    "Municipality": "municipality",
    "市区町村名": "municipality",
    "DistrictName": "district",
    "地区名": "district",
    "TradePrice": "price",
    "取引価格（総額）": "price",
    "Area": "area",
    "面積（㎡）": "area",
    "BuildingYear": "building_year",
    "建築年": "building_year",
    "Period": "period",
    "取引時期": "period",
    "取引時点": "period",
    "TimeToNearestStation": "walk",
    "最寄駅：距離（分）": "walk",
    "NearestStation": "station",
    "最寄駅：名称": "station",
    "PriceCategory": "price_category",
    "価格情報区分": "price_category",
    "FloorPlan": "floor_plan",
    "間取り": "floor_plan",
}

CONDO_TYPES = {"中古マンション等"}

# 「都心6区」としてよく使われる区分
CENTRAL_WARDS = {"北区", "中央区", "西区", "天王寺区", "福島区", "浪速区"}

ERA_START = {"明治": 1868, "大正": 1912, "昭和": 1926, "平成": 1989, "令和": 2019}


def load_raw(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    frames = []
    for path in sorted(raw_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        frames.append(pd.DataFrame(payload.get("data", [])))
    for path in sorted(raw_dir.glob("*.csv")):
        frames.append(pd.read_csv(path, encoding="cp932", dtype=str))
    if not frames:
        raise SystemExit(f"{raw_dir} にデータがありません。先に src.fetch を実行するか、CSVを置いてください")
    df = pd.concat(frames, ignore_index=True)
    return df.rename(columns={k: v for k, v in COLUMN_MAP.items() if k in df.columns})


def parse_walk(value) -> float | None:
    """駅徒歩分数。'30分?60分' は中央の45分、'1H?1H30' など1時間超は除外する。"""
    if pd.isna(value):
        return None
    s = str(value).strip()
    if s.isdigit():
        return float(s)
    if s.startswith("30分"):
        return 45.0
    return None


def parse_building_year(value) -> int | None:
    """'2005年'、'平成17年'、'令和元年' を西暦にする。'戦前' などは除外する。"""
    if pd.isna(value):
        return None
    s = str(value).strip()
    m = re.fullmatch(r"(\d{4})年?", s)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"(明治|大正|昭和|平成|令和)(元|\d+)年", s)
    if m:
        n = 1 if m.group(2) == "元" else int(m.group(2))
        return ERA_START[m.group(1)] + n - 1
    return None


def parse_period(value) -> tuple[int, int] | tuple[None, None]:
    """'2024年第1四半期' → (2024, 1)。"""
    if pd.isna(value):
        return None, None
    m = re.search(r"(\d{4})年第(\d)四半期", str(value))
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def to_number(value) -> float | None:
    """'25000000' や '1,200' を数値にする。'2000㎡以上' のような範囲表記は除外する。"""
    if pd.isna(value):
        return None
    s = str(value).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    if "walk" not in df.columns:
        raise SystemExit(
            "駅徒歩分数の列がありません。APIの結果に含まれない場合は、"
            "不動産情報ライブラリの画面からCSVをダウンロードして data/raw に置いてください"
        )

    df = df[df["type"].isin(CONDO_TYPES)]
    df = df[df["municipality"].fillna("").str.startswith("大阪市")].copy()

    df["ward"] = df["municipality"].str.replace("大阪市", "", regex=False)
    df["price"] = df["price"].map(to_number)
    df["area"] = df["area"].map(to_number)
    df["walk_min"] = df["walk"].map(parse_walk)
    df["built"] = df["building_year"].map(parse_building_year)
    periods = df["period"].map(parse_period)
    df["trade_year"] = periods.map(lambda p: p[0])
    df["trade_quarter"] = periods.map(lambda p: p[1])

    df = df.dropna(subset=["price", "area", "walk_min", "built", "trade_year"])
    df = df[(df["area"] >= 15) & (df["area"] <= 200)]

    df["age"] = df["trade_year"] - df["built"]
    df = df[df["age"] >= 0]
    df["unit_price"] = df["price"] / df["area"]
    df["central"] = df["ward"].isin(CENTRAL_WARDS)

    cols = ["ward", "district", "station", "price_category", "floor_plan", "price", "area",
            "unit_price", "walk_min", "built", "age", "trade_year", "trade_quarter", "central"]
    return df[[c for c in cols if c in df.columns]].reset_index(drop=True)


def main() -> None:
    out = prepare(load_raw())
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"{len(out)}件 → {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
