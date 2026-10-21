"""不動産情報ライブラリAPI（XIT001: 不動産価格情報）から大阪府の取引データを取得する。

使い方:
    export REINFOLIB_API_KEY=xxxx
    uv run python -m src.fetch --from-year 2020 --to-year 2025

出力: data/raw/osaka_pref_<year>Q<quarter>.json（APIのレスポンスをそのまま保存）
"""

import argparse
import json
import os
import time
from pathlib import Path

import requests

API_URL = "https://www.reinfolib.mlit.go.jp/ex-api/external/XIT001"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OSAKA_PREF_CODE = "27"


def fetch_quarter(api_key: str, year: int, quarter: int, area: str = OSAKA_PREF_CODE) -> dict:
    """1四半期分を取得する。取引価格・成約価格の両方を含む（priceClassification を指定しない）。"""
    resp = requests.get(
        API_URL,
        params={"year": year, "quarter": quarter, "area": area},
        headers={"Ocp-Apim-Subscription-Key": api_key},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-year", type=int, default=2020)
    parser.add_argument("--to-year", type=int, default=2025)
    parser.add_argument("--sleep", type=float, default=1.0, help="リクエスト間の待ち時間（秒）")
    args = parser.parse_args()

    api_key = os.environ.get("REINFOLIB_API_KEY")
    if not api_key:
        raise SystemExit("環境変数 REINFOLIB_API_KEY を設定してください（.env.example 参照）")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for year in range(args.from_year, args.to_year + 1):
        for quarter in range(1, 5):
            out = RAW_DIR / f"osaka_pref_{year}Q{quarter}.json"
            if out.exists():
                print(f"skip {out.name}（取得済み）")
                continue
            try:
                payload = fetch_quarter(api_key, year, quarter)
            except requests.HTTPError as e:
                # 未公表の四半期は404などが返るので、そこで打ち切らずに次へ進む
                print(f"{year}Q{quarter}: 取得できませんでした（{e}）")
                continue
            out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            print(f"{year}Q{quarter}: {len(payload.get('data', []))}件 → {out.name}")
            time.sleep(args.sleep)


if __name__ == "__main__":
    main()
