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


# =========================
# 各店舗
# =========================

def get_cardrush(card_code: str, card_type: str) -> int | None:
    url = f"https://www.cardrush-db.jp/product-list?keyword={quote(card_code)}"
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    results = []

    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)

        if card_code not in text:
            continue
        if card_type == "parallel" and "パラレル" not in text:
            continue
        if card_type == "normal" and "パラレル" in text:
            continue
        if any(x in text for x in ["SEC", "SCR", "シークレット", "サイン", "PSA", "鑑定"]):
            continue

        # 在庫なし除外（ここが今回の修正）
        if any(x in text for x in ["×", "在庫なし", "売り切れ", "SOLD OUT"]):
            continue

        # 在庫ありだけに絞る
        if "在庫数" not in text:
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

        href = a["href"]
        full_url = urljoin("https://www.mercarddb.jp", href)

        try:
            detail_html = fetch_html(full_url)
            soup2 = BeautifulSoup(detail_html, "html.parser")
            tag = soup2.find("meta", {"property": "product:price:amount"})
            if tag and tag.get("content"):
                return int(tag["content"])
        except Exception:
            continue

    return None


def get_fullahead(card_code: str, card_type: str) -> int | None:
    url = f"https://www.fullahead-dbs.com/shop/shopbrand.html?search={quote(card_code)}"
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    items = soup.select(".indexItemBox > div")
    results = []

    for item in items:
        name = item.select_one(".itemName")
        price = item.select_one(".itemPrice strong")

        if not name or not price:
            continue

        text = name.get_text(" ", strip=True)
        if card_code not in text:
            continue

        is_parallel = "パラレル" in text
        if card_type == "parallel" and not is_parallel:
            continue
        if card_type == "normal" and is_parallel:
            continue

        try:
            p = int(price.get_text(strip=True).replace("円", "").replace(",", ""))
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


def get_mercari_lowest(card_code: str, card_type: str) -> int | None:
    keyword = card_code
    if card_type == "parallel":
        keyword += " パラレル"

    url = (
        "https://jp.mercari.com/search?"
        f"keyword={quote(keyword)}&sort=price&order=asc&status=on_sale"
    )

    try:
        html = fetch_html(url)
        prices = extract_yen_prices(html)
        valid = [p for p in prices if 1000 <= p <= 50000]
        return min(valid) if valid else None
    except Exception:
        return None


# =========================
# 画像
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

def adopted_price(cardrush, mercard, fullahead, cardlabo, mercari):
    shop_prices = [p for p in [cardrush, mercard, fullahead, cardlabo] if p is not None]
    shop_min = min(shop_prices) if shop_prices else None

    usable = list(shop_prices)

    if mercari is not None:
        if shop_min is None or mercari >= shop_min * 0.6:
            usable.append(mercari)

    return min(usable) if usable else None


# =========================
# UI
# =========================

st.set_page_config(page_title="DBFW価格検索", page_icon="💴", layout="centered")

st.title("DBFW 価格検索")

card_code = st.text_input("カード番号", value="FB09-005").strip().upper()
ui_type = st.selectbox("種類", ["パラレル", "ノーマル"], index=0)
card_type = "parallel" if ui_type == "パラレル" else "normal"

if st.button("検索"):
    result = {
        "カードラッシュ": get_cardrush(card_code, card_type),
        "メルカード": get_mercard(card_code, card_type),
        "フルアヘッド": get_fullahead(card_code, card_type),
        "カードラボ": get_cardlabo(card_code, card_type),
        "メルカリ最安値": get_mercari_lowest(card_code, card_type),
    }

    prices = [v for v in result.values() if v is not None]
    final_price = min(prices) if prices else None

    img_url = get_card_image(card_code, card_type)

    if img_url:
        st.image(img_url)

    for k, v in result.items():
        st.write(k, f"{v:,}円" if v else "なし")

    st.markdown("---")
    st.write("最安価格", f"{final_price:,}円" if final_price else "なし")