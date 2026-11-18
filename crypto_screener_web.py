"""
加密货币自动筛选 - 完整版
恢复：市值前列币种 + 板块叙事
保留：自动做多/做空信号（趋势+CVD+资金费率）
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="加密货币自动信号", layout="wide")
st.title("加密货币自动做多/做空信号")
st.caption("自动扫描 · 板块叙事 · 资金费率 · 小时CVD · 趋势")

@st.cache_data(ttl=3600)
def get_top_coins(limit=60):
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": limit, "page": 1}
        data = requests.get(url, params=params, timeout=12).json()
        coins = []
        for c in data:
            sym = c["symbol"].upper() + "-USD"
            name = c.get("name", "").lower()
            narr = "其他"
            if any(k in name for k in ["ai", "artificial", "agent"]):
                narr = "AI"
            elif any(k in name for k in ["meme", "dog", "pepe", "inu", "frog", "cat"]):
                narr = "Meme"
            elif any(k in name for k in ["depin", "physical"]):
                narr = "DePIN"
            elif any(k in name for k in ["restak", "eigen"]):
                narr = "Restaking"
            elif any(k in name for k in ["defi", "swap", "lend"]):
                narr = "DeFi"
            coins.append({"symbol": sym, "narrative": narr, "name": c.get("name", sym)})
        return coins
    except:
        return [{"symbol": s, "narrative": "其他", "name": s} for s in ["BTC-USD", "ETH-USD", "SOL-USD"]]

def get_funding(symbol):
    try:
        pair = symbol.replace("-USD", "") + "USDT"
        fr = requests.get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={pair}&limit=1", timeout=6).json()
        return float(fr[0]["fundingRate"]) * 100 if fr else 0
    except:
        return 0

def get_hourly_cvd(symbol):
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

def analyze(symbol, narrative):
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
        cvd = get_hourly_cvd(symbol)

        if trend_up and cvd > 0 and funding < 0.08:
            signal = "做多"
            reason = "趋势上 + CVD流入 + 费率正常"
        elif trend_down and cvd < 0 and funding > -0.05:
            signal = "做空"
            reason = "趋势下 + CVD流出 + 费率正常"
        else:
            signal = "观望"
            reason = "-"

        return {
            "币种": symbol.replace("-USD", ""),
            "板块": narrative,
            "最新价": round(price, 4),
            "信号": signal,
            "依据": reason,
            "资金费率%": round(funding, 4),
            "小时CVD": f"{cvd/1e6:+.1f}M"
        }
    except:
        return None

# 侧边栏
st.sidebar.header("自动扫描设置")
top_n = st.sidebar.slider("扫描市值前 N 名", 20, 80, 40)
coin_data = get_top_coins(top_n)
narratives = sorted(set(c["narrative"] for c in coin_data))
sel_narr = st.sidebar.multiselect("板块筛选", narratives, default=narratives)
only_signal = st.sidebar.checkbox("只显示做多/做空", value=True)

filtered = [c for c in coin_data if c["narrative"] in sel_narr]
selected = st.sidebar.multiselect(
    "确认扫描列表",
    [c["symbol"] for c in filtered],
    default=[c["symbol"] for c in filtered[:15]]
)

if st.sidebar.button("开始自动筛选", type="primary"):
    progress = st.progress(0)
    results = []
    narr_map = {c["symbol"]: c["narrative"] for c in coin_data}
    for i, sym in enumerate(selected):
        res = analyze(sym, narr_map.get(sym, "其他"))
        if res:
            results.append(res)
        progress.progress((i + 1) / max(len(selected), 1))
    progress.empty()

    df = pd.DataFrame(results)
    if only_signal and not df.empty:
        df = df[df["信号"].isin(["做多", "做空"])]

    if not df.empty:
        def color(val):
            if val == "做多": return "background-color:#d4edda"
            if val == "做空": return "background-color:#f8d7da"
            return ""
        st.subheader(f"符合条件结果（{len(df)} 个）")
        cols = ["币种", "板块", "最新价", "信号", "依据", "资金费率%", "小时CVD"]
        st.dataframe(df[cols].style.map(color, subset=["信号"]), use_container_width=True, hide_index=True)
    else:
        st.warning("当前扫描范围内没有符合做多/做空条件的币种")

st.caption("信号规则：做多 = 站上20日均线 + 小时CVD为正 + 资金费率<0.08%；做空 = 低于20日均线 + 小时CVD为负 + 资金费率>-0.05%。板块来自名称关键词匹配。仅供研究。")
