# test_strategies.py
import pandas as pd
from moving_average_crossover import MovingAverageCrossover
from rsi_strategy import RSIStrategy
from data.data_preprocessing import clean_data, feature_engineer

# Load the data
df_5min = pd.read_csv('data/SPY_5min.csv', index_col=0)
df_5min.index.name = 'timestamp'
df_5min_cleaned = clean_data(df_5min.copy())
df_5min_engineered = feature_engineer(df_5min_cleaned.copy())

df_daily = pd.read_csv('data/SPY_daily.csv', index_col=0)
df_daily.index.name = 'timestamp'
df_daily_cleaned = clean_data(df_daily.copy())
df_daily_engineered = feature_engineer(df_daily_cleaned.copy())

df_weekly = pd.read_csv('data/SPY_weekly.csv', index_col=0)
df_weekly.index.name = 'timestamp'
df_weekly_cleaned = clean_data(df_weekly.copy())
df_weekly_engineered = feature_engineer(df_weekly_cleaned.copy())

print("-" * 50)
print("Testing Moving Average Crossover Strategy (5-Minute Data):")
short_window = 20
long_window = 50
ma_strategy_5min = MovingAverageCrossover(df_5min_engineered.copy(), short_window, long_window)
ma_strategy_5min.generate_signals()
print(ma_strategy_5min.data[['Short_MA', 'Long_MA', 'Signal']].head(60))

print("-" * 50)
print("Testing RSI Strategy (Daily Data):")
rsi_period = 14
overbought_level = 70
oversold_level = 30
rsi_strategy_daily = RSIStrategy(df_daily_engineered.copy(), rsi_period, overbought_level, oversold_level)
rsi_strategy_daily.generate_signals()
print(rsi_strategy_daily.data[['RSI', 'Signal']].head(30))

print("-" * 50)
print("Testing Moving Average Crossover Strategy (Weekly Data):")
ma_strategy_weekly = MovingAverageCrossover(df_weekly_engineered.copy(), short_window, long_window)
ma_strategy_weekly.generate_signals()
print(ma_strategy_weekly.data[['Short_MA', 'Long_MA', 'Signal']].head(60))

print("-" * 50)
print("Testing RSI Strategy (Weekly Data):")
rsi_strategy_weekly = RSIStrategy(df_weekly_engineered.copy(), rsi_period, overbought_level, oversold_level)
rsi_strategy_weekly.generate_signals()
print(rsi_strategy_weekly.data[['RSI', 'Signal']].head(30))