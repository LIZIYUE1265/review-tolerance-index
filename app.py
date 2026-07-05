"""
商品レビュー言語特徴分析システム — Streamlit インターフェース
研究課題：商品レビューにおける購買後評価の言語的特徴に関する研究
　　　　　——感情表現と欠陥表現の相対関係を手がかりに——
"""

import io
import re
import datetime

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import streamlit as st
from bs4 import BeautifulSoup

from kansei_research import (
    compare_groups,
    DEMO_FUNCTIONAL,
    DEMO_EMOTIONAL,
)


# ──────────────────────────────────────────────────────────
# デザイントークン（ダークテーマ固定）
# ──────────────────────────────────────────────────────────
COLOR_BG = "#161618"
COLOR_SURFACE = "#232326"
COLOR_BORDER = "#38383A"
COLOR_TEXT_PRIMARY = "#F5F5F7"
COLOR_TEXT_SECONDARY = "#98989D"
COLOR_ACCENT = "#0A84FF"       # プライマリアクション（Apple ダークモード系ブルー）
COLOR_ACCENT_TEXT = "#FFFFFF"
COLOR_FUNCTIONAL = "#7FA8C9"   # 機能性商品グループ（ダーク背景向けスレートブルー）
COLOR_EMOTIONAL = "#D9A0AC"    # 感情価値商品グループ（ダーク背景向けダスティローズ）


# ──────────────────────────────────────────────────────────
# 日本語フォント自動検出
# ──────────────────────────────────────────────────────────
def _jp_font() -> str:
    candidates = [
        "Hiragino Sans", "Hiragino Kaku Gothic Pro", "Hiragino Maru Gothic Pro",
        "MS Gothic", "Meiryo", "IPAexGothic", "Noto Sans CJK JP",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for c in candidates:
        if c in available:
            return c
    return "DejaVu Sans"


# ──────────────────────────────────────────────────────────
# ユーティリティ：アップロード HTML → レビューリスト
# ──────────────────────────────────────────────────────────
def parse_uploaded_html(uploaded_file) -> list[dict]:
    raw_bytes = uploaded_file.read()
    html = None
    for enc in ("utf-8", "utf-8-sig", "shift_jis", "euc-jp"):
        try:
            html = raw_bytes.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            pass
    if html is None:
        html = raw_bytes.decode("utf-8", errors="replace")

    soup = BeautifulSoup(html, "html.parser")
    reviews = []

    for container in soup.select('[data-hook="review"]'):
        body = container.select_one('[data-hook="review-body"]')
        if not body:
            continue
        text = body.get_text(" ", strip=True)
        text = re.sub(
            r"Brief content visible, double tap to read full content\.\s*"
            r"Full content visible, double tap to read brief content\.",
            "", text, flags=re.DOTALL)
        text = re.sub(r"続きを読む\s*表示を減らす|続きを読む|表示を減らす", "", text)
        text = re.sub(
            r"^.{0,60}星\d+つ中\d+(?:\.\d+)?.{0,100}\d{4}年\d+月\d+日に.{0,40}レビュー済み"
            r"(?:\s*色:.{0,40})?(?:\s*サイズ:.{0,40})?\s*Amazonで購入\s*",
            "", text, flags=re.DOTALL)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 15:
            continue

        star = 3
        for sel in ['[data-hook="review-star-rating"] .a-icon-alt',
                    '[data-hook="cmps-review-star-rating"] .a-icon-alt']:
            el = container.select_one(sel)
            if el:
                m = (re.search(r"のうち(\d+(?:\.\d+)?)", el.get_text()) or
                     re.search(r"(\d+(?:\.\d+)?)\s*out of", el.get_text()))
                if m:
                    star = min(5, max(1, round(float(m.group(1)))))
                break

        reviews.append({"text": text, "star": star})

    return reviews


# ──────────────────────────────────────────────────────────
# 可視化：寛容指数バーチャート
# ──────────────────────────────────────────────────────────
def plot_tolerance_chart(result: dict):
    font = _jp_font()
    plt.rcParams["font.family"] = font
    plt.rcParams["axes.edgecolor"] = COLOR_BORDER
    plt.rcParams["text.color"] = COLOR_TEXT_PRIMARY
    plt.rcParams["axes.labelcolor"] = COLOR_TEXT_SECONDARY

    fi = result["summary"]["functional_mean_tolerance_index"]
    ei = result["summary"]["emotional_mean_tolerance_index"]

    labels = ["機能性商品", "感情価値商品"]
    values = [fi if fi is not None else 0, ei if ei is not None else 0]
    colors = [COLOR_FUNCTIONAL, COLOR_EMOTIONAL]

    fig, ax = plt.subplots(figsize=(6, 3.6))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)
    bars = ax.bar(labels, values, color=colors, width=0.45)
    ax.set_ylabel("平均寛容指数（感情語数 ÷ 欠陥語数）", fontsize=10, color=COLOR_TEXT_SECONDARY)
    ax.set_title("グループ別 平均寛容指数", fontsize=13, fontweight="medium",
                 color=COLOR_TEXT_PRIMARY, loc="left", pad=14)
    ax.set_ylim(0, max(values) * 1.4 + 0.1)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLOR_BORDER)
    ax.spines["bottom"].set_color(COLOR_BORDER)
    ax.tick_params(colors=COLOR_TEXT_SECONDARY)
    for bar, val, orig in zip(bars, values, [fi, ei]):
        label = f"{val:.3f}" if orig is not None else "算出不可"
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.02,
                label, ha="center", va="bottom", fontsize=11,
                color=COLOR_TEXT_PRIMARY)
    fig.tight_layout()
    return fig


