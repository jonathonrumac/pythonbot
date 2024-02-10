import os
import time
import pandas as pd
from binance.client import Client
import backtrader as bt

# REPLACE with your actual API keys (NEVER share these publicly)
API_KEY = 'MYKEY'
API_SECRET = 'MYSECRET'

# Initialize Binance client
client = Client(API_KEY, API_SECRET)

class DoubleMovingAverageStrategy(bt.Strategy):
    params = (
        ('short_period', [5, 10]),  # Shorter periods for more reactive trades
        ('long_period', [20, 30]),  # Longer periods for trend confirmation
        ('risk_percentage', 0.1),  # Adjust based on risk tolerance (e.g., 0.05-0.15)
        ('stop_loss_pct', 0.08),  # Dynamic or fixed stop-loss based on risk management
        ('fee_pct', 0.001),  # Consider exchange and trading fees
        ('trailing_stop_pct', 0.05),  # Optional trailing stop for profit protection
        ('hold_period', 10),  # Adjust based on market volatility and strategy (can be dynamic)
        ('coins', []),  # Define target coins (research and diversify)
    )

    def __init__(self):
        # Initialize moving averages for each target coin
        self.sma_short = {}
        self.sma_long = {}
        self.current_position = {}  # Track current position (long/short) for each coin
        self.stop_loss = {}  # Store stop-loss orders for each coin
        self.trailing_stop = {}  # Store trailing stop-loss levels for each coin

        # **Fill in your target coins here:**
        self.params.coins = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']  # Example coins

        for coin in self.params.coins:
            self.sma_short[coin] = bt.indicators.SimpleMovingAverage(self.data[coin].close, period=self.params.short_period)
            self.sma_long[coin] = bt.indicators.SimpleMovingAverage(self.data[coin].close, period=self.params.long_period)
            self.current_position[coin] = None
            self.stop_loss[coin] = None
            self.trailing_stop[coin] = None

    def next(self):
        # Iterate through each target coin
        for coin in self.params.coins:
            # Buy signal (short-term MA above long-term MA and not already long)
            if self.sma_short[coin] > self.sma_long[coin] and self.current_position[coin] != 'long':
                self.buy(size=self.calculate_position_size(coin), data=self.data[coin])
                self.current_position[coin] = 'long'
                self.set_stop_loss(coin, order_type='long')
                if self.params.trailing_stop_pct:  # Optional trailing stop-loss
                    self.set_trailing_stop(coin, order_type='long')

            # Sell signal (long position and hold period over OR short-term MA below long-term MA)
            elif (self.current_position[coin] == 'long' and
                  (self.data.bar_executed - self.buy_bar >= self.params.hold_period or
                   self.sma_short[coin] < self.sma_long[coin])):
                self.sell(size=self.position.size, data=self.data[coin])
                self.current_position[coin] = None
                self.cancel_stop_loss(coin)
                self.cancel_trailing_stop(coin)

            # Short sell signal (short-term MA below long-term MA, portfolio value > $110)
            elif self.sma_short[coin] < self.sma_long[coin] and self.current_position[coin] != 'short' \
                 and self.broker.get_cash() > 110:
                self.sellshort(size=self.calculate_position_size(coin), data=self.data[coin])
                self.current_position[coin] = 'short'
                self.set_stop_loss(coin, order_type='short')
                if self.params.trailing_stop_pct:  # Optional trailing stop-loss
                    self.set_trailing_stop(coin, order_type='short')

    def set_trailing_stop(self, coin, order_type='long'):
        if order_type == 'long':
            self.trailing_stop[coin] = self.data.close * (1 - self.params.trailing_stop_pct)
        elif order_type == 'short':
            self.trailing_stop[coin] = self.data.close * (1 + self.params.trailing_stop_pct)

    def cancel_trailing_stop(self, coin):
        self.trailing_stop[coin] = None

# Run the strategy
if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(DoubleMovingAverageStrategy)

    # Fetch data from Binance (replace 'start' and 'end' with your desired time range)
    start = '2022-01-01'
    end = '2022-12-31'
    interval = Client.KLINE_INTERVAL_1HOUR  # 1-hour interval
    for coin in cerebro.strategy.params.coins:
        df = client.get_historical_klines(coin, interval, start_str=start, end_str=end)
        df = pd.DataFrame(df, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        data = bt.feeds.PandasData(dataname=df)
        cerebro.adddata(data)

    cerebro.run()
