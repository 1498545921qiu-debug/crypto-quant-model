"""
量化交易模型 - 浏览器交互版（Streamlit）
运行方式：streamlit run streamlit_quant_app.py
然后在浏览器打开显示的地址（通常是 http://localhost:8501）
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
st.markdown("基于趋势 + RSI + MACD + 成交量的多指标策略，可在浏览器中交互使用。")

# ==================== 侧边栏参数 ====================
st.sidebar.header("策略参数")
symbol = st.sidebar.selectbox("交易对", ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"])
period = st.sidebar.selectbox("数据周期", ["1y", "2y", "3y", "5y"], index=2)
cash = st.sidebar.number_input("初始本金（美元）", value=10000, step=1000)

trend_period = st.sidebar.slider("趋势均线周期", 20, 100, 50)
rsi_oversold = st.sidebar.slider("RSI超卖阈值", 30, 55, 48)
stop_loss_pct = st.sidebar.slider("止损比例 (%)", 0.5, 3.0, 1.0) / 100
position_pct = st.sidebar.slider("仓位比例", 0.3, 1.0, 0.8)

run_button = st.sidebar.button("开始回测", type="primary")
optimize_button = st.sidebar.button("优化参数（网格搜索）")

# ==================== 策略定义 ====================
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
            if (self.rsi[-1] > self.rsi_exit or 
                price < self.trend_sma[-1] or 
                self.macd[-1] < self.macd_signal[-1]):
                self.position.close()

# ==================== 主逻辑 ====================
if run_button:
    with st.spinner("正在下载数据并回测，请稍候..."):
        try:
            data = yf.download(symbol, period=period, interval="1d", progress=False)
            data = data.dropna()
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.droplevel(1)
            data.columns = [c.capitalize() for c in data.columns]

            # 动态设置策略参数
            BrowserQuantStrategy.trend_period = trend_period
            BrowserQuantStrategy.rsi_oversold = rsi_oversold
            BrowserQuantStrategy.stop_loss_pct = stop_loss_pct
            BrowserQuantStrategy.position_pct = position_pct

            bt = FractionalBacktest(data, BrowserQuantStrategy, cash=cash, commission=0.001, exclusive_orders=True)
            stats = bt.run()

            st.success("回测完成！")

            # 关键指标展示
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("总收益", f"{stats['Return [%]']:.2f}%")
            col2.metric("胜率", f"{stats['Win Rate [%]']:.1f}%")
            col3.metric("最大回撤", f"{stats['Max. Drawdown [%]']:.2f}%")
            col4.metric("交易次数", f"{stats['# Trades']}")

            st.subheader("详细回测结果")
            st.text(str(stats))

            # 权益曲线
            st.subheader("权益曲线")
            equity = stats._equity_curve["Equity"]
            st.line_chart(equity)

        except Exception as e:
            st.error(f"运行出错：{e}")
else:
    st.info("请在左侧调整参数后，点击「开始回测」按钮。")

# ==================== 参数优化 ====================
if optimize_button:
    with st.spinner("正在进行参数网格搜索（可能需要1-2分钟）..."):
        try:
            data = yf.download(symbol, period=period, interval="1d", progress=False)
            data = data.dropna()
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.droplevel(1)
            data.columns = [c.capitalize() for c in data.columns]

            bt = FractionalBacktest(data, BrowserQuantStrategy, cash=cash, commission=0.001, exclusive_orders=True)
            
            # 网格搜索关键参数
            stats, heatmap = bt.optimize(
                trend_period=range(30, 81, 10),
                rsi_oversold=range(35, 56, 5),
                stop_loss_pct=[0.008, 0.01, 0.015, 0.02],
                maximize='Win Rate [%]',   # 以胜率为优化目标（也可改为 'Return [%]' 或 'Sharpe Ratio'）
                constraint=lambda p: p.rsi_oversold < 60,
                return_heatmap=True
            )

            st.success("参数优化完成！")
            st.subheader("最优参数组合（以胜率为目标）")
            st.write(f"**趋势均线周期**: {stats._strategy.trend_period}")
            st.write(f"**RSI超卖阈值**: {stats._strategy.rsi_oversold}")
            st.write(f"**止损比例**: {stats._strategy.stop_loss_pct*100:.1f}%")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("最优胜率", f"{stats['Win Rate [%]']:.1f}%")
            col2.metric("对应收益", f"{stats['Return [%]']:.2f}%")
            col3.metric("最大回撤", f"{stats['Max. Drawdown [%]']:.2f}%")
            col4.metric("交易次数", f"{stats['# Trades']}")

            st.subheader("最优参数下的详细结果")
            st.text(str(stats))

            if heatmap is not None:
                st.subheader("参数热力图（胜率）")
                st.dataframe(heatmap.round(2))

        except Exception as e:
            st.error(f"优化过程出错：{e}")

st.markdown("---")
st.caption("本工具仅供学习与研究使用。历史回测不代表未来表现，请注意风险。")
