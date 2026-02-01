import twstock
import yfinance as yf
import pandas as pd
from datetime import datetime
from .utils import get_yfinance_ticker, safe_float

# 定義一個自訂例外，用於處理找不到資料的情況
class DataNotFoundError(Exception):
    pass

def get_realtime_data(stock_id: str):
    """獲取即時股價 (包含詳細報價資訊)"""
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
            "price": latest,
            "open": open_p,
            "high": high,
            "low": low,
            "volume": volume,
            "prev_close": prev_close,
            "change": round(change, 2),
            "change_percent": round(change_percent, 2),
            "bid": parse_val(rt.get('best_bid_price', [0])[0]),
            "ask": parse_val(rt.get('best_ask_price', [0])[0]),
            "avg_price": round((high + low)/2, 2) if high and low else latest,
            "amount": round(latest * volume / 10000, 2) if latest and volume else 0,
        }
    else:
        msg = realtime.get('rtmessage', 'Unknown error') if realtime else 'No response'
        raise DataNotFoundError(f"Realtime error: {msg}")

def get_history_data(stock_id: str):
    """獲取歷史 K 線資料 + MA (5, 20, 60)"""
    ticker_id = get_yfinance_ticker(stock_id)
    ticker = yf.Ticker(ticker_id)
    
    df = ticker.history(period="1y")
    
    if df.empty:
        raise DataNotFoundError(f"No data found for {stock_id}")

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

def get_intraday_data(stock_id: str):
    """獲取當日即時走勢 (1分鐘 K線)"""
    ticker_id = get_yfinance_ticker(stock_id)
    ticker = yf.Ticker(ticker_id)
    
    df = ticker.history(period="1d", interval="1m")
    
    if df.empty:
        raise DataNotFoundError("No intraday data found")

    ref_price = 0.0
    try:
        ref_price = ticker.info.get('previousClose', df['Open'].iloc[0])
    except:
        ref_price = df['Open'].iloc[0]

    times = []
    prices = []
    volumes = []

    # 處理時區
    if df.index.tz is None:
        # 如果 yfinance 沒有回傳時區，通常假設是 UTC，需視情況轉換，這裡保留原邏輯結構
        # 但通常 yfinance history 會帶時區。若無時區直接 convert 會報錯，建議加個檢查
        df.index = df.index.tz_localize('UTC').tz_convert('Asia/Taipei')
    else:
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

def get_forex_data(pair: str):
    """獲取匯率資料"""
    ticker_str = pair.upper()
    if not ticker_str.endswith("=X"):
        ticker_str += "=X"
        
    ticker = yf.Ticker(ticker_str)
    df = ticker.history(period="1d")
    
    if df.empty:
        raise DataNotFoundError(f"找不到匯率資料: {pair}")

    latest_rate = float(df['Close'].iloc[-1])
    prev_close = float(ticker.info.get('previousClose', latest_rate))
    
    change = latest_rate - prev_close
    change_percent = (change / prev_close) * 100 if prev_close else 0

    return {
        "pair": ticker_str.replace("=X", ""),
        "rate": round(latest_rate, 4),
        "change": round(change, 4),
        "change_percent": round(change_percent, 2),
        "update_time": datetime.now().strftime('%H:%M:%S')
    }