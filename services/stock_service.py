def get_stock_price_history(stock_id, date):
    date_obj = datetime.strptime(date, "%Y%m%d")

    # 抓本月與上個月資料，確保有足夠資料計算 MA20
    months = [
        date_obj.strftime("%Y%m%d"),
        (date_obj.replace(day=1) - timedelta(days=1)).strftime("%Y%m%d")
    ]

    all_rows = []

    for m in months:
        try:
            r = requests.get(
                TWSE_STOCK_DAY,
                params={
                    "date": m,
                    "stockNo": stock_id,
                    "response": "json"
                },
                timeout=30
            )

            if r.status_code != 200:
                continue

            js = r.json()

            # TWSE 回傳失敗
            if js.get("stat") != "OK":
                continue

            data = js.get("data", [])

            if data:
                all_rows.extend(data)

        except Exception:
            continue

    rows = []

    for row in all_rows:
        try:
            roc_date = row[0]
            y, m, d = roc_date.split("/")
            western_date = f"{int(y)+1911}-{m}-{d}"

            close = parse_num(row[6])
            volume = int(parse_num(row[1]) // 1000)

            if close > 0:
                rows.append({
                    "date": western_date,
                    "close": close,
                    "volume": volume
                })

        except Exception:
            continue

    # ===== 這裡就是修正 KeyError('date') =====

    if len(rows) == 0:
        return pd.DataFrame(columns=["date", "close", "volume"])

    df = pd.DataFrame(rows)

    if "date" not in df.columns:
        return pd.DataFrame(columns=["date", "close", "volume"])

    df = (
        df
        .drop_duplicates(subset="date")
        .sort_values("date")
        .reset_index(drop=True)
    )

    return df
