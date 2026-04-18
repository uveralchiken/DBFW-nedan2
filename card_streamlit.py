import re
import requests
import streamlit as st
from bs4 import BeautifulSoup
from urllib.parse import quote

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}
TIMEOUT = 15

st.set_page_config(page_title="DBFW価格比較", layout="centered")


# =========================
# 共通
# =========================
def fetch_text(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser").get_text("\n", strip=True)


def normalize(text: str) -> str:
    text = text or ""
    text = text.replace("　", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compact(text: str) -> str:
    return re.sub(r"\s+", "", normalize(text)).lower()


def parse_price(text: str):
    m = re.search(r"([\d,]+)\s*円", text)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def result(site, available=None, price=None, url=None):
    if available is True and price is not None:
        status = "在庫あり"
    elif available is False:
        status = "在庫なし"
        price = None
    else:
        status = "取得失敗"
        price = None

    return {
        "site": site,
        "available": available is True,
        "price": price,
        "status": status,
        "url": url,
    }


def type_match(block: str, card_type: str) -> bool:
    t = compact(block)

    parallel_keywords = [
        "パラレル", "parallel",
        "l☆", "l★", "sr☆", "sr★", "r☆", "r★", "c☆", "c★", "uc☆", "uc★", "scr☆", "scr★",
        "パラレル版", "リーダーパラレル", "リーパラ"
    ]
    is_parallel = any(k in t for k in [x.lower() for x in parallel_keywords])

    if card_type == "パラレル":
        return is_parallel
    return not is_parallel


def detect_stock(block: str):
    t = compact(block)

    # 在庫なし
    ng_words = [
        "在庫なし",
        "残り在庫無し",
        "残り在庫なし",
        "売り切れ",
        "品切れ",
        "soldout",
        "sold out",
    ]
    if any(w.replace(" ", "") in t for w in ng_words):
        return False

    # カードラッシュ系の ×
    if "×" in block:
        return False

    # 在庫あり
    if re.search(r"在庫数\s*\d+\s*枚", block):
        return True
    if re.search(r"残り\s*\d+\s*点", block):
        return True
    if re.search(r"残りあと\s*\d+\s*個", block):
        return True
    if "カートに入れる" in block:
        return True

    return None


def pick_best(blocks, card_type):
    """
    在庫あり価格を優先。
    一致候補があって全部在庫なしなら在庫なしを返す。
    """
    prices = []
    found = False
    found_oos = False

    for b in blocks:
        if not type_match(b, card_type):
            continue

        found = True
        stock = detect_stock(b)
        price = parse_price(b)

        if stock is True and price is not None:
            prices.append(price)
        elif stock is False:
            found_oos = True

    if prices:
        return True, min(prices)

    if found and found_oos:
        return False, None

    if found:
        return None, None

    return None, None


# =========================
# サイト別抽出
# =========================
def get_cardrush(card_no: str, card_type: str):
    site = "カードラッシュ"
    url = f"https://www.cardrush-db.jp/product-list?keyword={quote(card_no)}"

    try:
        text = fetch_text(url)

        # 1件ずつ抜く
        # 例:
        # ベジット〖L〗{ FB05-025 } ... 80円 (税込) 在庫数 11枚
        # 〔状態B〕ベジット(パラレル)... 6,780円 (税込) ×
        pattern = re.compile(
            rf"([^\n]*{re.escape(card_no)}[^\n]*?[\d,]+円[^\n]*?(?:在庫数\s*\d+\s*枚|×|在庫なし|売り切れ)?)",
            re.IGNORECASE
        )
        blocks = [normalize(m.group(1)) for m in pattern.finditer(text)]

        stock, price = pick_best(blocks, card_type)
        return result(site, stock, price, url)

    except Exception:
        return result(site, None, None, url)


def get_mercard(card_no: str, card_type: str):
    site = "メルカード"
    url = f"https://www.mercarddb.jp/product-list?keyword={quote(card_no)}"

    try:
        text = fetch_text(url)

        # 一覧 / 詳細の両方を拾えるように残り○点系で抜く
        pattern = re.compile(
            rf"([^\n]*{re.escape(card_no)}[^\n]*?[\d,]+円[^\n]*?(?:残り\s*\d+\s*点|残り在庫無し|残り在庫なし|在庫なし)?)",
            re.IGNORECASE
        )
        blocks = [normalize(m.group(1)) for m in pattern.finditer(text)]

        stock, price = pick_best(blocks, card_type)
        return result(site, stock, price, url)

    except Exception:
        return result(site, None, None, url)


def get_clabo(card_no: str, card_type: str):
    site = "カードラボ"
    url = "https://www.c-labo-online.jp/product-list/2989"

    try:
        text = fetch_text(url)

        pattern = re.compile(
            rf"([^\n]*{re.escape(card_no)}[^\n]*?[\d,]+円[^\n]*?(?:在庫数\s*\d+\s*枚|在庫なし)?)",
            re.IGNORECASE
        )
        blocks = [normalize(m.group(1)) for m in pattern.finditer(text)]

        stock, price = pick_best(blocks, card_type)
        return result(site, stock, price, url)

    except Exception:
        return result(site, None, None, url)


def get_fullahead(card_no: str, card_type: str):
    site = "フルアヘッド"

    # FB05-025 -> セットコード fb05, 枝番 025
    m = re.match(r"FB(\d{2})-(\d{3})", card_no.upper())
    if not m:
        return result(site, None, None, None)

    set_no = m.group(1)
    serial = m.group(2)

    # フルアヘッドは型番でURLが変わるので、通常/パラレルを分ける
    # 通常: fw-fb05-025
    # パラレル: fw-fb05-125 のように +100 されることが多い
    if card_type == "パラレル":
        code_num = int(serial) + 100
    else:
        code_num = int(serial)

    code = f"{code_num:03d}"

    # 一覧より商品詳細の方が安定
    # ただし shopdetail ID は固定で分からないため、カテゴリページを読む
    if card_type == "パラレル":
        url = f"https://www.fullahead-dbs.com/shopbrand/fw-fb{set_no}/"
    else:
        url = f"https://www.fullahead-dbs.com/shopbrand/no-fw-fb{set_no}/"

    try:
        text = fetch_text(url)

        # 型番 fw-fb05-025 / fw-fb05-125 を含む行を優先して抜く
        model_code = f"fw-fb{set_no}-{code}".lower()

        lines = [normalize(x) for x in text.split("\n") if normalize(x)]
        blocks = []

        for i, line in enumerate(lines):
            joined = " ".join(lines[i:i+6])
            if model_code in compact(joined) or card_no.lower() in joined.lower():
                if "円" in joined:
                    blocks.append(joined)

        stock, price = pick_best(blocks, card_type)
        return result(site, stock, price, url)

    except Exception:
        return result(site, None, None, url)


def get_mercari(card_no: str, card_type: str):
    site = "メルカリ"
    url = f"https://jp.mercari.com/search?keyword={quote(card_no)}"

    try:
        text = fetch_text(url)

        # メルカリは「販売中のみ表示」が検索画面に出る
        # ただし出品まとめ売り混入があるので、カード番号を含む行だけ対象にする
        lines = [normalize(x) for x in text.split("\n") if normalize(x)]
        candidates = []

        for line in lines:
            if card_no.lower() not in line.lower():
                continue
            if card_type == "パラレル":
                if not any(k in compact(line) for k in ["パラレル", "l☆", "l★", "リーダーパラレル", "リーパラ"]):
                    continue
            price = parse_price(line.replace("¥", "") + "円" if "¥" in line and "円" not in line else line)
            if price is not None and 30 <= price <= 300000:
                candidates.append(price)

        if candidates:
            return result(site, True, min(candidates), url)

        return result(site, None, None, url)

    except Exception:
        return result(site, None, None, url)


# =========================
# 画像（カードラッシュ）
# =========================
def get_cardrush_image(card_no: str):
    url = f"https://www.cardrush-db.jp/product-list?keyword={quote(card_no)}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        for img in soup.select("img"):
            src = img.get("src", "")
            alt = img.get("alt", "")
            joined = f"{src} {alt}"
            if card_no.lower() in joined.lower() and "sold" not in joined.lower():
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    src = "https://www.cardrush-db.jp" + src
                if src.startswith("http"):
                    return src
    except:
        return None
    return None


# =========================
# 採用価格
# =========================
def calc_adopted_price(results):
    shop_prices = [
        r["price"]
        for r in results
        if r["site"] != "メルカリ" and r["available"] and r["price"] is not None
    ]

    mercari = next((r for r in results if r["site"] == "メルカリ"), None)

    adopted = min(shop_prices) if shop_prices else None

    if mercari and mercari["available"] and mercari["price"] is not None:
        mp = mercari["price"]
        if adopted is None:
            adopted = mp
        elif mp >= int(adopted * 0.7):
            adopted = min(adopted, mp)

    return adopted


# =========================
# UI
# =========================
def render_result(r, adopted_price=None):
    highlight = (
        adopted_price is not None
        and r["available"]
        and r["price"] == adopted_price
    )

    border = "2px solid #22c55e" if highlight else "1px solid #444"
    bg = "#0f172a" if highlight else "#111827"
    price_text = f"¥{r['price']:,}" if r["price"] is not None else "—"

    st.markdown(
        f"""
        <div style="border:{border}; background:{bg}; border-radius:12px; padding:14px; margin-bottom:10px;">
            <div style="font-size:18px; font-weight:700;">{r['site']}</div>
            <div style="margin-top:6px;">状態：{r['status']}</div>
            <div style="margin-top:6px; font-size:24px; font-weight:800;">価格：{price_text}</div>
            {f"<div style='margin-top:8px;'><a href='{r['url']}' target='_blank'>開く</a></div>" if r['url'] else ""}
        </div>
        """,
        unsafe_allow_html=True
    )


def main():
    st.title("DBFW 価格比較")

    card_no = st.text_input("カード番号", value="FB05-025").strip().upper()
    card_type = st.selectbox("種類", ["ノーマル", "パラレル"])

    if st.button("検索"):
        with st.spinner("取得中..."):
            image_url = get_cardrush_image(card_no)

            results = [
                get_cardrush(card_no, card_type),
                get_mercard(card_no, card_type),
                get_fullahead(card_no, card_type),
                get_clabo(card_no, card_type),
                get_mercari(card_no, card_type),
            ]
            adopted_price = calc_adopted_price(results)

        if image_url:
            st.image(image_url, width=260)

        st.subheader("採用価格")
        if adopted_price is not None:
            st.success(f"¥{adopted_price:,}")
        else:
            st.error("在庫ありの価格を取得できませんでした")

        st.subheader("各サイト")
        for r in results:
            render_result(r, adopted_price)

        with st.expander("デバッグ結果"):
            st.json(results)


if __name__ == "__main__":
    main()