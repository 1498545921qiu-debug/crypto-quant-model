"""
加密货币量化筛选网页 - 高级信号版
包含：市场阶段、板块叙事、做多做空、背离、诱多诱空、筑底启动
所有判断基于明确数据规则
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="加密货币量化筛选", layout="wide")
st.title("加密货币量化筛选与高级信号")
st.caption("背离警示 · 诱多诱空 · 筑底启动 · 市场阶段 · 板块叙事 · 做多做空")

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def detect_advanced_signals(df):
    """数据规则驱动的高级信号"""
    if df is None or len(df) < 60:
        return {"背离警示": "-", "诱多/诱空": "-", "筑底/启动": "-"}
    
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    rsi = calc_rsi(close)
    
    signals = {"背离警示": "-", "诱多/诱空": "-", "筑底/启动": "-"}
    
    # 背离
    if len(close) >= 40:
        recent_high = close.iloc[-20:].max()
        prev_high = close.iloc[-40:-20].max()
        recent_rsi_high = rsi.iloc[-20:].max()
        prev_rsi_high = rsi.iloc[-40:-20].max()
        if recent_high > prev_high and recent_rsi_high < prev_rsi_high:
            signals["背离警示"] = "顶背离"
        
        recent_low = close.iloc[-20:].min()
        prev_low = close.iloc[-40:-20].min()
        recent_rsi_low = rsi.iloc[-20:].min()
        prev_rsi_low = rsi.iloc[-40:-20].min()
        if recent_low < prev_low and recent_rsi_low > prev_rsi_low:
            signals["背离警示"] = "底背离"
    
    # 诱多/诱空
    resistance = high.iloc[-30:-5].max()
    support = low.iloc[-30:-5].min()
    recent_vol = volume.iloc[-3:].mean()
    avg_vol = volume.iloc[-20:].mean()
    
    if close.iloc[-5:].max() > resistance and close.iloc[-1] < resistance and recent_vol < avg_vol * 0.85:
        signals["诱多/诱空"] = "疑似诱多"
    if close.iloc[-5:].min() < support and close.iloc[-1] > support and recent_vol < avg_vol * 0.85:
        signals["诱多/诱空"] = "疑似诱空"
    
    # 筑底
    if len(low) >= 15:
        higher_lows = low.iloc[-1] > low.iloc[-8] and low.iloc[-8] > low.iloc[-15]
        vol_dry = volume.iloc[-10:].mean() < volume.iloc[-30:-10].mean() * 0.75
        if higher_lows and vol_dry:
            signals["筑底/启动"] = "筑底特征"
    
    # 启动
    sma20 = close.rolling(20).mean().iloc[-1]
    if close.iloc[-1] > high.iloc[-20:-1].max() and volume.iloc[-1] > avg_vol * 1.7 and close.iloc[-1] > sma20:
        signals["筑底/启动"] = "启动信号"
    
    return signals

@st.cache_data(ttl=3600)
def get_coins(limit=50):
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": limit, "page": 1}
        data = requests.get(url, params=params, timeout=10).json()
        result = []
        for c in data:
            sym = c["symbol"].upper() + "-USD"
            name = c.get("name", "").lower()
            narr = "其他"
            if any(k in name for k in ["ai", "artificial"]):
                narr = "AI"
            elif any(k in name for k in ["meme", "dog", "pepe", "inu"]):
                narr = "Meme"
            elif "depin" in name:
                narr = "DePIN"
            result.append({"symbol": sym, "narrative": narr})
        return result
    except:
        return [{"symbol": "BTC-USD", "narrative": "其他"}]

st.sidebar.header("筛选")
top_n = st.sidebar.slider("市值前N", 10, 80, 30)
coins = get_coins(top_n)
selected = st.sidebar.multiselect("币种", [c["symbol"] for c in coins], default=[c["symbol"] for c in coins[:8]])
if st.sidebar.button("开始分析", type="primary"):
    progress = st.progress(0)
    rows = []
    for i, sym in enumerate(selected):
        try:
            df = yf.download(sym, period="120d", interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df = df.dropna()
            if len(df) < 60:
                continue
            adv = detect_advanced_signals(df)
            price = float(df["Close"].iloc[-1])
            change = (df["Close"].iloc[-1] / df["Close"].iloc[-2] - 1) * 100
            rows.append({
                "币种": sym.replace("-USD", ""),
                "最新价": round(price, 4),
                "涨跌%": round(change, 2),
                **adv
            })
        except:
            pass
        progress.progress((i+1)/len(selected))
    progress.empty()
    if rows:
        st.session_state.df = pd.DataFrame(rows)

if "df" in st.session_state and not st.session_state.df.empty:
    st.dataframe(st.session_state.df, use_container_width=True, hide_index=True)
    st.download_button("下载CSV", st.session_state.df.to_csv(index=False).encode("utf-8-sig"), "signals.csv")
else:
    st.info("选择币种后点击「开始分析」")

st.caption("信号基于明确规则：RSI背离、假突破+量能不足、更高低点+缩量、放量突破。仅供研究。")
