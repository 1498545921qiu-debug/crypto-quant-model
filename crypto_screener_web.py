"""
加密货币量化筛选 - 小时线CVD增强版
新增：小时线近似CVD
保留：资金费率、持仓量、OBV、A/D
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="加密货币量化筛选", layout="wide")
st.title("加密货币量化筛选（含小时线CVD）")
st.caption("小时线CVD · 资金费率 · 持仓量 · OBV · A/D")

def get_binance_funding_oi(symbol):
    try:
        base = symbol.replace("-USD", "")
        pair = base + "USDT"
        fr = requests.get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={pair}&limit=1", timeout=8).json()
        funding = float(fr[0]["fundingRate"]) * 100 if fr else None
        oi = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={pair}", timeout=8).json()
        open_interest = float(oi.get("openInterest", 0))
        return {
            "资金费率%": round(funding, 4) if funding is not None else "-",
            "持仓量": round(open_interest, 0) if open_interest else "-"
        }
    except:
        return {"资金费率%": "-", "持仓量": "-"}

def calc_hourly_cvd(symbol):
    """用小时线近似CVD"""
    try:
        df = yf.download(symbol, period="5d", interval="1h", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df.dropna()
        if len(df) < 10:
            return "-"
        direction = np.sign(df["Close"].diff()).fillna(0)
        cvd = (direction * df["Volume"]).cumsum()
        recent = cvd.iloc[-1] - cvd.iloc[-12]
        if recent > 0:
            return f"近12h净流入近似 +{recent/1e6:.1f}M"
        else:
            return f"近12h净流出近似 {recent/1e6:.1f}M"
    except:
        return "-"

def calc_obv_ad(df):
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    direction = np.sign(close.diff()).fillna(0)
    obv = (direction * volume).cumsum()
    obv_trend = "上升" if obv.iloc[-1] > obv.iloc[-5] else "下降"
    clv = ((close - low) - (high - close)) / (high - low + 1e-9)
    ad = (clv * volume).cumsum()
    ad_trend = "上升" if ad.iloc[-1] > ad.iloc[-5] else "下降"
    return {"OBV趋势": obv_trend, "A/D趋势": ad_trend}

st.sidebar.header("筛选")
symbols = st.sidebar.multiselect(
    "币种",
    ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "DOGE-USD"],
    default=["BTC-USD", "ETH-USD", "SOL-USD"]
)
if st.sidebar.button("开始分析", type="primary"):
    rows = []
    for sym in symbols:
        try:
            df_d = yf.download(sym, period="30d", interval="1d", progress=False)
            if isinstance(df_d.columns, pd.MultiIndex):
                df_d.columns = df_d.columns.droplevel(1)
            df_d = df_d.dropna()
            
            deriv = get_binance_funding_oi(sym)
            cvd = calc_hourly_cvd(sym)
            vol_ind = calc_obv_ad(df_d) if len(df_d) > 10 else {}
            
            fr = deriv["资金费率%"]
            fr_note = "正常"
            if isinstance(fr, float):
                if fr > 0.05: fr_note = "多头拥挤"
                elif fr < -0.03: fr_note = "空头拥挤"
            
            rows.append({
                "币种": sym.replace("-USD", ""),
                "最新价": round(float(df_d["Close"].iloc[-1]), 2) if len(df_d) else "-",
                "小时CVD": cvd,
                "资金费率%": fr,
                "费率状态": fr_note,
                "持仓量": deriv["持仓量"],
                **vol_ind
            })
        except Exception as e:
            st.warning(f"{sym}: {e}")
    
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("小时CVD为近似值（涨的小时加量、跌的小时减量），正值代表近期主动买盘占优。")

st.info("下一步可继续加：稳定币流向、链上净流入。")
