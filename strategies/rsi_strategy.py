# rsi_strategy.py
from .base_strategy import BaseStrategy
import pandas as pd
import talib

class RSIStrategy(BaseStrategy):
    def __init__(self, data, rsi_period, overbought_level, oversold_level):
        super().__init__(data)
        self.rsi_period = rsi_period
        self.overbought_level = overbought_level
        self.oversold_level = oversold_level

    def generate_signals(self):
        """
        Generates buy/sell signals based on RSI levels.
        """
        if '4. close' not in self.data.columns:
            print("Error: '4. close' column not found in data.")
            return

        close_prices = pd.to_numeric(self.data['4. close'], errors='coerce').dropna()

        # Calculate RSI
        if len(close_prices) >= self.rsi_period:
            self.data['RSI'] = talib.RSI(close_prices.values, timeperiod=self.rsi_period)
        else:
            print(f"Warning: Not enough data to calculate RSI with period {self.rsi_period}.")
            return

        # Create signals
        signals = pd.Series(index=self.data.index)
        signals[:] = 0  # Initialize with no signals

        # Generate buy signal when RSI crosses below oversold level
        signals[(self.data['RSI'].shift(1) >= self.oversold_level) & (self.data['RSI'] < self.oversold_level)] = 1

        # Generate sell signal when RSI crosses above overbought level
        signals[(self.data['RSI'].shift(1) <= self.overbought_level) & (self.data['RSI'] > self.overbought_level)] = -1

        # Store signals in the data DataFrame
        self.data['Signal'] = signals

        # For demonstration purposes, let's print the signals
        print("Generated RSI Signals:")
        print(self.data[self.data['Signal'] != 0][['RSI', 'Signal']].head())