from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests
import pandas as pd

# 引入核心服務與例外
from core import service
from core.service import DataNotFoundError

app = FastAPI()

# 設定 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Stock API is running with yfinance (Refactored)"}

@app.get("/api/realtime/{stock_id}")
def get_realtime_stock(stock_id: str):
    try:
        return service.get_realtime_data(stock_id)
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"Realtime Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stock/{stock_id}")
def get_stock_history(stock_id: str):
    try:
        return service.get_history_data(stock_id)
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"History Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/intraday/{stock_id}")    
def get_intraday_chart(stock_id: str):
    try:
        return service.get_intraday_data(stock_id)
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"Intraday Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/forex/{pair}")
def get_forex_rate(pair: str):
    try:
        return service.get_forex_data(pair)
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/rank/{rank_type}")
def get_rank_data(rank_type: str):
    """
    獲取漲跌幅排行
    rank_type: 'up' (漲停/漲幅排行) 或 'down' (跌停/跌幅排行)
    """
    try:
        # Yahoo 股市排行榜網址
        url = "https://tw.stock.yahoo.com/rank/change-up" if rank_type == 'up' else "https://tw.stock.yahoo.com/rank/change-down"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 使用 requests 獲取 HTML，再用 pandas 解析
        r = requests.get(url, headers=headers)
        dfs = pd.read_html(r.text)
        
        if not dfs:
            return []
            
        # 通常主要表格是第一個
        df = dfs[0]
        
        # 重新命名欄位以便前端使用 (Yahoo 的欄位名稱可能會變，這裡做簡單對應)
        # 假設欄位包含：['名次', '股票代號', '股票名稱', '股價', '漲跌', '漲跌幅', ...]
        result = []
        
        # 尋找關鍵欄位索引
        col_map = {}
        for col in df.columns:
            if '代號' in col: col_map['code'] = col
            elif '名稱' in col: col_map['name'] = col
            elif '股價' in col or '成交' in col: col_map['price'] = col
            elif '幅' in col: col_map['percent'] = col

        if not col_map.get('code'):
             return []

        for _, row in df.head(30).iterrows(): # 取前 30 名
            # 處理股票代號，有時候會是 "2330.TW" 或單純 "2330"
            raw_code = str(row[col_map['code']])
            code = raw_code.split('.')[0] # 移除可能的 .TW 後綴
            
            # 簡單過濾非股票 (如權證等，通常代號長度不為4)
            if len(code) != 4: 
                continue

            result.append({
                "code": code,
                "name": str(row[col_map['name']]),
                "price": row[col_map['price']],
                "percent": row[col_map['percent']]
            })
            
        return result

    except Exception as e:
        print(f"Rank Error: {e}")
        return []

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)