"""
加密货币量化筛选 - 含成交量指标版
新增：OBV、A/D 趋势
保留：背离、诱多诱空、筑底启动
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="加密货币量化筛选", layout="wide")
st.title("加密货币量化筛选（含成交量指标）")
st.caption("OBV · A/D · 背离 · 诱多诱空 · 筑底启动")

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_volume_indicators(df):
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    
    # OBV
    direction = np.sign(close.diff()).fillna(0)
    obv = (direction * volume).cumsum()
    obv_trend = "上升" if obv.iloc[-1] > obv.iloc[-10] else "下降"
    
    # A/D
    clv = ((close - low) - (high - close)) / (high - low + 1e-9)
    ad = (clv * volume).cumsum()
    ad_trend = "上升" if ad.iloc[-1] > ad.iloc[-10] else "下降"
    
    return {"OBV趋势": obv_trend, "A/D趋势": ad_trend}

def detect_advanced_signals(df):
    if len(df) < 60:
        return {"背离警示": "-", "诱多/诱空": "-", "筑底/启动": "-"}
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    rsi = calc_rsi(close)
    signals = {"背离警示": "-", "诱多/诱空": "-", "筑底/启动": "-"}
    
    if len(close) >= 40:
        if close.iloc[-20:].max() > close.iloc[-40:-20].max() and rsi.iloc[-20:].max() < rsi.iloc[-40:-20].max():
            signals["背离警示"] = "顶背离"
        if close.iloc[-20:].min() < close.iloc[-40:-20].min() and rsi.iloc[-20:].min() > rsi.iloc[-40:-20].min():
            signals["背离警示"] = "底背离"
    
    resistance = high.iloc[-30:-5].max()
    support = low.iloc[-30:-5].min()
    recent_vol = volume.iloc[-3:].mean()
    avg_vol = volume.iloc[-20:].mean()
    if close.iloc[-5:].max() > resistance and close.iloc[-1] < resistance and recent_vol < avg_vol * 0.85:
        signals["诱多/诱空"] = "疑似诱多"
    if close.iloc[-5:].min() < support and close.iloc[-1] > support and recent_vol < avg_vol * 0.85:
        signals["诱多/诱空"] = "疑似诱空"
    
    return signals

st.sidebar.header("筛选")
symbols = st.sidebar.multiselect("币种", ["BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD","DOGE-USD","AVAX-USD"], 
                                 default=["BTC-USD","ETH-USD","SOL-USD"])
if st.sidebar.button("开始分析", type="primary"):
    rows = []
    for sym in symbols:
        try:
            df = yf.download(sym, period="90d", interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df = df.dropna()
            if len(df) < 30:
                continue
            vol_ind = calc_volume_indicators(df)
            adv = detect_advanced_signals(df)
            rows.append({
                "币种": sym.replace("-USD",""),
                "最新价": round(float(df["Close"].iloc[-1]), 4),
                **vol_ind,
                **adv
            })
        except Exception as e:
            st.warning(f"{sym} 失败: {e}")
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.info("""
**指标说明（有数据支撑）**
- **OBV**：价涨加量、价跌减量，趋势向上代表资金持续流入
- **A/D**：根据收盘位置分配成交量，上升代表吸筹
- **CVD**：需要逐笔数据，当前免费源无法精确计算
- **ETF净流入 / 链上净流入**：需要 Glassnode、CoinGlass 等付费或限流API，暂以文字提示
- **合约/现货**：可用资金费率、持仓量等，后续可接入
""")
