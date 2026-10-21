"""実データなしで前処理とモデルが動くことを確かめるテスト（合成データを使う）。"""

import json

import numpy as np
import pandas as pd
import pytest

from src import model, prepare


@pytest.mark.parametrize(
    "value, expected",
    [("5", 5.0), ("30分～60分", 45.0), ("1H～1H30", None), (None, None)],
)
def test_parse_walk(value, expected):
    assert prepare.parse_walk(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [("2005年", 2005), ("平成17年", 2005), ("令和元年", 2019), ("昭和55年", 1980), ("戦前", None)],
)
def test_parse_building_year(value, expected):
    assert prepare.parse_building_year(value) == expected


def test_parse_period():
    assert prepare.parse_period("2024年第3四半期") == (2024, 3)


def make_fake_api_rows(n: int = 3000, true_pct: float = -1.5, seed: int = 0) -> list[dict]:
    """徒歩1分で㎡単価が true_pct % 変わるように作った合成データ。"""
    rng = np.random.default_rng(seed)
    wards = ["北区", "中央区", "西区", "天王寺区", "淀川区", "東淀川区", "平野区", "住吉区"]
    ward_level = dict(zip(wards, [0.5, 0.55, 0.45, 0.4, 0.1, 0.0, -0.2, -0.1]))
    b_walk = np.log(1 + true_pct / 100)
    rows = []
    for _ in range(n):
        ward = rng.choice(wards)
        walk = int(rng.integers(1, 25))
        built = int(rng.integers(1975, 2023))
        year = int(rng.integers(2020, 2025))
        area = float(rng.uniform(25, 100))
        log_up = 13.0 + ward_level[ward] + b_walk * walk - 0.015 * (year - built) + 0.05 * np.log(area)
        unit_price = np.exp(log_up + rng.normal(0, 0.15))
        rows.append({
            "PriceCategory": "成約価格情報",
            "Type": "中古マンション等",
            "Municipality": f"大阪市{ward}",
            "DistrictName": "テスト町",
            "TradePrice": str(int(unit_price * area)),
            "Area": str(round(area)),
            "BuildingYear": f"{built}年",
            "Period": f"{year}年第{int(rng.integers(1, 5))}四半期",
            "TimeToNearestStation": str(walk),
        })
    # 除外されるべき行
    rows.append({**rows[0], "Type": "宅地(土地)"})
    rows.append({**rows[0], "Municipality": "堺市北区"})
    return rows


def test_end_to_end_recovers_effect(tmp_path):
    (tmp_path / "fake.json").write_text(json.dumps({"data": make_fake_api_rows()}, ensure_ascii=False), encoding="utf-8")
    df = prepare.prepare(prepare.load_raw(tmp_path))

    assert set(df["ward"]) <= {"北区", "中央区", "西区", "天王寺区", "淀川区", "東淀川区", "平野区", "住吉区"}

    est = model.pct_per_minute(model.fit(df))
    assert est["ci_low"] < -1.5 < est["ci_high"]
    assert abs(est["pct"] - (-1.5)) < 0.3

    groups = model.by_group(df)
    assert list(groups["区分"]) == ["大阪市全体", "都心6区", "その他の区"]

    medians = model.median_by_walk(df)
    assert medians["件数"].sum() == len(df)
