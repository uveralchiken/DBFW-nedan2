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


# =========================
# カードラッシュ（修正版）
# =========================
def get_cardrush(card_no):
    site = "カードラッシュ"
    url = f"https://www.cardrush-db.jp/product-list?keyword={quote(card_no)}"

    try:
        text = fetch_text(url)

        # 在庫ありのみ取得
        pattern = re.compile(
            rf"([^\n]*{re.escape(card_no)}[^\n]*?([\d,]+円)[^\n]*在庫数\s*\d+\s*枚)",
            re.IGNORECASE
        )

        blocks = [normalize(m.group(1)) for m in pattern.finditer(text)]

        prices = []
        for b in blocks:
            price = parse_price(b)
            if price:
                prices.append(price)

        if prices:
            return result(site, True, min(prices), url)

        return result(site, False, None, url)

    except Exception:
        return result(site, None, None, url)


# =========================
# メルカード
# =========================
def get_mercard(card_no):
    site = "メルカード"
    url = f"https://www.mercarddb.jp/product-list?keyword={quote(card_no)}"

    try:
        text = fetch_text(url)
        prices = [parse_price(line) for line in text.split("\n") if card_no in line]
        prices = [p for p in prices if p]

        if prices:
            return result(site, True, min(prices), url)

        return result(site, False, None, url)

    except:
        return result(site, None, None, url)


# =========================
# カードラボ
# =========================
def get_clabo(card_no):
    site = "カードラボ"
    url = "https://www.c-labo-online.jp/product-list/2989"

    try:
        text = fetch_text(url)
        prices = [parse_price(line) for line in text.split("\n") if card_no in line]
        prices = [p for p in prices if p]

        if prices:
            return result(site, True, min(prices), url)

        return result(site, False, None, url)

    except:
        return result(site, None, None, url)


# =========================
# メルカリ
# =========================
def get_mercari(card_no):
    site = "メルカリ"
    url = f"https://jp.mercari.com/search?keyword={quote(card_no)}"

    try:
        text = fetch_text(url)
        prices = [parse_price(line.replace("¥", "") + "円") for line in text.split("\n") if "¥" in line]
        prices = [p for p in prices if p and 30 < p < 300000]

        if prices:
            return result(site, True, min(prices), url)

        return result(site, None, None, url)

    except:
        return result(site, None, None, url)


# =========================
# 採用価格
# =========================
def calc_adopted_price(results):
    prices = [r["price"] for r in results if r["available"] and r["price"]]
    return min(prices) if prices else None


# =========================
# UI
# =========================
def main():
    st.title("DBFW価格比較")

    card_no = st.text_input("カード番号", "FB05-025")

    if st.button("検索"):
        results = [
            get_cardrush(card_no),
            get_mercard(card_no),
            get_clabo(card_no),
            get_mercari(card_no),
        ]

        adopted = calc_adopted_price(results)

        if adopted:
            st.success(f"最安価格：¥{adopted:,}")
        else:
            st.error("価格取得失敗")

        for r in results:
            st.write(r)


if __name__ == "__main__":
    main()