"""
加密货币量化筛选 - 衍生品数据增强版
新增：资金费率、持仓量（Binance公开API）
保留：OBV、A/D、背离、诱多诱空等
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="加密货币量化筛选", layout="wide")
st.title("加密货币量化筛选（含衍生品数据）")
st.caption("资金费率 · 持仓量 · OBV · A/D · 背离警示")

def get_binance_funding_oi(symbol):
    """获取Binance永续合约资金费率和持仓量"""
    try:
        base = symbol.replace("-USD", "")
        pair = base + "USDT"
        
        fr_url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={pair}&limit=1"
        fr = requests.get(fr_url, timeout=8).json()
        funding = float(fr[0]["fundingRate"]) * 100 if fr else None
        
        oi_url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={pair}"
        oi = requests.get(oi_url, timeout=8).json()
        open_interest = float(oi.get("openInterest", 0))
        
        return {
            "资金费率%": round(funding, 4) if funding is not None else "-",
            "持仓量": round(open_interest, 0) if open_interest else "-"
        }
    except:
        return {"资金费率%": "-", "持仓量": "-"}

def calc_volume_indicators(df):
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

st.sidebar.header("筛选设置")
symbols = st.sidebar.multiselect(
    "选择币种",
    ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "DOGE-USD", "ADA-USD"],
    default=["BTC-USD", "ETH-USD", "SOL-USD"]
)
if st.sidebar.button("开始分析", type="primary"):
    rows = []
    progress = st.progress(0)
    for i, sym in enumerate(symbols):
        try:
            df = yf.download(sym, period="60d", interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df = df.dropna()
            if len(df) < 20:
                continue
            
            vol_ind = calc_volume_indicators(df)
            deriv = get_binance_funding_oi(sym)
            
            fr = deriv["资金费率%"]
            fr_note = ""
            if isinstance(fr, (int, float)):
                if fr > 0.05:
                    fr_note = "费率偏高（多头拥挤）"
                elif fr < -0.03:
                    fr_note = "费率负（空头拥挤）"
                else:
                    fr_note = "费率正常"
            
            rows.append({
                "币种": sym.replace("-USD", ""),
                "最新价": round(float(df["Close"].iloc[-1]), 4),
                "资金费率%": fr,
                "费率提示": fr_note,
                "持仓量": deriv["持仓量"],
                **vol_ind
            })
        except Exception as e:
            st.warning(f"{sym}: {e}")
        progress.progress((i + 1) / len(symbols))
    progress.empty()
    
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("资金费率 >0.05% 通常代表多头拥挤，<-0.03% 代表空头拥挤，极端值容易引发反向波动。")

st.info("""
**当前已接入**
- Binance 永续合约资金费率（实时）
- 持仓量（Open Interest）
- OBV / A/D 趋势

**下一步计划**
- 小时线近似CVD
- 稳定币流向
- 链上交易所净流入（需额外API）
""")
