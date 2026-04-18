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
    ng_words = ["在庫なし", "売り切れ", "SOLD OUT", "品切れ", "×", "残り在庫無し"]
    return any(word in text for word in ng_words)


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
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

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
        if has_soldout_text(text):
            continue

        stock_match = re.search(r'残り\s*(\d+)\s*点', text)
        if not stock_match:
            continue

        if int(stock_match.group(1)) <= 0:
            continue

        href = a["href"]
        full_url = urljoin("https://www.mercarddb.jp", href)

        try:
            detail_html = fetch_html(full_url)
            soup2 = BeautifulSoup(detail_html, "html.parser")

            if has_soldout_text(soup2.get_text(" ", strip=True)):
                continue

            tag = soup2.find("meta", {"property": "product:price:amount"})
            if tag and tag.get("content"):
                price = int(tag["content"])
                results.append(price)
        except Exception:
            continue

    return min(results) if results else None


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

        stock_match = re.search(r'残りあと\s*(\d+)\s*個', item_text)
        if not stock_match:
            continue

        if int(stock_match.group(1)) <= 0:
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

    urls = ["https://www.c-labo-online.jp/product-list/2684"]

    results = []

    for url in urls:
        try:
            html = fetch_html(url)
        except Exception:
            continue

        soup = BeautifulSoup(html, "html.parser")

        for li in soup.find_all("li"):
            text = li.get_text(" ", strip=True)

            if code_upper not in text.upper():
                continue

            if card_type == "parallel" and "★" not in text:
                continue
            if card_type == "normal" and "★" in text:
                continue
            if has_soldout_text(text):
                continue

            m = re.search(r'(\d[\d,]*)\s*円', text)
            if not m:
                continue

            try:
                price = int(m.group(1).replace(",", ""))
                results.append(price)
            except:
                pass

    return min(results) if results else None


# =========================
# UI
# =========================

st.set_page_config(page_title="DBFW価格検索", page_icon="💴", layout="centered")

st.markdown("## DBFW 価格検索")

card_code = st.text_input("カード番号", value="FB09-005").strip().upper()
ui_type = st.selectbox("種類", ["パラレル", "ノーマル"], index=0)
card_type = "parallel" if ui_type == "パラレル" else "normal"

if st.button("検索"):
    result = {
        "カードラッシュ": get_cardrush(card_code, card_type),
        "メルカード": get_mercard(card_code, card_type),
        "フルアヘッド": get_fullahead(card_code, card_type),
        "カードラボ": get_cardlabo(card_code, card_type),
    }

    prices = [v for v in result.values() if v is not None]
    final_price = min(prices) if prices else None

    for k, v in result.items():
        st.write(k, f"{v:,}円" if v else "なし")

    st.markdown("---")
    st.write("最安価格", f"{final_price:,}円" if final_price else "なし")