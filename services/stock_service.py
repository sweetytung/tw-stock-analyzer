import requests
import pandas as pd
from datetime import datetime, timedelta

TWSE_MI_INDEX = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
TWSE_STOCK_DAY = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
TWSE_T86 = "https://www.twse.com.tw/rwd/zh/fund/T86"


def to_twse_date(date):
    if not date:
        return datetime.now().strftime("%Y%m%d")
    return date.replace("-", "").replace("/", "")


def parse_num(value):
    try:
        value = str(value).replace(",", "").replace("--", "0").strip()
        return float(value)
    except:
        return 0


def get_top20_volume(date=None):
    date = to_twse_date(date)

    r = requests.get(TWSE_MI_INDEX, params={
        "date": date,
        "type": "ALLBUT0999",
        "response": "json"
    }, timeout=30)
    r.raise_for_status()

    rows = []
    for table in r.json().get("tables", []):
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

        close = parse_num(row[8])
        volume = int(parse_num(row[2]) // 1000)

        if close <= 0:
            continue

        result.append({
            "stock_id": stock_id,
            "stock_name": stock_name,
            "close": close,
            "volume": volume
        })

    result = sorted(result, key=lambda x: x["volume"], reverse=True)[:20]

    for i, item in enumerate(result, 1):
        item["rank"] = i

    return {"date": date, "count": len(result), "data": result}


def get_stock_price_history(stock_id, date):
    date_obj = datetime.strptime(date, "%Y%m%d")
    months = [
        date_obj.strftime("%Y%m%d"),
        (date_obj.replace(day=1) - timedelta(days=1)).strftime("%Y%m%d")
    ]

    all_rows = []

    for m in months:
        r = requests.get(TWSE_STOCK_DAY, params={
            "date": m,
            "stockNo": stock_id,
            "response": "json"
        }, timeout=30)

        if r.status_code != 200:
            continue

        data = r.json().get("data", [])
        all_rows.extend(data)

    rows = []

    for row in all_rows:
        roc_date = row[0]
        y, m, d = roc_date.split("/")
        western_date = f"{int(y) + 1911}-{m}-{d}"

        close = parse_num(row[6])
        volume = int(parse_num(row[1]) // 1000)

        if close > 0:
            rows.append({
                "date": western_date,
                "close": close,
                "volume": volume
            })

    df = pd.DataFrame(rows).drop_duplicates("date").sort_values("date")
    return df


def get_institution_by_date(date):
    r = requests.get(TWSE_T86, params={
        "date": date,
        "selectType": "ALLBUT0999",
        "response": "json"
    }, timeout=30)

    if r.status_code != 200:
        return {}

    data = r.json().get("data", [])
    fields = r.json().get("fields", [])

    result = {}

    for row in data:
        stock_id = row[0].strip()

        def get_field(keyword):
            for i, f in enumerate(fields):
                if keyword in f:
                    return int(parse_num(row[i]) // 1000)
            return 0

        result[stock_id] = {
            "外資買賣超張數": get_field("外陸資買賣超股數"),
            "投信買賣超張數": get_field("投信買賣超股數"),
            "自營商買賣超張數": get_field("自營商買賣超股數")
        }

    return result


def get_stock_detail(stock_id, stock_name, date):
    df = get_stock_price_history(stock_id, date)

    if df.empty or len(df) < 5:
        return {
            "stock_id": stock_id,
            "stock_name": stock_name,
            "history": [],
            "ma": {},
            "signal": "股價資料不足"
        }

    df["MA5"] = df["close"].rolling(5).mean()
    df["MA10"] = df["close"].rolling(10).mean()
    df["MA20"] = df["close"].rolling(20).mean()

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    signal = "無明顯交叉"

    if pd.notna(prev["MA5"]) and pd.notna(prev["MA10"]):
        if prev["MA5"] <= prev["MA10"] and latest["MA5"] > latest["MA10"]:
            signal = "5MA突破10MA：黃金交叉"
        elif prev["MA5"] >= prev["MA10"] and latest["MA5"] < latest["MA10"]:
            signal = "5MA跌破10MA：死亡交叉"

    if signal == "無明顯交叉" and pd.notna(prev["MA20"]):
        if prev["MA5"] <= prev["MA20"] and latest["MA5"] > latest["MA20"]:
            signal = "5MA突破20MA：黃金交叉"
        elif prev["MA5"] >= prev["MA20"] and latest["MA5"] < latest["MA20"]:
            signal = "5MA跌破20MA：死亡交叉"

    last5 = df.tail(5)
    history = []

    for _, row in last5.iterrows():
        twse_date = row["date"].replace("-", "")
        inst = get_institution_by_date(twse_date).get(stock_id, {
            "外資買賣超張數": 0,
            "投信買賣超張數": 0,
            "自營商買賣超張數": 0
        })

        history.append({
            "日期": row["date"],
            "收盤價": round(row["close"], 2),
            "成交量張數": int(row["volume"]),
            **inst
        })

    return {
        "stock_id": stock_id,
        "stock_name": stock_name,
        "history": history,
        "ma": {
            "5MA": round(latest["MA5"], 2) if pd.notna(latest["MA5"]) else None,
            "10MA": round(latest["MA10"], 2) if pd.notna(latest["MA10"]) else None,
            "20MA": round(latest["MA20"], 2) if pd.notna(latest["MA20"]) else None,
        },
        "signal": signal
    }


def get_top20_detail(date=None):
    date = to_twse_date(date)
    top20 = get_top20_volume(date)

    for item in top20["data"]:
        item["detail"] = get_stock_detail(
            item["stock_id"],
            item["stock_name"],
            date
        )

    return top20
