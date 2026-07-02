import requests
import pandas as pd
from datetime import datetime, timedelta

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"


def fetch_finmind(dataset, start_date, end_date=None, data_id=None):
    params = {
        "dataset": dataset,
        "start_date": start_date,
    }

    if end_date:
        params["end_date"] = end_date

    if data_id:
        params["data_id"] = data_id

    response = requests.get(FINMIND_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json().get("data", [])
    return pd.DataFrame(data)


def get_top20_volume(date=None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    df = fetch_finmind("TaiwanStockPrice", date, date)

    if df.empty:
        return {
            "date": date,
            "message": "查無資料，可能是假日或資料尚未更新",
            "data": []
        }

    df = df[df["stock_id"].astype(str).str.match(r"^\d{4}$")]
    df["Trading_Volume"] = pd.to_numeric(df["Trading_Volume"], errors="coerce").fillna(0)

    top20 = df.sort_values("Trading_Volume", ascending=False).head(20)

    result = []
    for idx, row in enumerate(top20.itertuples(), start=1):
        result.append({
            "rank": idx,
            "stock_id": row.stock_id,
            "date": row.date,
            "open": float(row.open),
            "high": float(row.max),
            "low": float(row.min),
            "close": float(row.close),
            "volume": int(row.Trading_Volume)
        })

    return {
        "date": date,
        "count": len(result),
        "data": result
    }