# ──────────────────────────────────────────────────────────
# Excel エクスポート
# ──────────────────────────────────────────────────────────
def export_excel(func_reviews: list[dict], emo_reviews: list[dict], result: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        func_rows = []
        for i, r in enumerate(result["functional_group"]["per_review"], 1):
            func_rows.append({
                "No.": i,
                "レビュー本文（抜粋）": r["text"][:120] + "…",
                "欠陥語ヒット数": r["defect_hits"],
                "感情語ヒット数": r["emotion_hits"],
                "寛容指数": r["tolerance_index"] if r["tolerance_index"] is not None else "算出不可",
            })
        pd.DataFrame(func_rows).to_excel(writer, sheet_name="機能性商品_寛容指数", index=False)

        emo_rows = []
        for i, r in enumerate(result["emotional_group"]["per_review"], 1):
            emo_rows.append({
                "No.": i,
                "レビュー本文（抜粋）": r["text"][:120] + "…",
                "欠陥語ヒット数": r["defect_hits"],
                "感情語ヒット数": r["emotion_hits"],
                "寛容指数": r["tolerance_index"] if r["tolerance_index"] is not None else "算出不可",
            })
        pd.DataFrame(emo_rows).to_excel(writer, sheet_name="感情価値商品_寛容指数", index=False)

        s = result["summary"]
        fg = result["functional_group"]
        eg = result["emotional_group"]
        fi = s["functional_mean_tolerance_index"]
        ei = s["emotional_mean_tolerance_index"]
        summary_rows = [
            {
                "指標": "レビュー総数",
                "機能性商品グループ": fg["total_count"],
                "感情価値商品グループ": eg["total_count"],
            },
            {
                "指標": "欠陥言及あり件数",
                "機能性商品グループ": fg["valid_count"],
                "感情価値商品グループ": eg["valid_count"],
            },
            {
                "指標": "欠陥言及率",
                "機能性商品グループ": s["functional_valid_ratio"],
                "感情価値商品グループ": s["emotional_valid_ratio"],
            },
            {
                "指標": "平均寛容指数",
                "機能性商品グループ": fi,
                "感情価値商品グループ": ei,
            },
        ]
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="グループ比較サマリー", index=False)

    return buf.getvalue()


