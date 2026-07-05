# ══════════════════════════════════════════════════════════
# 寛容指数分析モジュール（研究計画書「四、研究方法」4.1・4.2節に対応）
# ══════════════════════════════════════════════════════════

# ── 形態素解析器（MeCab / fugashi）：利用可能な場合は使用する ─
try:
    import fugashi
    _tagger = fugashi.Tagger()
    def _tokenize(text: str) -> list[str]:
        return [w.surface for w in _tagger(text)]
    _MECAB_AVAILABLE = True
except Exception:
    _MECAB_AVAILABLE = False
    def _tokenize(text: str) -> list[str]:
        # MeCab が利用不可の場合は文字単位に分解してマッチング精度を維持する
        return list(text)

# ── デモデータ：HTML 未アップロード時のフォールバック ─────
DEMO_FUNCTIONAL = [
    {"text": "Joy-Conのドリフト現象が酷い。故障が多く不良品だと思います。動かない場面が増えてきた。", "star": 2},
    {"text": "画面は綺麗ですが、バッテリーの持ちが悪く使いにくい。遅いと感じる場面もある。", "star": 3},
    {"text": "初期不良でボタンが反応しない。エラーが頻発して使えなかった。交換対応してもらった。", "star": 2},
    {"text": "思ったより重い。うるさいし、デザインも薄いので壊れそう。品質に欠陥を感じる。", "star": 3},
    {"text": "普通に使えています。故障もなく、機能面では問題なし。値段相応かと思います。", "star": 4},
    {"text": "不具合なく動いている。ただバッテリーが遅く切れるのが少し不満。それ以外は満足。", "star": 4},
]

DEMO_EMOTIONAL = [
    {"text": "大好きなキャラのぬいぐるみ！可愛い！癒される！幸せな気持ちになれます。壊れやすいのが残念。", "star": 4},
    {"text": "最高すぎる！感動した！萌え萌えです。ふわふわで癒し効果抜群。少し破損していたが許せる。", "star": 4},
    {"text": "きゅんとしました。嬉しい！好き！ただ縫い目に欠陥があったのが少し残念でした。", "star": 4},
    {"text": "ほっこりする可愛さ。テンション上がる！感動！故障品だったが交換後は最高でした。", "star": 5},
    {"text": "かわいい！大好き！幸せ！不良品っぽい感じはあったけど愛着があるから全然いい。", "star": 4},
    {"text": "癒しの塊。萌えが止まらない。嬉しくて泣きそう。初期不良があったが満足しています。", "star": 5},
]

# ── 辞書：研究計画書 4.2節（3）に対応 ───────────────────────
# 欠陥語辞書：故障・動作不良・不良品等（MeCab 分かち書き後の表層形と照合）
DEFECT_DICT = [
    "壊れ", "故障", "傷", "不良品", "不具合", "エラー",
    "動かない", "動作不良", "初期不良", "遅い", "うるさい", "重い",
    "使いにくい", "臭い", "薄い", "破損", "欠陥",
    # 先導調査で実際に観察された、間接的な欠陥表現（研究計画書 4.2節(3)に対応）
    "折れ", "出来なかった", "できなかった", "づらい",
    "残念", "イマイチ", "微妙", "がっかり", "期待外れ",
]

# 感情語辞書：可愛い・癒される・好き等（MeCab 分かち書き後の表層形と照合）
EMOTION_DICT = [
    "可愛い", "かわいい", "癒される", "癒し", "好き", "大好き",
    "萌え", "ふわふわ", "嬉しい", "幸せ", "最高", "感動",
    "テンション上がる", "きゅん", "ほっこり",
]


def count_dict_hits(text: str, word_dict: list[str]) -> int:
    """
    研究計画書 4.2節（2）（3）に対応。
    MeCab（fugashi）で分かち書きしたトークン列に対して辞書語を照合し、
    ヒット数を返す。MeCab 未インストール時は文字列直接マッチングにフォールバック。
    """
    if _MECAB_AVAILABLE:
        tokens = _tokenize(text)
        return sum(tokens.count(w) for w in word_dict)
    else:
        return sum(text.count(w) for w in word_dict)


