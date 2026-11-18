"""
加密货币筛选网页 - 扩展版
支持筛选市值前100加密货币
"""

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import requests

st.set_page_config(page_title="加密货币量化筛选", layout="wide")
st.title("加密货币量化筛选网页")
st.caption("多币种筛选 · 买卖信号 · 止盈止损 · 波动事件提示")

@st.cache_data(ttl=3600)
def get_top_coins(limit=100):
    """从 CoinGecko 获取市值前 N 的币种"""
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": False
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        symbols = []
        for coin in data:
            sym = coin["symbol"].upper() + "-USD"
            symbols.append(sym)
        return symbols
    except Exception as e:
        st.warning(f"获取币种列表失败，使用默认列表：{e}")
        return ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "DOGE-USD", "AVAX-USD"]

# 侧边栏
st.sidebar.header("筛选设置")
top_n = st.sidebar.slider("筛选市值前 N 名", 10, 100, 50)
all_coins = get_top_coins(top_n)
selected = st.sidebar.multiselect(
    "选择要筛选的币种（可多选或全选）",
    all_coins,
    default=all_coins[:20]
)
period = st.sidebar.selectbox("数据周期", ["30d", "60d", "90d"], index=1)
run = st.sidebar.button("开始筛选", type="primary")

def get_data(symbol, period):
    try:
        df = yf.download(symbol, period=period, interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        return df.dropna()
    except:
        return None

def analyze(df, symbol):
    if df is None or len(df) < 30:
        return None
    close = df["Close"]
    volume = df["Volume"]
    price = float(close.iloc[-1])
    change = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100

    sma20 = close.rolling(20).mean().iloc[-1]
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean().iloc[-1]
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
    rsi = 100 - (100 / (1 + gain / loss)) if loss != 0 else 50

    vol_ma = volume.rolling(20).mean().iloc[-1]
    vol_ratio = volume.iloc[-1] / vol_ma if vol_ma > 0 else 0
    volatility = close.pct_change().rolling(5).std().iloc[-1] * 100

    if price > sma20 and rsi < 50:
        signal = "买入"
        sl = round(price * 0.988, 4)
        tp = round(price * 1.018, 4)
    elif rsi > 70 or price < sma20 * 0.97:
        signal = "卖出"
        sl = tp = "-"
    else:
        signal = "观望"
        sl = tp = "-"

    events = []
    if abs(change) >= 4:
        events.append(f"价格异动{change:+.1f}%")
    if vol_ratio >= 1.8:
        events.append(f"量能{vol_ratio:.1f}x")
    if volatility >= 4:
        events.append(f"波动率{volatility:.1f}%")

    return {
        "币种": symbol.replace("-USD", ""),
        "最新价": round(price, 4),
        "涨跌%": round(change, 2),
        "信号": signal,
        "建议止损": sl,
        "建议止盈": tp,
        "RSI": round(rsi, 1),
        "波动提示": " | ".join(events) if events else "-"
    }

if run:
    if not selected:
        st.warning("请至少选择一个币种")
    else:
        progress = st.progress(0)
        results = []
        for i, sym in enumerate(selected):
            df = get_data(sym, period)
            res = analyze(df, sym)
            if res:
                results.append(res)
            progress.progress((i + 1) / len(selected))
        progress.empty()
        st.session_state.results = pd.DataFrame(results)

if "results" in st.session_state and not st.session_state.results.empty:
    df = st.session_state.results

    def color_signal(val):
        if val == "买入":
            return "background-color: #d4edda; color: #155724"
        elif val == "卖出":
            return "background-color: #f8d7da; color: #721c24"
        return ""

    st.subheader(f"筛选结果（{datetime.now().strftime('%Y-%m-%d %H:%M')}）共 {len(df)} 个币")
    styled = df.style.map(color_signal, subset=["信号"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    vol_df = df[df["波动提示"] != "-"]
    if not vol_df.empty:
        st.subheader("波动事件提示")
        st.dataframe(vol_df[["币种", "最新价", "涨跌%", "波动提示"]], use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("下载筛选结果 CSV", csv, "crypto_screen.csv", "text/csv")
else:
    st.info("请在左侧选择币种数量和具体币种后，点击「开始筛选」")

st.markdown("---")
st.caption("数据来源：CoinGecko + Yahoo Finance。仅供学习研究，不构成投资建议。")
