from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import twstock
import yfinance as yf
from datetime import datetime

app = FastAPI()

# 設定 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_yfinance_ticker(stock_id: str) -> str:
    """
    將台灣股票代碼轉換為 Yahoo Finance 格式
    上市 -> .TW
    上櫃 -> .TWO
    """
    if stock_id in twstock.codes:
        market = twstock.codes[stock_id].market
        if market == '上市':
            return f"{stock_id}.TW"
        elif market == '上櫃':
            return f"{stock_id}.TWO"
    
    return f"{stock_id}.TW"

def safe_float(value) -> Optional[float]:
    """安全轉換 float，避免 NaN 或 None"""
    try:
        if value != value: 
            return None
        return float(value)
    except (ValueError, TypeError):
        return None

@app.get("/")
def read_root():
    return {"message": "Stock API is running with yfinance"}

@app.get("/api/stock/{stock_id}")
def get_stock_history(stock_id: str):
    """
    獲取歷史 K 線資料 (改用 yfinance 引擎)
    """
    try:
        ticker_id = get_yfinance_ticker(stock_id)
        ticker = yf.Ticker(ticker_id)

        df = ticker.history(period="3mo")
        
        if df.empty:
            raise HTTPException(status_code=404, detail="No data found for this stock")


        dates = []
        chart_data = []

        df = df.reset_index()

        for _, row in df.iterrows():
            date_str = row['Date'].strftime('%Y-%m-%d')
            
            o = safe_float(row['Open'])
            c = safe_float(row['Close'])
            l = safe_float(row['Low'])
            h = safe_float(row['High'])


            if None in [o, c, l, h]:
                continue
            
            dates.append(date_str)
            chart_data.append([o, c, l, h])

        return {
            "stock_id": stock_id,
            "source": "yfinance",
            "dates": dates,
            "values": chart_data
        }

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/realtime/{stock_id}")
def get_realtime_stock(stock_id: str):
    """
    獲取即時股價
    """
    try:
        realtime = twstock.realtime.get(stock_id)
        if realtime and realtime.get('success'):
            return realtime['realtime']
        else:
            msg = realtime.get('rtmessage', 'Unknown error') if realtime else 'No response'
            raise HTTPException(status_code=404, detail=f"Realtime error: {msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)