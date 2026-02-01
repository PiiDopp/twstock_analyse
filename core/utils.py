import twstock
from typing import Optional

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