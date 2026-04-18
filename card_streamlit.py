import re
import requests
import streamlit as st
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin

HEADERS = {"User-Agent": "Mozilla/5.0"}


# =========================
# 共通
# =========================

def fetch_html(url: str) -> str:
    res = requests.get(url, headers=HEADERS, timeout=20)
    res.raise_for_status()
    return res.text


def extract_yen_prices(text: str) -> list[int]:
    raw = re.findall(r'(\d[\d,]*)\s*円', text)
    prices = []

    for p in raw:
        try:
            num = int(p.replace(",", ""))
            if 300 <= num <= 300000:
                prices.append(num)
        except Exception:
            pass

    return sorted(set(prices))


def has_soldout_text(text: str) -> bool:
    ng_words = [
        "在庫なし",
        "売り切れ",
        "SOLD OUT",
        "品切れ",
        "×",
        "残り在庫無し",
        "販売終了",
    ]
    return any(word in text for word in ng_words)


# =========================
# 各店舗
# =========================

def get_cardrush(card_code: str, card_type: str) -> int | None:
    url = f"https://www.cardrush-db.jp/product-list?keyword={quote(card_code)}"

    try:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return None

    results = []

    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)

        if not text:
            continue
        if card_code not in text:
            continue
        if card_type == "parallel" and "パラレル" not in text:
            continue
        if card_type == "normal" and "パラレル" in text:
            continue
        if any(x in text for x in ["SEC", "SCR", "シークレット", "サイン", "PSA", "鑑定"]):
            continue
        if has_soldout_text(text):
            continue

        prices = extract_yen_prices(text)
        if not prices:
            continue

        price = min(prices)
        if price > 50000:
            continue

        results.append(price)

    return min(results) if results else None


def get_mercard(card_code: str, card_type: str) -> int | None:
    url = f"https://www.mercarddb.jp/product-list?keyword={quote(card_code)}"

    try:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return None

    results = []

    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)

        if not text:
            continue
        if card_code not in text:
            continue
        if card_type == "parallel" and "パラレル" not in text:
            continue
        if card_type == "normal" and "パラレル" in text:
            continue
        if any(x in text for x in ["SEC", "SCR", "シークレット", "サイン", "PSA", "鑑定"]):
            continue
        if has_soldout_text(text):
            continue

        href = a["href"]
        full_url = urljoin("https://www.mercarddb.jp", href)

        try:
            detail_html = fetch_html(full_url)
            soup2 = BeautifulSoup(detail_html, "html.parser")
            detail_text = soup2.get_text(" ", strip=True)

            if has_soldout_text(detail_text):
                continue

            tag = soup2.find("meta", {"property": "product:price:amount"})
            if tag and tag.get("content"):
                price = int(tag["content"])
                if 300 <= price <= 300000:
                    results.append(price)
                    continue

            prices = extract_yen_prices(detail_text)
            if prices:
                price = min(prices)
                if 300 <= price <= 300000:
                    results.append(price)

        except Exception:
            continue

    return min(results) if results else None


def get_fullahead(card_code: str, card_type: str) -> int | None:
    url = f"https://www.fullahead-dbs.com/shop/shopbrand.html?search={quote(card_code)}"

    try:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return None

    items = soup.select(".indexItemBox > div")
    results = []

    for item in items:
        name = item.select_one(".itemName")
        price = item.select_one(".itemPrice strong")
        link = item.find("a", href=True)

        if not name or not price:
            continue

        text = name.get_text(" ", strip=True)
        item_text = item.get_text(" ", strip=True)

        if card_code not in text:
            continue

        is_parallel = "パラレル" in text
        if card_type == "parallel" and not is_parallel:
            continue
        if card_type == "normal" and is_parallel:
            continue
        if has_soldout_text(item_text):
            continue

        if link and link.get("href"):
            detail_url = urljoin("https://www.fullahead-dbs.com", link["href"])
            try:
                detail_html = fetch_html(detail_url)
                detail_text = BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True)
                if has_soldout_text(detail_text):
                    continue
            except Exception:
                pass

        try:
            p = int(price.get_text(strip=True).replace("円", "").replace(",", ""))
            if 300 <= p <= 300000:
                results.append(p)
        except Exception:
            pass

    return min(results) if results else None


def get_cardlabo(card_code: str, card_type: str) -> int | None:
    code_upper = card_code.upper()
    prefix = code_upper.split("-")[0]

    cardlabo_category_map = {
        "FB09": "https://www.c-labo-online.jp/product-list/3330",
        "FB08": "https://www.c-labo-online.jp/product-list/3258",
        "FB07": "https://www.c-labo-online.jp/product-list/3183",
        "FB06": "https://www.c-labo-online.jp/product-list/3053",
        "FB05": "https://www.c-labo-online.jp/product-list/2989",
        "FB04": "https://www.c-labo-online.jp/product-list/2922/0/normal",
        "FB03": "https://www.c-labo-online.jp/product-list/2854/0/normal?available=1&num=120",
        "FB02": "https://www.c-labo-online.jp/product-list/2806",
        "FB01": "https://www.c-labo-online.jp/product-list/2685",
    }

    fw_root_url = "https://www.c-labo-online.jp/product-list/2684"

    if prefix in cardlabo_category_map:
        target_urls = [cardlabo_category_map[prefix]]
    elif prefix.startswith("FS") or prefix.startswith("FP") or prefix.startswith("SB"):
        target_urls = [fw_root_url]
    else:
        target_urls = [fw_root_url]

    results = []

    for url in target_urls:
        try:
            html = fetch_html(url)
        except Exception:
            continue

        soup = BeautifulSoup(html, "html.parser")

        for li in soup.find_all("li"):
            text = li.get_text(" ", strip=True)

            if code_upper not in text.upper():
                continue

            has_star = "★" in text
            if card_type == "parallel" and not has_star:
                continue
            if card_type == "normal" and has_star:
                continue

            if any(x in text for x in ["SCR", "SEC", "シークレット", "シリアル", "PSA", "鑑定"]):
                if prefix.startswith("FB") and "★" not in text:
                    pass
                else:
                    continue

            if has_soldout_text(text):
                continue

            detail_url = None
            a_tag = li.find("a", href=True)
            if a_tag and a_tag.get("href"):
                detail_url = urljoin("https://www.c-labo-online.jp", a_tag["href"])

            if detail_url:
                try:
                    detail_html = fetch_html(detail_url)
                    detail_text = BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True)

                    if has_soldout_text(detail_text):
                        continue
                except Exception:
                    continue

            m = re.search(r'(\d[\d,]*)\s*円', text)
            if not m:
                continue

            try:
                price = int(m.group(1).replace(",", ""))
            except ValueError:
                continue

            if 300 <= price <= 300000:
                results.append(price)

    return min(results) if results else None


