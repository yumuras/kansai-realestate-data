# kansai-realestate-data

大阪市の中古マンションについて、「駅徒歩1分で㎡単価はいくら下がるか」を公開データで推定する分析です。

## 使うデータ

国土交通省の[不動産情報ライブラリ](https://www.reinfolib.mlit.go.jp/)の不動産価格情報（取引価格・成約価格）を使います。APIは無料ですが、サイトの「API利用申請」からAPIキーを申請する必要があります。

## モデル

```
log(㎡単価) = b0 + b1*駅徒歩分 + b2*築年数 + b3*log(面積) + 区ダミー + 取引年ダミー + e
```

`(exp(b1) - 1) × 100` が「徒歩1分あたり㎡単価が何%変わるか」です。標準誤差は区単位のクラスタ頑健標準誤差です。全体に加えて、都心6区（北・中央・西・天王寺・福島・浪速）とその他の区で分けた推定も出します。

## 手順

```bash
pip install -r requirements.txt
export REINFOLIB_API_KEY=xxxx        # キーはコミットしない

python -m src.fetch --from-year 2020 --to-year 2025   # data/raw/ にAPIレスポンスを保存
python -m src.prepare                                 # data/processed/osaka_city_condos.csv
python -m src.model                                   # outputs/ に係数表・区分別結果・図
```

APIの結果に駅徒歩分数が含まれていない場合は、不動産情報ライブラリの画面から大阪府のCSVをダウンロードして `data/raw/` に置けば、`src.prepare` がそのまま読み込みます（Shift_JIS）。

## 出力

| ファイル | 内容 |
| --- | --- |
| `outputs/regression_summary.txt` | 大阪市全体の回帰結果 |
| `outputs/walk_premium_by_group.csv` | 全体・都心6区・その他の区ごとの「徒歩1分あたり%」と95%信頼区間 |
| `outputs/median_by_walk.csv` / `.png` | 徒歩分数帯ごとの㎡単価中央値（記事の図用、補正なし） |

## 前処理のルール

- 種類が「中古マンション等」、市区町村が「大阪市〜」の取引のみ
- 駅徒歩「30分〜60分」は45分とみなし、1時間超は除外
- 建築年は和暦も西暦に変換し、「戦前」は除外
- 面積15〜200㎡に限定

## テスト

```bash
python -m pytest -q
```

合成データ（徒歩1分で-1.5%になるように作ったもの）で、前処理からモデルまで通して推定値が真の値を再現するかを確かめています。

## 注意

これは市場全体の傾向の分析で、個別物件の価格を評価するものではありません。
