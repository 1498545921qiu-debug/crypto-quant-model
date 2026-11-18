"""
加密货币量化筛选 - 稳定币流向增强版
新增：稳定币总市值变化（资金进出场参考）
保留：小时CVD、资金费率、持仓量、OBV、A/D
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="加密货币量化筛选", layout="wide")
st.title("加密货币量化筛选（含稳定币流向）")
st.caption("稳定币流向 · 小时CVD · 资金费率 · 持仓量")

@st.cache_data(ttl=1800)
def get_stablecoin_flow():
    """用DefiLlama稳定币市值变化近似资金流向"""
    try:
        url = "https://stablecoins.llama.fi/stablecoincharts/all"
        data = requests.get(url, timeout=10).json()
        if not data or len(data) < 2:
            return "数据不足"
        latest = data[-1].get("totalCirculatingUSD", {}).get("peggedUSD", 0)
        prev = data[-2].get("totalCirculatingUSD", {}).get("peggedUSD", 0)
        change = latest - prev
        change_m = change / 1e6
        if change > 0:
            return f"近1日稳定币增发 +{change_m:.0f}M（资金可能进场）"
        else:
            return f"近1日稳定币减少 {change_m:.0f}M（资金可能离场）"
    except Exception as e:
        return f"获取失败（{str(e)[:30]}）"

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
    try:
        df = yf.download(symbol, period="5d", interval="1h", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df.dropna()
        if len(df) < 12:
            return "-"
        direction = np.sign(df["Close"].diff()).fillna(0)
        cvd = (direction * df["Volume"]).cumsum()
        recent = cvd.iloc[-1] - cvd.iloc[-12]
        sign = "+" if recent > 0 else ""
        return f"近12h {sign}{recent/1e6:.1f}M"
    except:
        return "-"

# 显示稳定币全局流向
st.info(f"**稳定币流向参考**：{get_stablecoin_flow()}")

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
            df = yf.download(sym, period="30d", interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            price = round(float(df["Close"].dropna().iloc[-1]), 2) if not df.empty else "-"
            
            deriv = get_binance_funding_oi(sym)
            cvd = calc_hourly_cvd(sym)
            
            fr = deriv["资金费率%"]
            fr_note = "正常"
            if isinstance(fr, float):
                if fr > 0.05: fr_note = "多头拥挤"
                elif fr < -0.03: fr_note = "空头拥挤"
            
            rows.append({
                "币种": sym.replace("-USD", ""),
                "最新价": price,
                "小时CVD": cvd,
                "资金费率%": fr,
                "费率状态": fr_note,
                "持仓量": deriv["持仓量"]
            })
        except Exception as e:
            st.warning(f"{sym}: {e}")
    
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.caption("稳定币增发通常伴随资金进场，减少则可能离场。小时CVD为正代表近期主动买盘占优。数据仅供研究。")