# =========================
# 画像（カードラッシュのみ）
# =========================

def get_card_image(card_code: str, card_type: str) -> str | None:
    try:
        url = f"https://www.cardrush-db.jp/product-list?keyword={quote(card_code)}"
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        for a in soup.find_all("a", href=True):
            text = a.get_text(" ", strip=True)

            if card_code not in text:
                continue
            if card_type == "parallel" and "パラレル" not in text:
                continue
            if card_type == "normal" and "パラレル" in text:
                continue

            img = a.find("img")
            if img and img.get("src"):
                return urljoin("https://www.cardrush-db.jp", img["src"])
    except Exception:
        return None

    return None


# =========================
# 採用価格
# =========================

def adopted_price(cardrush, mercard, fullahead, cardlabo):
    shop_prices = [p for p in [cardrush, mercard, fullahead, cardlabo] if p is not None]
    return min(shop_prices) if shop_prices else None


# =========================
# 価格取得まとめ
# =========================

def search_card(card_code: str, card_type: str) -> dict:
    result = {
        "カードラッシュ": None,
        "メルカード": None,
        "フルアヘッド": None,
        "カードラボ": None,
        "採用価格": None,
    }

    try:
        result["カードラッシュ"] = get_cardrush(card_code, card_type)
    except Exception:
        pass

    try:
        result["メルカード"] = get_mercard(card_code, card_type)
    except Exception:
        pass

    try:
        result["フルアヘッド"] = get_fullahead(card_code, card_type)
    except Exception:
        pass

    try:
        result["カードラボ"] = get_cardlabo(card_code, card_type)
    except Exception:
        pass

    result["採用価格"] = adopted_price(
        result["カードラッシュ"],
        result["メルカード"],
        result["フルアヘッド"],
        result["カードラボ"],
    )

    return result


def format_price(value):
    if value is None:
        return "なし"
    return f"{value:,}円"


# =========================
# UI
# =========================

st.set_page_config(page_title="DBFW価格検索", page_icon="💴", layout="centered")

st.markdown("""
<style>
html, body, [class*="css"] {
    font-family: "Yu Gothic UI", sans-serif;
}
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 760px;
}
.big-title {
    font-size: 48px;
    font-weight: 800;
    margin-bottom: 8px;
    color: #1f2a44;
}
.sub-text {
    color: #6b7280;
    margin-bottom: 24px;
}
.price-card {
    padding: 16px 18px;
    border-radius: 16px;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    margin-bottom: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.shop-name {
    font-size: 18px;
    font-weight: 700;
    color: #1f2937;
}
.shop-price {
    font-size: 28px;
    font-weight: 800;
    color: #f06418;
    text-align: right;
}
.final-wrap {
    margin-top: 18px;
    padding: 18px;
    border-radius: 18px;
    background: #fff5f2;
    border: 2px solid #f28c52;
    text-align: center;
}
.final-label {
    font-size: 18px;
    color: #8b3d16;
    font-weight: 700;
}
.final-price {
    font-size: 42px;
    color: #e85d0c;
    font-weight: 900;
    margin-top: 8px;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">DBFW 価格検索</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">カード番号を入れて相場を確認</div>', unsafe_allow_html=True)

card_code = st.text_input("カード番号", value="FB09-005").strip().upper()
ui_type = st.selectbox("種類", ["パラレル", "ノーマル"], index=0)
card_type = "parallel" if ui_type == "パラレル" else "normal"

if st.button("検索", use_container_width=True):
    if not card_code:
        st.warning("カード番号を入力してください")
    else:
        with st.spinner("検索中..."):
            result = search_card(card_code, card_type)
            img_url = get_card_image(card_code, card_type)

        st.markdown("## 検索結果")

        if img_url:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(img_url, use_container_width=True)

        for shop_name in ["カードラッシュ", "メルカード", "フルアヘッド", "カードラボ"]:
            price_text = format_price(result[shop_name])

            st.markdown(
                f"""
                <div class="price-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div class="shop-name">{shop_name}</div>
                        <div class="shop-price">{price_text}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown(
            f"""
            <div class="final-wrap">
                <div class="final-label">採用価格</div>
                <div class="final-price">{format_price(result["採用価格"])}</div>
            </div>
            """,
            unsafe_allow_html=True
        )