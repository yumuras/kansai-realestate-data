"""駅徒歩1分あたりの㎡単価の下落率を重回帰（ヘドニック回帰）で推定する。

    log(㎡単価) = b0 + b1*駅徒歩分 + b2*築年数 + b3*log(面積) + 区ダミー + 取引年ダミー + e

b1 × 100 ≒ 「徒歩1分あたり何%変わるか」。

使い方:
    python -m src.model
出力: outputs/ に係数表・区分別の結果・図
"""

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parent.parent
IN_PATH = ROOT / "data" / "processed" / "osaka_city_condos.csv"
OUT_DIR = ROOT / "outputs"

FORMULA = "np.log(unit_price) ~ walk_min + age + np.log(area) + C(ward) + C(trade_year)"
FORMULA_NO_WARD = "np.log(unit_price) ~ walk_min + age + np.log(area) + C(trade_year)"


def fit(df: pd.DataFrame, formula: str = FORMULA):
    # 同じ区・同じ年の取引は誤差が相関しやすいので、区単位のクラスタ頑健標準誤差を使う
    return smf.ols(formula, data=df).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(df["ward"])[0]})


def pct_per_minute(result) -> dict:
    """徒歩1分あたりの㎡単価の変化率（%）と95%信頼区間。"""
    b = result.params["walk_min"]
    lo, hi = result.conf_int().loc["walk_min"]
    to_pct = lambda x: (np.exp(x) - 1) * 100
    return {"pct": to_pct(b), "ci_low": to_pct(lo), "ci_high": to_pct(hi), "n": int(result.nobs)}


def by_group(df: pd.DataFrame) -> pd.DataFrame:
    """全体・都心6区・それ以外で同じ回帰を回し、駅近プレミアムを比べる。"""
    rows = []
    for name, sub in [("大阪市全体", df), ("都心6区", df[df["central"]]), ("その他の区", df[~df["central"]])]:
        if sub["ward"].nunique() < 2:
            continue
        rows.append({"区分": name, **pct_per_minute(fit(sub))})
    return pd.DataFrame(rows)


def median_by_walk(df: pd.DataFrame) -> pd.DataFrame:
    """記事の図用：徒歩分数ごとの㎡単価の中央値（生データ、補正なし）。"""
    bins = [0, 3, 5, 7, 10, 15, 20, 60]
    labels = ["〜3分", "4〜5分", "6〜7分", "8〜10分", "11〜15分", "16〜20分", "21分〜"]
    cut = pd.cut(df["walk_min"], bins=bins, labels=labels, include_lowest=True)
    return (
        df.groupby(cut, observed=True)["unit_price"]
        .agg(["median", "count"])
        .rename(columns={"median": "㎡単価中央値（円）", "count": "件数"})
    )


def plot_median(table: pd.DataFrame, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(table.index.astype(str), table["㎡単価中央値（円）"] / 10_000, color="#4a7fb5")
    ax.set_ylabel("m2 unit price median (10k JPY)")
    ax.set_xlabel("walk to station")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    df = pd.read_csv(IN_PATH)
    OUT_DIR.mkdir(exist_ok=True)

    result = fit(df)
    (OUT_DIR / "regression_summary.txt").write_text(result.summary().as_text(), encoding="utf-8")

    groups = by_group(df)
    groups.to_csv(OUT_DIR / "walk_premium_by_group.csv", index=False)

    medians = median_by_walk(df)
    medians.to_csv(OUT_DIR / "median_by_walk.csv")
    plot_median(medians, OUT_DIR / "median_by_walk.png")

    main_row = pct_per_minute(result)
    print(f"件数: {main_row['n']}")
    print(f"駅徒歩1分あたり ㎡単価 {main_row['pct']:+.2f}%（95%CI {main_row['ci_low']:+.2f}〜{main_row['ci_high']:+.2f}%）")
    print(groups.to_string(index=False))


if __name__ == "__main__":
    main()
