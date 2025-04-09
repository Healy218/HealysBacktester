# moving_average_crossover.py
from .base_strategy import BaseStrategy
import pandas as pd

class MovingAverageCrossover(BaseStrategy):
    def __init__(self, data, short_window, long_window):
        super().__init__(data)
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self):
        """
        Generates buy/sell signals based on moving average crossover.
        """
        # Calculate short-term and long-term moving averages
        if '4. close' not in self.data.columns:
            print("Error: '4. close' column not found in data.")
            return

        close_prices = pd.to_numeric(self.data['4. close'], errors='coerce').dropna()
        short_ma = close_prices.rolling(window=self.short_window, min_periods=self.short_window).mean()
        long_ma = close_prices.rolling(window=self.long_window, min_periods=self.long_window).mean()

        # Create signals
        signals = pd.Series(index=close_prices.index)
        signals[:] = 0  # Initialize with no signals

        # Create short moving average
        self.data['Short_MA'] = short_ma

        # Create long moving average
        self.data['Long_MA'] = long_ma

        # Generate buy signal when short MA crosses above long MA
        signals[(self.data['Short_MA'].shift(1) < self.data['Long_MA'].shift(1)) & (self.data['Short_MA'] > self.data['Long_MA'])] = 1

        # Generate sell signal when short MA crosses below long MA
        signals[(self.data['Short_MA'].shift(1) > self.data['Long_MA'].shift(1)) & (self.data['Short_MA'] < self.data['Long_MA'])] = -1

        # Store signals in the data DataFrame
        self.data['Signal'] = signals

        # For demonstration purposes, let's print the signals
        print("Generated Signals:")
        print(self.data[self.data['Signal'] != 0][['Short_MA', 'Long_MA', 'Signal']].head())