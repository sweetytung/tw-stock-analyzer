import requests
import pandas as pd
from datetime import datetime

def get_top20_volume(date=None):
    if date is None:
        date = datetime.now().strftime("%Y%m%d")
    else:
        date = date.replace("-", "")

    url = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
    params = {
        "date": date,
        "type": "ALLBUT0999",
        "response": "json"
    }

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    tables = data.get("tables", [])
    rows = []

    for table in tables:
        fields = table.get("fields", [])
        if "證券代號" in fields and "成交股數" in fields and "收盤價" in fields:
            rows = table.get("data", [])
            break

    result = []

    for row in rows:
        stock_id = row[0].strip()
        stock_name = row[1].strip()

        if not stock_id.isdigit() or len(stock_id) != 4:
            continue

        volume = int(row[2].replace(",", ""))
        close_text = row[8].replace(",", "").strip()

        if close_text == "--":
            continue

        result.append({
            "stock_id": stock_id,
            "stock_name": stock_name,
            "close": float(close_text),
            "volume": volume
        })

    result = sorted(result, key=lambda x: x["volume"], reverse=True)[:20]

    for i, item in enumerate(result, 1):
        item["rank"] = i

    return {
        "date": date,
        "count": len(result),
        "data": result
    }