def calc_tolerance_index(text: str) -> dict:
    """
    研究計画書 4.1節の定義に対応。
    寛容指数 ＝ 感情語彙のヒット数 ／ 欠陥語彙のヒット数

    欠陥語ヒット数が 0 の場合（欠陥への言及なし）は None を返す。
    ゼロ除算を防ぐとともに、統計結果の誤解釈を防ぐための設計。
    """
    defect_hits = count_dict_hits(text, DEFECT_DICT)
    emotion_hits = count_dict_hits(text, EMOTION_DICT)

    if defect_hits == 0:
        tolerance_index = None
    else:
        tolerance_index = round(emotion_hits / defect_hits, 3)

    return {
        "text": text,
        "defect_hits": defect_hits,
        "emotion_hits": emotion_hits,
        "tolerance_index": tolerance_index,
    }


def analyze_group(reviews: list[dict]) -> dict:
    """
    研究計画書 4.2節（4）前半に対応。
    1グループ分のレビューについて寛容指数を一括算出し、グループ統計を返す。

    引数：
        reviews: {"text": str, "star": int} 形式のレビューリスト
    戻り値：
        per_review         : 各レビューの詳細結果リスト
        valid_count        : 欠陥言及があり指数算出可能なレビュー件数
        total_count        : グループのレビュー総数
        mean_tolerance_index: グループ内平均寛容指数（valid_count=0 の場合 None）
    """
    per_review = []
    valid_indices = []

    for r in reviews:
        result = calc_tolerance_index(r["text"])
        per_review.append(result)
        if result["tolerance_index"] is not None:
            valid_indices.append(result["tolerance_index"])

    mean_index = (
        round(sum(valid_indices) / len(valid_indices), 3)
        if valid_indices else None
    )

    return {
        "per_review": per_review,
        "valid_count": len(valid_indices),
        "total_count": len(reviews),
        "mean_tolerance_index": mean_index,
    }


def compare_groups(func_reviews: list[dict], emo_reviews: list[dict]) -> dict:
    """
    研究計画書 4.2節（4）後半に対応。
    「機能価値型商品グループ」と「感情価値型商品グループ」の
    平均寛容指数を比較し、差異を返す。
    """
    func_result = analyze_group(func_reviews)
    emo_result = analyze_group(emo_reviews)

    fi = func_result["mean_tolerance_index"]
    ei = emo_result["mean_tolerance_index"]

    return {
        "functional_group": func_result,
        "emotional_group": emo_result,
        "summary": {
            "functional_mean_tolerance_index": fi,
            "emotional_mean_tolerance_index": ei,
            "difference": round(ei - fi, 3) if (fi is not None and ei is not None) else None,
            "functional_valid_ratio": round(
                func_result["valid_count"] / func_result["total_count"], 3
            ) if func_result["total_count"] else None,
            "emotional_valid_ratio": round(
                emo_result["valid_count"] / emo_result["total_count"], 3
            ) if emo_result["total_count"] else None,
        },
    }


if __name__ == "__main__":
    result = compare_groups(DEMO_FUNCTIONAL, DEMO_EMOTIONAL)

    print(f"[MeCab 使用: {_MECAB_AVAILABLE}]")
    print("【機能性商品グループ】")
    print(f"  レビュー総数：{result['functional_group']['total_count']}")
    print(f"  欠陥言及ありのレビュー数：{result['functional_group']['valid_count']}")
    print(f"  平均寛容指数：{result['summary']['functional_mean_tolerance_index']}")
    print("【感情価値商品グループ】")
    print(f"  レビュー総数：{result['emotional_group']['total_count']}")
    print(f"  欠陥言及ありのレビュー数：{result['emotional_group']['valid_count']}")
    print(f"  平均寛容指数：{result['summary']['emotional_mean_tolerance_index']}")
    print(f"  差分（感情 − 機能）：{result['summary']['difference']}")