# ──────────────────────────────────────────────────────────
# ページ設定
# ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="商品レビュー言語特徴分析",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
    html, body, [class*="css"] {{
        font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
                     "Hiragino Kaku Gothic ProN", "Yu Gothic", "Noto Sans CJK JP",
                     sans-serif !important;
    }}

    /* ── ベース：常にライトトーンを強制し、環境のダークテーマに左右されない ── */
    .stApp {{
        background-color: {COLOR_BG} !important;
    }}
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
        background-color: {COLOR_BG} !important;
    }}

    /* ── 中央寄せ・余白を大きく取ったコンテナ ── */
    .block-container {{
        max-width: 900px;
        padding-top: 4rem;
        padding-bottom: 5rem;
        margin: 0 auto;
    }}

    h1 {{
        color: {COLOR_TEXT_PRIMARY} !important;
        font-weight: 600 !important;
        font-size: 2.6rem !important;
        letter-spacing: -0.02em;
        margin-bottom: 0.3rem;
    }}
    h2, h3 {{
        color: {COLOR_TEXT_PRIMARY} !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em;
        margin-top: 2.2rem;
    }}
    p, li, label, .stMarkdown, span {{
        color: {COLOR_TEXT_PRIMARY};
        line-height: 1.7;
    }}
    [data-testid="stCaptionContainer"] {{
        color: {COLOR_TEXT_SECONDARY} !important;
    }}

    /* ── サイドバー ── */
    [data-testid="stSidebar"] {{
        background-color: {COLOR_SURFACE} !important;
        border-right: 1px solid {COLOR_BORDER};
    }}
    [data-testid="stSidebar"] * {{
        color: {COLOR_TEXT_PRIMARY} !important;
    }}

    /* ── メトリクスカード ── */
    div[data-testid="stMetric"] {{
        background-color: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: 16px;
        padding: 28px 26px;
    }}
    [data-testid="stMetricLabel"] {{
        color: {COLOR_TEXT_SECONDARY} !important;
        font-weight: 400 !important;
        font-size: 0.85rem !important;
        margin-bottom: 6px;
    }}
    [data-testid="stMetricValue"] {{
        color: {COLOR_TEXT_PRIMARY} !important;
        font-size: 1.9rem !important;
    }}
    div[data-testid="stHorizontalBlock"] {{
        gap: 16px;
    }}

    /* ── ボタン：ピル形、色を明示指定してテーマ依存のコントラスト事故を防ぐ ── */
    .stButton > button, .stDownloadButton > button {{
        border-radius: 999px !important;
        border: 1px solid {COLOR_BORDER} !important;
        background-color: {COLOR_SURFACE} !important;
        color: {COLOR_TEXT_PRIMARY} !important;
        font-weight: 500 !important;
        padding: 0.6rem 1.6rem !important;
        transition: opacity 0.15s ease;
        opacity: 1;
    }}
    .stButton > button:hover, .stDownloadButton > button:hover {{
        opacity: 0.7;
        background-color: {COLOR_SURFACE} !important;
        border-color: {COLOR_BORDER} !important;
        color: {COLOR_TEXT_PRIMARY} !important;
    }}
    .stButton > button p, .stDownloadButton > button p,
    .stButton > button span, .stDownloadButton > button span,
    .stButton > button div, .stDownloadButton > button div {{
        color: inherit !important;
        background-color: transparent !important;
    }}
    .stButton > button[kind="primary"] {{
        background-color: {COLOR_ACCENT} !important;
        border: none !important;
        color: {COLOR_ACCENT_TEXT} !important;
    }}
    .stButton > button[kind="primary"]:hover {{
        opacity: 0.7;
        background-color: {COLOR_ACCENT} !important;
        color: {COLOR_ACCENT_TEXT} !important;
    }}
    .stButton > button[kind="primary"] p,
    .stButton > button[kind="primary"] span,
    .stButton > button[kind="primary"] div {{
        color: {COLOR_ACCENT_TEXT} !important;
        background-color: transparent !important;
    }}
    .stButton > button:disabled, .stButton > button:disabled p {{
        color: #55555A !important;
        background-color: {COLOR_SURFACE} !important;
        border-color: {COLOR_BORDER} !important;
        opacity: 1 !important;
    }}
    .stButton > button:disabled:hover {{
        opacity: 1 !important;
    }}

    /* ── Streamlit 純正ツールバー（明暗切替・Deploy 等）を非表示にする ── */
    [data-testid="stToolbar"] {{
        visibility: hidden;
        height: 0;
    }}
    [data-testid="stDecoration"] {{
        display: none;
    }}
    #MainMenu {{
        visibility: hidden;
    }}
    footer {{
        visibility: hidden;
    }}

    /* ── タブ：控えめなアクセントに統一 ── */
    div[data-baseweb="tab-list"] {{
        gap: 8px;
        border-bottom: 1px solid {COLOR_BORDER};
    }}
    button[data-baseweb="tab"] {{
        color: {COLOR_TEXT_SECONDARY} !important;
        font-weight: 500;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {COLOR_TEXT_PRIMARY} !important;
    }}
    div[data-baseweb="tab-highlight"] {{
        background-color: {COLOR_TEXT_PRIMARY} !important;
    }}

    hr {{
        border-color: {COLOR_BORDER} !important;
        margin: 2rem 0 !important;
    }}

    .stDataFrame {{
        border: 1px solid {COLOR_BORDER};
        border-radius: 12px;
    }}

    [data-testid="stFileUploaderDropzone"] {{
        background-color: {COLOR_SURFACE} !important;
        border: 1px dashed {COLOR_BORDER} !important;
        border-radius: 14px;
        padding: 8px;
    }}
    [data-testid="stFileUploaderDropzone"] * {{
        color: {COLOR_TEXT_SECONDARY} !important;
    }}
    [data-testid="stFileUploaderDropzone"] button {{
        border-radius: 999px !important;
        background-color: {COLOR_TEXT_PRIMARY} !important;
        color: {COLOR_SURFACE} !important;
        border: none !important;
        padding: 0.55rem 1.4rem !important;
        font-weight: 500 !important;
    }}
    [data-testid="stFileUploaderDropzone"] button p {{
        color: {COLOR_SURFACE} !important;
        font-weight: 500 !important;
    }}
    [data-testid="stFileUploaderDropzone"] small {{
        color: {COLOR_TEXT_SECONDARY} !important;
        opacity: 0.8;
    }}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 研究概要")
    st.divider()
    st.markdown(
        "**研究目的**\n\n"
        "消費者が購買の意思決定を完了した後、レビュー本文において"
        "自らの決定を言語的に再解釈し、自己正当化する傾向を示すかを観察する。\n\n"
        "本システムの分析対象は「寛容指数」という数値そのものではなく、"
        "その背後にある購買後の言語調整行動である。寛容指数は、"
        "この行動を観測するために設計した操作的指標に過ぎない。"
    )
    st.divider()
    st.markdown(
        "<span style='color:#6E6E73; font-size:13px;'>"
        "機能性商品と感情価値商品は購買動機が異なる商品群として、"
        "指標が実際に機能するかを検証するために用いている。"
        "</span>",
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown(
        "<span style='color:#6E6E73; font-size:13px;'>"
        "寛容指数 ＝ 感情語ヒット数 ／ 欠陥語ヒット数"
        "</span>",
        unsafe_allow_html=True,
    )

st.title("商品レビュー言語特徴分析")
st.caption("寛容指数：購買後の自己正当化を観測するための言語指標")

for _k, _v in [("func_reviews", []), ("emo_reviews", []), ("result", None)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

tab1, tab2, tab3 = st.tabs(["データ入力", "分析結果", "レポート出力"])


# ══════════════════════════════════════════════════════════
# Tab 1 — データ入力
# ══════════════════════════════════════════════════════════
with tab1:
    st.subheader("レビューデータの入力")
    st.markdown(
        "<span style='color:#6E6E73;'>手順：ブラウザで Amazon 等の EC サイトにログインし、"
        "レビューページを Cmd+S（Mac）→「Webページ、HTML のみ」で保存。"
        "機能性商品用・感情価値商品用をそれぞれ保存してアップロードしてください。</span>",
        unsafe_allow_html=True,
    )

    st.write("")
    col_func, col_emo = st.columns(2)

    with col_func:
        st.markdown("**機能性商品**")
        st.caption("例：ゲーム機、家電、PC 周辺機器など")
        func_file = st.file_uploader("functional.html をアップロード",
                                     type=["html", "htm"], key="func_upload",
                                     label_visibility="collapsed")
        if func_file is not None:
            parsed = parse_uploaded_html(func_file)
            st.session_state.func_reviews = parsed
            st.caption(f"{len(parsed)} 件のレビューを取得しました。")
            if parsed:
                with st.expander("プレビュー（先頭 3 件）"):
                    for r in parsed[:3]:
                        st.markdown(f"★{r['star']}　{r['text'][:100]}…")

    with col_emo:
        st.markdown("**感情価値商品**")
        st.caption("例：キャラクターグッズ、限定版、ぬいぐるみなど")
        emo_file = st.file_uploader("emotional.html をアップロード",
                                    type=["html", "htm"], key="emo_upload",
                                    label_visibility="collapsed")
        if emo_file is not None:
            parsed = parse_uploaded_html(emo_file)
            st.session_state.emo_reviews = parsed
            st.caption(f"{len(parsed)} 件のレビューを取得しました。")
            if parsed:
                with st.expander("プレビュー（先頭 3 件）"):
                    for r in parsed[:3]:
                        st.markdown(f"★{r['star']}　{r['text'][:100]}…")

    st.divider()
    col_demo, col_run = st.columns(2)

    with col_demo:
        if st.button("デモデータを使用", use_container_width=True):
            st.session_state.func_reviews = list(DEMO_FUNCTIONAL)
            st.session_state.emo_reviews  = list(DEMO_EMOTIONAL)
            st.caption(f"デモデータを設定しました（機能性 {len(DEMO_FUNCTIONAL)} 件／感情価値 {len(DEMO_EMOTIONAL)} 件）")

    with col_run:
        can_run = (len(st.session_state.func_reviews) > 0
                   and len(st.session_state.emo_reviews) > 0)
        if st.button("分析を実行", type="primary",
                     disabled=not can_run, use_container_width=True):
            with st.spinner("寛容指数を算出しています…"):
                result = compare_groups(
                    st.session_state.func_reviews,
                    st.session_state.emo_reviews,
                )
                st.session_state.result = result
            st.caption("分析が完了しました。「分析結果」タブをご確認ください。")

    if not can_run:
        st.caption("HTML をアップロードするか、デモデータを設定してから実行してください。")


# ══════════════════════════════════════════════════════════
# Tab 2 — 分析結果
# ══════════════════════════════════════════════════════════
with tab2:
    if st.session_state.result is None:
        st.markdown(
            "<span style='color:#6E6E73;'>「データ入力」タブで分析を実行してください。</span>",
            unsafe_allow_html=True,
        )
    else:
        result       = st.session_state.result
        func_reviews = st.session_state.func_reviews
        emo_reviews  = st.session_state.emo_reviews
        s            = result["summary"]
        fg           = result["functional_group"]
        eg           = result["emotional_group"]
        fi           = s["functional_mean_tolerance_index"]
        ei           = s["emotional_mean_tolerance_index"]

        st.subheader("概要")
        k1, k2, k3, k4 = st.columns(4)
        func_avg = round(sum(r["star"] for r in func_reviews) / max(len(func_reviews), 1), 1)
        emo_avg  = round(sum(r["star"] for r in emo_reviews)  / max(len(emo_reviews),  1), 1)
        k1.metric("機能性・平均星評価", f"{func_avg}")
        k2.metric("感情価値・平均星評価", f"{emo_avg}")
        k3.metric("機能性・平均寛容指数", f"{fi:.3f}" if fi is not None else "算出不可")
        try:
            delta = f"{round(ei - fi, 3):+}" if ei is not None and fi is not None else None
        except TypeError:
            delta = None
        k4.metric("感情価値・平均寛容指数", f"{ei:.3f}" if ei is not None else "算出不可", delta=delta)

        st.divider()

        st.subheader("グループ別 平均寛容指数")
        st.pyplot(plot_tolerance_chart(result), use_container_width=True)
        st.caption(
            "寛容指数 ＝ 感情語ヒット数 ÷ 欠陥語ヒット数。"
            "値が大きいほど、欠陥への言及が感情表現によって強く相対化されていることを示す。"
        )

        st.divider()

        st.subheader("グループ統計")
        compare_df = pd.DataFrame([
            {
                "グループ":         "機能性商品",
                "レビュー総数":     fg["total_count"],
                "欠陥言及あり件数": fg["valid_count"],
                "欠陥言及率":       f"{s['functional_valid_ratio']:.1%}" if s['functional_valid_ratio'] else "—",
                "平均寛容指数":     f"{fi:.3f}" if fi is not None else "算出不可",
            },
            {
                "グループ":         "感情価値商品",
                "レビュー総数":     eg["total_count"],
                "欠陥言及あり件数": eg["valid_count"],
                "欠陥言及率":       f"{s['emotional_valid_ratio']:.1%}" if s['emotional_valid_ratio'] else "—",
                "平均寛容指数":     f"{ei:.3f}" if ei is not None else "算出不可",
            },
        ])
        st.dataframe(compare_df, use_container_width=True, hide_index=True)

        st.divider()

        col_f, col_e = st.columns(2)
        with col_f:
            st.markdown("**機能性商品グループ — 寛容指数詳細**")
            rows = []
            for i, r in enumerate(fg["per_review"], 1):
                rows.append({
                    "No.": i,
                    "欠陥語": r["defect_hits"],
                    "感情語": r["emotion_hits"],
                    "寛容指数": f"{r['tolerance_index']:.3f}" if r["tolerance_index"] is not None else "算出不可",
                    "本文（抜粋）": r["text"][:60] + "…",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with col_e:
            st.markdown("**感情価値商品グループ — 寛容指数詳細**")
            rows = []
            for i, r in enumerate(eg["per_review"], 1):
                rows.append({
                    "No.": i,
                    "欠陥語": r["defect_hits"],
                    "感情語": r["emotion_hits"],
                    "寛容指数": f"{r['tolerance_index']:.3f}" if r["tolerance_index"] is not None else "算出不可",
                    "本文（抜粋）": r["text"][:60] + "…",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════
# Tab 3 — レポート出力
# ══════════════════════════════════════════════════════════
with tab3:
    if st.session_state.result is None:
        st.markdown(
            "<span style='color:#6E6E73;'>「データ入力」タブで分析を実行してください。</span>",
            unsafe_allow_html=True,
        )
    else:
        result       = st.session_state.result
        func_reviews = st.session_state.func_reviews
        emo_reviews  = st.session_state.emo_reviews
        today_str    = datetime.date.today().strftime("%Y%m%d")

        st.subheader("研究レポートの出力")
        col_xl, col_img = st.columns(2)

        with col_xl:
            st.markdown("**Excel 研究報告書（3 シート）**")
            st.caption(
                "Sheet1：機能性商品_寛容指数\n\n"
                "Sheet2：感情価値商品_寛容指数\n\n"
                "Sheet3：グループ比較サマリー"
            )
            if st.button("Excel を生成", use_container_width=True):
                with st.spinner("生成中…"):
                    excel_bytes = export_excel(func_reviews, emo_reviews, result)
                st.download_button(
                    label="Excel をダウンロード",
                    data=excel_bytes,
                    file_name=f"kansei_research_{today_str}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

        with col_img:
            st.markdown("**寛容指数比較グラフ（PNG）**")
            st.caption("300 dpi。研究計画書・論文への挿入に対応。")
            if st.button("PNG を生成", use_container_width=True):
                with st.spinner("生成中…"):
                    fig = plot_tolerance_chart(result)
                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", dpi=300,
                                bbox_inches="tight", facecolor="white")
                    buf.seek(0)
                st.download_button(
                    label="PNG をダウンロード",
                    data=buf.getvalue(),
                    file_name=f"tolerance_index_{today_str}.png",
                    mime="image/png",
                    use_container_width=True,
                )

        st.divider()
        st.caption(
            "本システムで処理する EC レビューデータは、研究目的のみに使用してください。"
        )
