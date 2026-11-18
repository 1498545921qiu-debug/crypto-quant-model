"""
加密货币量化筛选 + 回测网页（完善版）
改进：
- 优化买卖信号逻辑（趋势+RSI回升+量能确认）
- 动态止盈止损（基于波动率）
- 流动性过滤
- 只显示买入信号选项
- 单币种历史回测
- 新增：市场阶段判断（牛市/熊市/震荡市）
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import requests

st.set_page_config(page_title="加密货币量化筛选与回测", layout="wide")
st.title("加密货币量化筛选与回测")
st.caption("优化信号 · 动态止盈止损 · 流动性过滤 · 历史回测 · 市场阶段")

@st.cache_data(ttl=3600)
def get_top_coins(limit=100):
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {"vs_currency": "usd", "order": "market_cap_desc",
                  "per_page": limit, "page": 1, "sparkline": False}
        data = requests.get(url, params=params, timeout=10).json()
        return [c["symbol"].upper() + "-USD" for c in data]
    except:
        return ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD"]

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_coin(df, symbol):
    if df is None or len(df) < 60:
        return None
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    price = float(close.iloc[-1])

    sma20 = close.rolling(20).mean().iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1]
    rsi = calc_rsi(close).iloc[-1]
    rsi_prev = calc_rsi(close).iloc[-2]

    atr = (high - low).rolling(14).mean().iloc[-1]
    vol_pct = atr / price * 100

    vol_ma = volume.rolling(20).mean().iloc[-1]
    vol_ratio = volume.iloc[-1] / vol_ma if vol_ma > 0 else 0
    avg_dollar_vol = (volume * close).rolling(20).mean().iloc[-1]

    if avg_dollar_vol < 1_000_000:
        return None

    trend_up = price > sma20 and sma20 > sma50
    rsi_recover = 35 < rsi < 60 and rsi > rsi_prev
    volume_ok = vol_ratio > 1.2

    # 熊市时提高买入门槛
    if phase == "熊市":
        rsi_recover = 30 < rsi < 45 and rsi > rsi_prev

    if trend_up and rsi_recover and volume_ok:
        signal = "买入"
        sl_pct = max(1.0, min(3.0, vol_pct * 0.8))
        tp_pct = max(1.5, min(5.0, vol_pct * 1.5))
        sl = round(price * (1 - sl_pct/100), 4)
        tp = round(price * (1 + tp_pct/100), 4)
    elif rsi > 75 or price < sma20 * 0.95:
        signal = "卖出"
        sl = tp = "-"
    else:
        signal = "观望"
        sl = tp = "-"

    change = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100
    events = []
    if abs(change) >= 5:
        events.append(f"价格异动{change:+.1f}%")
    if vol_ratio >= 2:
        events.append(f"量能{vol_ratio:.1f}x")

    return {
        "币种": symbol.replace("-USD", ""),
        "最新价": round(price, 4),
        "涨跌%": round(change, 2),
        "信号": signal,
        "建议止损": sl,
        "建议止盈": tp,
        "RSI": round(rsi, 1),
        "波动率%": round(vol_pct, 2),
        "波动提示": " | ".join(events) if events else "-"
    }

# ==========市场阶段判断==========
@st.cache_data(ttl=1800)
def get_market_phase():
    try:
        btc = yf.download("BTC-USD", period="120d", interval="1d", progress=False)
        if isinstance(btc.columns, pd.MultiIndex):
            btc.columns = btc.columns.droplevel(1)
        close = btc["Close"].dropna()
        sma50 = close.rolling(50).mean().iloc[-1]
        sma50_prev = close.rolling(50).mean().iloc[-5]
        price = close.iloc[-1]
        if price > sma50 and sma50 > sma50_prev:
            return "牛市", "BTC 处于上升趋势，可正常寻找买入机会"
        elif price < sma50 and sma50 < sma50_prev:
            return "熊市", "BTC 处于下降趋势，建议减少买入或仅短线操作"
        else:
            return "震荡市", "趋势不明，建议降低仓位、谨慎操作"
    except:
        return "未知", "无法获取市场数据"

phase, phase_desc = get_market_phase()
phase_color = {"牛市": "green", "熊市": "red", "震荡市": "orange"}.get(phase, "gray")
st.markdown(f"**当前市场阶段：<span style='color:{phase_color};font-size:1.2em'>{phase}</span>**  \n{phase_desc}", unsafe_allow_html=True)
st.markdown("---")

# ==========侧边栏==========
st.sidebar.header("筛选设置")
top_n = st.sidebar.slider("市值前 N 名", 20, 100, 50)
only_buy = st.sidebar.checkbox("只显示买入信号", value=False)
period = st.sidebar.selectbox("数据周期", ["60d", "90d", "180d"], index=0)
coins = get_top_coins(top_n)
selected = st.sidebar.multiselect("选择币种", coins, default=coins[:15])
run = st.sidebar.button("开始筛选", type="primary")

# ==========筛选==========
if run and selected:
    progress = st.progress(0)
    results = []
    for i, sym in enumerate(selected):
        try:
            df = yf.download(sym, period=period, interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            res = analyze_coin(df.dropna(), sym)
            if res:
                results.append(res)
        except:
            pass
        progress.progress((i+1)/len(selected))
    progress.empty()
    if results:
        df_res = pd.DataFrame(results)
        if only_buy and "信号" in df_res.columns:
            df_res = df_res[df_res["信号"] == "买入"]
        st.session_state.results = df_res
    else:
        st.session_state.results = pd.DataFrame()
        st.warning("没有找到符合条件的币种（可能被流动性过滤或无买入信号）")

# ==========显示结果==========
if "results" in st.session_state and not st.session_state.results.empty:
    df = st.session_state.results
    def color(val):
        if val == "买入": return "background-color:#d4edda"
        if val == "卖出": return "background-color:#f8d7da"
        return ""
    st.subheader(f"筛选结果（{len(df)} 个币）")
    st.dataframe(df.style.map(color, subset=["信号"]), use_container_width=True, hide_index=True)

    st.subheader("单币种历史回测")
    coin_list = df["币种"].tolist()
    if coin_list:
        bt_coin = st.selectbox("选择要回测的币种", coin_list)
        if st.button("运行回测"):
            sym = bt_coin + "-USD"
            df_bt = yf.download(sym, period="2y", interval="1d", progress=False)
            if isinstance(df_bt.columns, pd.MultiIndex):
                df_bt.columns = df_bt.columns.droplevel(1)
            df_bt = df_bt.dropna()
            cash = 10000
            position = 0
            equity = []
            for i in range(60, len(df_bt)):
                sub = df_bt.iloc[:i+1]
                res = analyze_coin(sub, sym)
                price = float(sub["Close"].iloc[-1])
                if res and res["信号"] == "买入" and position == 0:
                    position = cash / price
                    cash = 0
                elif res and res["信号"] == "卖出" and position > 0:
                    cash = position * price
                    position = 0
                equity.append(cash + position * price)
            if equity:
                ret = (equity[-1] / 10000 - 1) * 100
                st.metric("近2年模拟收益", f"{ret:.1f}%")
                st.line_chart(equity)
                st.caption("回测为简化版，仅供参考，未计入手续费滑点。")

else:
    st.info("请在左侧选择币种后点击「开始筛选」")

st.markdown("---")
st.caption("数据来源：CoinGecko + Yahoo Finance。仅供学习研究，不构成投资建议。")
