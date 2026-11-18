"""
量化交易模型 - 浏览器交互版（Streamlit）
运行方式：streamlit run streamlit_quant_app.py
"""

import streamlit as st
import yfinance as yf
from backtesting import Strategy
from backtesting.lib import FractionalBacktest
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

st.set_page_config(page_title="加密货币量化交易模型", layout="wide")
st.title("加密货币量化交易模型（浏览器版）")
st.markdown("基于趋势 + RSI + MACD + 成交量的多指标策略")

st.sidebar.header("策略参数")
symbol = st.sidebar.selectbox("交易对", ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"])
period = st.sidebar.selectbox("数据周期", ["1y", "2y", "3y", "5y"], index=2)
cash = st.sidebar.number_input("初始本金（美元）", value=10000, step=1000)

trend_period = st.sidebar.slider("趋势均线周期", 20, 100, 50)
rsi_oversold = st.sidebar.slider("RSI超卖阈值", 30, 55, 48)
stop_loss_pct = st.sidebar.slider("止损比例 (%)", 0.5, 3.0, 1.0) / 100
position_pct = st.sidebar.slider("仓位比例", 0.3, 1.0, 0.8)

run_button = st.sidebar.button("开始回测", type="primary")

def RSI(series, period=14):
    delta = pd.Series(series).diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def MACD(series, fast=12, slow=26, signal=9):
    ema_fast = pd.Series(series).ewm(span=fast, adjust=False).mean()
    ema_slow = pd.Series(series).ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

class BrowserQuantStrategy(Strategy):
    trend_period = 50
    rsi_oversold = 48
    rsi_exit = 55
    vol_threshold = 0.5
    stop_loss_pct = 0.01
    position_pct = 0.8

    def init(self):
        close = self.data.Close
        volume = self.data.Volume
        self.trend_sma = self.I(lambda x: pd.Series(x).rolling(self.trend_period).mean(), close)
        self.rsi = self.I(RSI, close, 14)
        self.macd = self.I(lambda x: MACD(x)[0], close)
        self.macd_signal = self.I(lambda x: MACD(x)[1], close)
        self.vol_ma = self.I(lambda x: pd.Series(x).rolling(20).mean(), volume)

    def next(self):
        price = self.data.Close[-1]
        vol = self.data.Volume[-1]
        in_uptrend = price > self.trend_sma[-1]
        rsi_ok = self.rsi[-1] < self.rsi_oversold
        macd_ok = (self.macd[-1] > self.macd[-2]) or (self.macd[-1] > self.macd_signal[-1])
        vol_ok = vol > self.vol_ma[-1] * self.vol_threshold

        if in_uptrend and rsi_ok and macd_ok and vol_ok and not self.position:
            sl = price * (1 - self.stop_loss_pct)
            self.buy(size=self.position_pct, sl=sl)
        elif self.position:
            if (self.rsi[-1] > self.rsi_exit or price < self.trend_sma[-1] or self.macd[-1] < self.macd_signal[-1]):
                self.position.close()

if run_button:
    with st.spinner("正在下载数据并回测..."):
        try:
            data = yf.download(symbol, period=period, interval="1d", progress=False)
            data = data.dropna()
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.droplevel(1)
            data.columns = [c.capitalize() for c in data.columns]

            BrowserQuantStrategy.trend_period = trend_period
            BrowserQuantStrategy.rsi_oversold = rsi_oversold
            BrowserQuantStrategy.stop_loss_pct = stop_loss_pct
            BrowserQuantStrategy.position_pct = position_pct

            bt = FractionalBacktest(data, BrowserQuantStrategy, cash=cash, commission=0.001, exclusive_orders=True)
            stats = bt.run()

            st.success("回测完成！")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("总收益", f"{stats['Return [%]']:.2f}%")
            col2.metric("胜率", f"{stats['Win Rate [%]']:.1f}%")
            col3.metric("最大回撤", f"{stats['Max. Drawdown [%]']:.2f}%")
            col4.metric("交易次数", f"{stats['# Trades']}")

            st.subheader("详细结果")
            st.text(str(stats))
            st.subheader("权益曲线")
            st.line_chart(stats._equity_curve["Equity"])
        except Exception as e:
            st.error(f"运行出错：{str(e)}")
else:
    st.info("请在左侧调整参数后点击「开始回测」")

st.markdown("---")
st.caption("仅供学习研究使用，历史回测不代表未来表现。")
