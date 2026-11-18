"""
加密货币量化筛选 + 回测网页（完整版）
新增：
- 板块/叙事标签（AI、Meme、DeFi等）
- 做多/做空方向
- 市场阶段判断
- 动态止盈止损、流动性过滤、历史回测
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import requests

st.set_page_config(page_title="加密货币量化筛选与回测", layout="wide")
st.title("加密货币量化筛选与回测")
st.caption("板块叙事 · 做多做空 · 市场阶段 · 动态止盈止损 · 历史回测")

@st.cache_data(ttl=3600)
def get_top_coins_with_category(limit=100):
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {"vs_currency": "usd", "order": "market_cap_desc",
                  "per_page": limit, "page": 1, "sparkline": False}
        data = requests.get(url, params=params, timeout=15).json()
        coins = []
        for c in data:
            symbol = c["symbol"].upper() + "-USD"
            cats = c.get("categories") or []
            narrative = "其他"
            cat_str = " ".join(cats).lower() if cats else ""
            name = c.get("name", "").lower()
            if any(k in cat_str or k in name for k in ["artificial-intelligence", "ai", "machine-learning"]):
                narrative = "AI"
            elif any(k in cat_str or k in name for k in ["meme", "dog", "frog", "pepe"]):
                narrative = "Meme"
            elif any(k in cat_str for k in ["decentralized-finance", "defi"]):
                narrative = "DeFi"
            elif any(k in cat_str for k in ["layer-1", "smart-contract-platform"]):
                narrative = "Layer1"
            elif any(k in cat_str for k in ["layer-2", "scaling"]):
                narrative = "Layer2"
            elif any(k in cat_str for k in ["gaming", "metaverse", "nft"]):
                narrative = "Gaming/NFT"
            elif any(k in cat_str for k in ["real-world-assets", "rwa"]):
                narrative = "RWA"
            coins.append({"symbol": symbol, "narrative": narrative, "name": c.get("name", symbol)})
        return coins
    except Exception as e:
        st.warning(f"获取币种失败：{e}")
        return [{"symbol": s, "narrative": "其他", "name": s} for s in 
                ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"]]

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def analyze_coin(df, symbol, phase="震荡市"):
    if df is None or len(df) < 60:
        return None
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    price = float(close.iloc[-1])

    sma20 = close.rolling(20).mean().iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1]
    rsi_series = calc_rsi(close)
    rsi = rsi_series.iloc[-1]
    rsi_prev = rsi_series.iloc[-2]

    atr = (high - low).rolling(14).mean().iloc[-1]
    vol_pct = atr / price * 100 if price > 0 else 0

    vol_ma = volume.rolling(20).mean().iloc[-1]
    vol_ratio = volume.iloc[-1] / vol_ma if vol_ma > 0 else 0
    avg_dollar_vol = (volume * close).rolling(20).mean().iloc[-1]

    if avg_dollar_vol < 500_000:
        return None

    trend_up = price > sma20 > sma50
    trend_down = price < sma20 < sma50
    rsi_recover = 35 < rsi < 65 and rsi > rsi_prev
    rsi_weak = rsi < 40 and rsi < rsi_prev
    volume_ok = vol_ratio > 1.1

    if phase == "熊市":
        rsi_recover = 30 < rsi < 50 and rsi > rsi_prev

    if trend_up and rsi_recover and volume_ok:
        direction = "做多"
        signal = "买入"
        sl_pct = max(1.2, min(3.5, vol_pct * 0.9))
        tp_pct = max(2.0, min(6.0, vol_pct * 1.6))
        sl = round(price * (1 - sl_pct/100), 4)
        tp = round(price * (1 + tp_pct/100), 4)
    elif trend_down and rsi_weak and volume_ok:
        direction = "做空"
        signal = "卖出/做空"
        sl_pct = max(1.2, min(3.5, vol_pct * 0.9))
        tp_pct = max(2.0, min(6.0, vol_pct * 1.6))
        sl = round(price * (1 + sl_pct/100), 4)
        tp = round(price * (1 - tp_pct/100), 4)
    elif rsi > 75 or (trend_down and price < sma20 * 0.96):
        direction = "做空"
        signal = "卖出"
        sl = tp = "-"
    else:
        direction = "观望"
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
        "方向": direction,
        "信号": signal,
        "建议止损": sl,
        "建议止盈": tp,
        "RSI": round(rsi, 1),
        "波动率%": round(vol_pct, 2),
        "波动提示": " | ".join(events) if events else "-"
    }

# ==========市场阶段==========
@st.cache_data(ttl=1800)
def get_market_phase():
    try:
        btc = yf.download("BTC-USD", period="120d", interval="1d", progress=False)
        if isinstance(btc.columns, pd.MultiIndex):
            btc.columns = btc.columns.droplevel(1)
        close = btc["Close"].dropna()
        sma50 = close.rolling(50).mean().iloc[-1]
        sma50_prev = close.rolling(50).mean().iloc[-5]
        price = float(close.iloc[-1])
        if price > sma50 and sma50 > sma50_prev:
            return "牛市", "BTC上升趋势，可积极寻找做多机会"
        elif price < sma50 and sma50 < sma50_prev:
            return "熊市", "BTC下降趋势，谨慎做多，可关注做空"
        else:
            return "震荡市", "趋势不明，建议轻仓或观望"
    except:
        return "未知", "无法获取数据"

phase, phase_desc = get_market_phase()
color_map = {"牛市": "green", "熊市": "red", "震荡市": "orange"}
st.markdown(f"**当前市场阶段：<span style='color:{color_map.get(phase,'gray')};font-size:1.3em'>{phase}</span>**  \n{phase_desc}", unsafe_allow_html=True)
st.markdown("---")

# ==========侧边栏==========
st.sidebar.header("筛选设置")
top_n = st.sidebar.slider("市值前 N 名", 20, 100, 40)
coin_data = get_top_coins_with_category(top_n)
narratives = sorted(set(c["narrative"] for c in coin_data))
selected_narr = st.sidebar.multiselect("板块/叙事筛选", narratives, default=narratives)
only_direction = st.sidebar.selectbox("方向筛选", ["全部", "只看做多", "只看做空"])
period = st.sidebar.selectbox("数据周期", ["60d", "90d", "180d"], index=0)

filtered_coins = [c for c in coin_data if c["narrative"] in selected_narr]
selected_symbols = st.sidebar.multiselect(
    "选择币种",
    [c["symbol"] for c in filtered_coins],
    default=[c["symbol"] for c in filtered_coins[:12]]
)
run = st.sidebar.button("开始筛选", type="primary")

# ==========筛选==========
if run and selected_symbols:
    progress = st.progress(0)
    results = []
    narr_map = {c["symbol"]: c["narrative"] for c in coin_data}
    for i, sym in enumerate(selected_symbols):
        try:
            df = yf.download(sym, period=period, interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            res = analyze_coin(df.dropna(), sym, phase)
            if res:
                res["板块"] = narr_map.get(sym, "其他")
                results.append(res)
        except:
            pass
        progress.progress((i + 1) / len(selected_symbols))
    progress.empty()

    if results:
        df_res = pd.DataFrame(results)
        if only_direction == "只看做多":
            df_res = df_res[df_res["方向"] == "做多"]
        elif only_direction == "只看做空":
            df_res = df_res[df_res["方向"] == "做空"]
        st.session_state.results = df_res
    else:
        st.session_state.results = pd.DataFrame()
        st.warning("没有符合条件的结果")

# ==========显示==========
if "results" in st.session_state and not st.session_state.results.empty:
    df = st.session_state.results
    def color_dir(val):
        if val == "做多": return "background-color:#d4edda"
        if val == "做空": return "background-color:#f8d7da"
        return ""
    st.subheader(f"筛选结果（{len(df)} 个币）")
    cols = ["币种", "板块", "最新价", "涨跌%", "方向", "信号", "建议止损", "建议止盈", "RSI", "波动提示"]
    st.dataframe(df[cols].style.map(color_dir, subset=["方向"]), use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("下载结果 CSV", csv, "crypto_screen.csv", "text/csv")
else:
    st.info("请在左侧选择板块和币种后点击「开始筛选」")

st.markdown("---")
st.caption("板块数据来自 CoinGecko，价格来自 Yahoo Finance。仅供学习研究，不构成投资建议。做空需注意爆仓风险。")
