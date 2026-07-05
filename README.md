# 商品レビュー言語特徴分析システム

商品レビューにおける「寛容指数」（感情語ヒット数 ÷ 欠陥語ヒット数）を算出するツールです。

## セットアップ

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 使い方

1. Amazon 等のレビューページを `Cmd+S` で「Webページ、HTML のみ」保存
2. 「機能性商品」用・「感情価値商品」用をそれぞれアップロード
3. 「分析を実行」で寛容指数を算出

HTML がなければ「デモデータを使用」で動作確認できます。

## 辞書について

東北大学 乾・岡崎研究室「日本語評価極性辞書」を使用しています。辞書本体は含まれていないため、[こちら](https://www.cl.ecei.tohoku.ac.jp/Open_Resources-Japanese_Sentiment_Polarity_Dictionary.html)から取得してください。
