import requests
import pandas as pd
from datetime import datetime, timedelta

TWSE_MI_INDEX = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
TWSE_STOCK_DAY = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
TWSE_T86 = "https://www.twse.com.tw/rwd/zh/fund/T86"


def to_twse_date(date=None):
    if not date:
        return datetime.now().strftime("%Y%m%d")
    return str(date).replace("-", "").replace("/", "")


def parse_num(value):
    try:
        return float(str(value).replace(",", "").replace("--", "0").replace("X", "0").strip())
    except Exception:
        return 0


def twse_get(url, params):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.twse.com.tw/"
    }
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def get_institution_map(date):
    date = to_twse_date(date)
    try:
        js = twse_get(TWSE_T86, {
            "date": date,
            "selectType": "ALLBUT0999",
            "response": "json"
        })

        data = js.get("data", [])
        fields = js.get("fields", [])

        result = {}

        for row in data:
            if not row:
                continue

            stock_id = str(row[0]).strip()

            def find_field(keyword):
                for i, field_name in enumerate(fields):
                    if keyword in field_name and i < len(row):
                        return int(parse_num(row[i]) // 1000)
                return 0

            result[stock_id] = {
                "外資買賣超張數": find_field("外陸資買賣超股數"),
                "投信買賣超張數": find_field("投信買賣超股數"),
                "自營商買賣超張數": find_field("自營商買賣超股數")
            }

        return result

    except Exception:
        return {}


def get_top20_volume(date=None):
    date = to_twse_date(date)
    institution_map = get_institution_map(date)

    js = twse_get(TWSE_MI_INDEX, {
        "date": date,
        "type": "ALLBUT0999",
        "response": "json"
    })

    rows = []
    for table in js.get("tables", []):
        fields = table.get("fields", [])
        if "證券代號" in fields and "成交股數" in fields and "收盤價" in fields:
            rows = table.get("data", [])
            break

    result = []

    for row in rows:
        if len(row) < 9:
            continue

        stock_id = str(row[0]).strip()
        stock_name = str(row[1]).strip()

        if not stock_id.isdigit() or len(stock_id) != 4:
            continue

        close = parse_num(row[8])
        volume = int(parse_num(row[2]) // 1000)

        if close <= 0 or volume <= 0:
            continue

        inst = institution_map.get(stock_id, {
            "外資買賣超張數": 0,
            "投信買賣超張數": 0,
            "自營商買賣超張數": 0
        })

        result.append({
            "stock_id": stock_id,
            "stock_name": stock_name,
            "close": close,
            "volume": volume,
            **inst
        })

    result = sorted(result, key=lambda x: x["volume"], reverse=True)[:20]

    for i, item in enumerate(result, 1):
        item["rank"] = i

    return {
        "date": date,
        "count": len(result),
        "data": result
    }


def get_stock_price_history(stock_id, date=None):
    date = to_twse_date(date)
    date_obj = datetime.strptime(date, "%Y%m%d")

    this_month = date_obj.replace(day=1)
    last_month = (this_month - timedelta(days=1)).replace(day=1)

    months = [
        this_month.strftime("%Y%m%d"),
        last_month.strftime("%Y%m%d")
    ]

    rows = []

    for month_date in months:
        try:
            js = twse_get(TWSE_STOCK_DAY, {
                "date": month_date,
                "stockNo": stock_id,
                "response": "json"
            })

            if js.get("stat") != "OK":
                continue

            for row in js.get("data", []):
                try:
                    roc_date = row[0]
                    y, m, d = roc_date.split("/")
                    western_date = f"{int(y) + 1911}-{m}-{d}"

                    volume = int(parse_num(row[1]) // 1000)
                    close = parse_num(row[6])

                    if close > 0:
                        rows.append({
                            "date": western_date,
                            "close": close,
                            "volume": volume
                        })
                except Exception:
                    continue

        except Exception:
            continue

    if not rows:
        return pd.DataFrame(columns=["date", "close", "volume"])

    df = pd.DataFrame(rows)

    if "date" not in df.columns:
        return pd.DataFrame(columns=["date", "close", "volume"])

    return (
        df.drop_duplicates("date")
          .sort_values("date")
          .reset_index(drop=True)
    )
def detect_cross(df):
    if len(df) < 2:
        return "資料不足"

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    if pd.notna(prev.get("MA5")) and pd.notna(prev.get("MA10")) and pd.notna(latest.get("MA5")) and pd.notna(latest.get("MA10")):
        if prev["MA5"] <= prev["MA10"] and latest["MA5"] > latest["MA10"]:
            return "5MA突破10MA：黃金交叉"
        if prev["MA5"] >= prev["MA10"] and latest["MA5"] < latest["MA10"]:
            return "5MA跌破10MA：死亡交叉"

    if pd.notna(prev.get("MA5")) and pd.notna(prev.get("MA20")) and pd.notna(latest.get("MA5")) and pd.notna(latest.get("MA20")):
        if prev["MA5"] <= prev["MA20"] and latest["MA5"] > latest["MA20"]:
            return "5MA突破20MA：黃金交叉"
        if prev["MA5"] >= prev["MA20"] and latest["MA5"] < latest["MA20"]:
            return "5MA跌破20MA：死亡交叉"

    return "無明顯交叉"


def get_stock_detail(stock_id, stock_name="", date=None):
    date = to_twse_date(date)
    df = get_stock_price_history(stock_id, date)

    default_inst = {
        "外資買賣超張數": 0,
        "投信買賣超張數": 0,
        "自營商買賣超張數": 0
    }

    if df.empty or len(df) < 5:
        return {
            "stock_id": stock_id,
            "stock_name": stock_name,
            "history": [],
            "institution": default_inst,
            "ma": {},
            "signal": "股價資料不足"
        }

    df["MA5"] = df["close"].rolling(5).mean()
    df["MA10"] = df["close"].rolling(10).mean()
    df["MA20"] = df["close"].rolling(20).mean()

    latest = df.iloc[-1]
    institution_map = get_institution_map(date)
    latest_inst = institution_map.get(stock_id, default_inst)

    history = []
    for _, row in df.tail(5).iterrows():
        history.append({
            "日期": row["date"],
            "收盤價": round(float(row["close"]), 2),
            "成交量張數": int(row["volume"])
        })

    return {
        "stock_id": stock_id,
        "stock_name": stock_name,
        "history": history,
        "institution": latest_inst,
        "ma": {
            "5MA": round(float(latest["MA5"]), 2) if pd.notna(latest["MA5"]) else None,
            "10MA": round(float(latest["MA10"]), 2) if pd.notna(latest["MA10"]) else None,
            "20MA": round(float(latest["MA20"]), 2) if pd.notna(latest["MA20"]) else None
        },
        "signal": detect_cross(df)
    }
