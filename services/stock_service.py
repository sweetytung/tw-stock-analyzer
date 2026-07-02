import requests
import pandas as pd
from datetime import datetime, timedelta

TWSE_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"


def finmind(dataset, start_date, end_date, stock_id):
    params = {
        "dataset": dataset,
        "data_id": stock_id,
        "start_date": start_date,
        "end_date": end_date,
    }
    r = requests.get(FINMIND_URL, params=params, timeout=30)
    r.raise_for_status()
    return pd.DataFrame(r.json().get("data", []))


def get_top20_volume(date=None):
    if date is None:
        date = datetime.now().strftime("%Y%m%d")
    else:
        date = date.replace("-", "")

    r = requests.get(TWSE_URL, params={
        "date": date,
        "type": "ALLBUT0999",
        "response": "json"
    }, timeout=30)
    r.raise_for_status()

    tables = r.json().get("tables", [])
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

        close_text = row[8].replace(",", "").strip()
        if close_text == "--":
            continue

        volume_shares = int(row[2].replace(",", ""))
        volume_lots = volume_shares // 1000

        result.append({
            "stock_id": stock_id,
            "stock_name": stock_name,
            "close": float(close_text),
            "volume": volume_lots
        })

    result = sorted(result, key=lambda x: x["volume"], reverse=True)[:20]

    for i, item in enumerate(result, 1):
        item["rank"] = i

    return {
        "date": date,
        "count": len(result),
        "data": result
    }


def get_stock_detail(stock_id, stock_name, date):
    end_date = date.replace("/", "-")
    start_date = (
        datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=45)
    ).strftime("%Y-%m-%d")

    price = finmind("TaiwanStockPrice", start_date, end_date, stock_id)

    if price.empty:
        return {
            "stock_id": stock_id,
            "stock_name": stock_name,
            "history": [],
            "ma": {},
            "signal": "查無股價資料"
        }

    price = price.sort_values("date")
    price["close"] = pd.to_numeric(price["close"], errors="coerce")
    price["Trading_Volume"] = pd.to_numeric(price["Trading_Volume"], errors="coerce")

    price["MA5"] = price["close"].rolling(5).mean()
    price["MA10"] = price["close"].rolling(10).mean()
    price["MA20"] = price["close"].rolling(20).mean()

    latest = price.iloc[-1]
    previous = price.iloc[-2] if len(price) >= 2 else latest

    signal = "無明顯交叉"

    if previous["MA5"] <= previous["MA10"] and latest["MA5"] > latest["MA10"]:
        signal = "5MA突破10MA：黃金交叉"
    elif previous["MA5"] >= previous["MA10"] and latest["MA5"] < latest["MA10"]:
        signal = "5MA跌破10MA：死亡交叉"
    elif previous["MA5"] <= previous["MA20"] and latest["MA5"] > latest["MA20"]:
        signal = "5MA突破20MA：黃金交叉"
    elif previous["MA5"] >= previous["MA20"] and latest["MA5"] < latest["MA20"]:
        signal = "5MA跌破20MA：死亡交叉"

    inst = finmind(
        "TaiwanStockInstitutionalInvestorsBuySell",
        start_date,
        end_date,
        stock_id
    )

    inst_map = {}

    if not inst.empty:
        for _, row in inst.iterrows():
            d = row.get("date")
            name = row.get("name")
            buy_sell = row.get("buy_sell", 0)

            try:
                buy_sell = int(float(buy_sell)) // 1000
            except:
                buy_sell = 0

            if d not in inst_map:
                inst_map[d] = {
                    "外資": 0,
                    "投信": 0,
                    "自營商": 0
                }

            if "Foreign" in name or "外資" in name:
                inst_map[d]["外資"] += buy_sell
            elif "Investment" in name or "投信" in name:
                inst_map[d]["投信"] += buy_sell
            elif "Dealer" in name or "自營商" in name:
                inst_map[d]["自營商"] += buy_sell

    last5 = price.tail(5)

    history = []

    for _, row in last5.iterrows():
        d = row["date"]
        history.append({
            "日期": d,
            "收盤價": round(float(row["close"]), 2),
            "成交量張數": int(row["Trading_Volume"] // 1000),
            "外資買賣超張數": inst_map.get(d, {}).get("外資", 0),
            "投信買賣超張數": inst_map.get(d, {}).get("投信", 0),
            "自營商買賣超張數": inst_map.get(d, {}).get("自營商", 0)
        })

    return {
        "stock_id": stock_id,
        "stock_name": stock_name,
        "history": history,
        "ma": {
            "5MA": round(float(latest["MA5"]), 2) if pd.notna(latest["MA5"]) else None,
            "10MA": round(float(latest["MA10"]), 2) if pd.notna(latest["MA10"]) else None,
            "20MA": round(float(latest["MA20"]), 2) if pd.notna(latest["MA20"]) else None,
        },
        "signal": signal
    }


def get_top20_detail(date=None):
    top20 = get_top20_volume(date)
    date_text = f"{top20['date'][:4]}-{top20['date'][4:6]}-{top20['date'][6:8]}"

    details = []

    for item in top20["data"]:
        detail = get_stock_detail(
            item["stock_id"],
            item["stock_name"],
            date_text
        )
        item["detail"] = detail
        details.append(item)

    return {
        "date": top20["date"],
        "count": len(details),
        "data": details
    }
