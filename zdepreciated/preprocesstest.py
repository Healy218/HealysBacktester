import pandas as pd
from zdepreciated.data_preprocessingAV import clean_data, feature_engineer

# Load the 5-minute data
df_5min = pd.read_csv('data/SPY_5min.csv', index_col=0)
df_5min.index.name = 'timestamp'  # Rename the index
df_5min_cleaned = clean_data(df_5min.copy())
df_5min_engineered = feature_engineer(df_5min_cleaned.copy())
print("First 50 Rows of 5-Minute Data Engineered:")
print(df_5min_engineered.head(50))
print("-" * 50)

# Load the daily data
df_daily = pd.read_csv('data/SPY_daily.csv', index_col=0)
df_daily.index.name = 'timestamp'
df_daily_cleaned = clean_data(df_daily.copy())
df_daily_engineered = feature_engineer(df_daily_cleaned.copy())
print("First 50 Rows of Daily Data Engineered:")
print(df_daily_engineered.head(50))
print("-" * 50)

# Load the weekly data
df_weekly = pd.read_csv('data/SPY_weekly.csv', index_col=0)
df_weekly.index.name = 'timestamp'
df_weekly_cleaned = clean_data(df_weekly.copy())
df_weekly_engineered = feature_engineer(df_weekly_cleaned.copy())
print("First 50 Rows of Weekly Data Engineered:")
print(df_weekly_engineered.head(50))