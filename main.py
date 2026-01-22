from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import twstock
import yfinance as yf
from datetime import datetime
import pandas as pd 

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
    若 twstock 查無資料 (如新上市或 ETF)，預設回傳 .TW
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

        if value is None or (isinstance(value, float) and value != value):
            return None
        return float(value)
    except (ValueError, TypeError):
        return None

@app.get("/")
def read_root():
    return {"message": "Stock API is running with yfinance"}

@app.get("/api/realtime/{stock_id}")
def get_realtime_stock(stock_id: str):
    """
    獲取即時股價 (包含詳細報價資訊)
    """
    try:
        realtime = twstock.realtime.get(stock_id)
        
        if realtime and realtime.get('success'):
            info = realtime['info'] 
            rt = realtime['realtime'] 
            
  
            def parse_val(val):
                try:
                    return float(val)
                except:
                    return None

            latest = parse_val(rt.get('latest_trade_price'))
            open_p = parse_val(rt.get('open'))
            high = parse_val(rt.get('high'))
            low = parse_val(rt.get('low'))
            volume = parse_val(rt.get('accumulate_trade_volume'))
            
            try:
                stock_hist = twstock.Stock(stock_id)
                # 抓最近一筆交易的 close (即昨收)
                prev_close = stock_hist.price[-1] if stock_hist.price else latest
            except:
                prev_close = latest 

            # 計算漲跌
            change = 0.0
            change_percent = 0.0
            if latest and prev_close:
                change = latest - prev_close
                change_percent = (change / prev_close) * 100

            return {
                "name": info.get('name', stock_id),
                "code": info.get('code', stock_id),
                "timestamp": rt.get('latest_trade_time'),
                "price": latest,              # 成交
                "open": open_p,               # 開盤
                "high": high,                 # 最高
                "low": low,                   # 最低
                "volume": volume,             # 總量
                "prev_close": prev_close,     # 昨收
                "change": round(change, 2),   # 漲跌
                "change_percent": round(change_percent, 2), # 漲跌幅
                "bid": parse_val(rt.get('best_bid_price', [0])[0]), # 買價 (取第一檔)
                "ask": parse_val(rt.get('best_ask_price', [0])[0]), # 賣價 (取第一檔)
                "avg_price": round((high + low)/2, 2) if high and low else latest, # 均價 (估算)
                "amount": round(latest * volume / 10000, 2) if latest and volume else 0, # 金額(億) - 粗略估算
            }
        else:
            msg = realtime.get('rtmessage', 'Unknown error') if realtime else 'No response'
            raise HTTPException(status_code=404, detail=f"Realtime error: {msg}")
            
    except Exception as e:
        print(f"Realtime Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/api/stock/{stock_id}")
def get_stock_history(stock_id: str):
    """
    獲取歷史 K 線資料 + MA (5, 20, 60) (使用 yfinance)
    """
    try:

        ticker_id = get_yfinance_ticker(stock_id)
        ticker = yf.Ticker(ticker_id)
        

        df = ticker.history(period="1y")
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {stock_id}")

        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()


        dates = []
        chart_data = [] 
        ma5_data = []   
        ma20_data = []  
        ma60_data = []  


        df = df.reset_index()

        for _, row in df.iterrows():
            date_str = row['Date'].strftime('%Y-%m-%d')
            
            o = safe_float(row['Open'])
            c = safe_float(row['Close'])
            l = safe_float(row['Low'])
            h = safe_float(row['High'])

            m5 = safe_float(row['MA5'])
            m20 = safe_float(row['MA20'])
            m60 = safe_float(row['MA60'])

            if None in [o, c, l, h]:
                continue
            
            dates.append(date_str)
            chart_data.append([o, c, l, h])
            
            ma5_data.append(m5)
            ma20_data.append(m20)
            ma60_data.append(m60)

        return {
            "stock_id": stock_id,
            "dates": dates,
            "values": chart_data,
            "ma5": ma5_data,
            "ma20": ma20_data,
            "ma60": ma60_data
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"History Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/intraday/{stock_id}")    
def get_intraday_chart(stock_id: str):
    """
    獲取當日即時走勢 (1分鐘 K線)
    """
    try:
        ticker_id = get_yfinance_ticker(stock_id)
        ticker = yf.Ticker(ticker_id)
        
        df = ticker.history(period="1d", interval="1m")
        
        if df.empty:
            raise HTTPException(status_code=404, detail="No intraday data found")

        ref_price = 0.0
        try:
            ref_price = ticker.info.get('previousClose', df['Open'].iloc[0])
        except:
            ref_price = df['Open'].iloc[0]

        times = []
        prices = []
        volumes = []

        df.index = df.index.tz_convert('Asia/Taipei')

        for dt, row in df.iterrows():

            time_str = dt.strftime('%H:%M')
            p = safe_float(row['Close'])
            v = safe_float(row['Volume'])
            
            if p is not None:
                times.append(time_str)
                prices.append(p)
                volumes.append(v)

        return {
            "stock_id": stock_id,
            "ref_price": ref_price, 
            "prices": prices,
            "volumes": volumes
        }

    except Exception as e:
        print(f"Intraday Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)