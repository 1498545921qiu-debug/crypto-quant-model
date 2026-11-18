"""
加密货币自动筛选 - 做多做空信号版
基于：资金费率 + 小时CVD + 价格趋势 自动给出信号
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="加密货币自动信号", layout="wide")
st.title("加密货币自动做多/做空信号")
st.caption("自动扫描 · 资金费率 · 小时CVD · 趋势确认")

def get_funding(symbol):
    try:
        pair = symbol.replace("-USD", "") + "USDT"
        fr = requests.get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={pair}&limit=1", timeout=6).json()
        return float(fr[0]["fundingRate"]) * 100 if fr else 0
    except:
        return 0

def get_hourly_cvd_score(symbol):
    try:
        df = yf.download(symbol, period="3d", interval="1h", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df.dropna()
        if len(df) < 12:
            return 0
        direction = np.sign(df["Close"].diff()).fillna(0)
        cvd = (direction * df["Volume"]).cumsum()
        return float(cvd.iloc[-1] - cvd.iloc[-12])
    except:
        return 0

def analyze_signal(symbol):
    try:
        df = yf.download(symbol, period="30d", interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df.dropna()
        if len(df) < 20:
            return None
        
        price = float(df["Close"].iloc[-1])
        sma20 = df["Close"].rolling(20).mean().iloc[-1]
        trend_up = price > sma20
        trend_down = price < sma20
        
        funding = get_funding(symbol)
        cvd = get_hourly_cvd_score(symbol)
        
        if trend_up and cvd > 0 and funding < 0.08:
            signal = "做多"
            reason = "趋势向上 + 小时CVD净流入 + 费率未极端"
        elif trend_down and cvd < 0 and funding > -0.05:
            signal = "做空"
            reason = "趋势向下 + 小时CVD净流出 + 费率未极端"
        else:
            signal = "观望"
            reason = "-"
        
        return {
            "币种": symbol.replace("-USD", ""),
            "最新价": round(price, 4),
            "信号": signal,
            "依据": reason,
            "资金费率%": round(funding, 4),
            "小时CVD": f"{cvd/1e6:+.1f}M"
        }
    except:
        return None

DEFAULT_COINS = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", 
                 "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", "DOT-USD"]

st.sidebar.header("自动扫描")
scan_list = st.sidebar.multiselect("扫描币种", DEFAULT_COINS, default=DEFAULT_COINS[:6])
only_signal = st.sidebar.checkbox("只显示有信号的币", value=True)

if st.sidebar.button("开始自动筛选", type="primary"):
    progress = st.progress(0)
    results = []
    for i, sym in enumerate(scan_list):
        res = analyze_signal(sym)
        if res:
            results.append(res)
        progress.progress((i + 1) / len(scan_list))
    progress.empty()
    
    df = pd.DataFrame(results)
    if only_signal:
        df = df[df["信号"].isin(["做多", "做空"])]
    
    if not df.empty:
        def color(val):
            if val == "做多": return "background-color:#d4edda"
            if val == "做空": return "background-color:#f8d7da"
            return ""
        st.subheader(f"筛选结果（{len(df)} 个符合条件）")
        st.dataframe(df.style.map(color, subset=["信号"]), use_container_width=True, hide_index=True)
    else:
        st.warning("当前没有符合做多/做空条件的币种")

st.caption("信号规则：做多=日线站上20均线 + 小时CVD为正 + 资金费率<0.08%；做空=日线低于20均线 + 小时CVD为负 + 资金费率>-0.05%。仅供研究。")
