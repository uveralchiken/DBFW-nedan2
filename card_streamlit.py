def get_cardrush(card_no: str, card_type: str):
    site = "カードラッシュ"
    url = f"https://www.cardrush-db.jp/product-list?keyword={quote(card_no)}"

    try:
        text = fetch_text(url)

        # 在庫あり（在庫数○枚）のみ取得する正規表現
        pattern = re.compile(
            rf"([^\n]*{re.escape(card_no)}[^\n]*?([\d,]+円)[^\n]*在庫数\s*\d+\s*枚)",
            re.IGNORECASE
        )

        blocks = [normalize(m.group(1)) for m in pattern.finditer(text)]

        # パラレル判定込みで価格抽出
        prices = []
        for b in blocks:
            if not type_match(b, card_type):
                continue

            price = parse_price(b)
            if price is not None:
                prices.append(price)

        if prices:
            return result(site, True, min(prices), url)

        # 在庫ありが1つも無い＝在庫なし
        return result(site, False, None, url)

    except Exception:
        return result(site, None, None, url)