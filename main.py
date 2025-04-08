# main.py
from data.data_loader import load_stock_data, load_crypto_data
from data.data_preprocessing import clean_data, feature_engineer
from strategies.moving_average_crossover import MovingAverageCrossover
from backtesting_engine.backtester import Backtester
from analysis.performance_metrics import calculate_sharpe_ratio, calculate_max_drawdown
from analysis.visualizations import plot_equity_curve
from config.backtesting_config import INITIAL_CAPITAL, COMMISSION_PER_TRADE, START_DATE, END_DATE, STOCK_SYMBOLS, CRYPTO_SYMBOLS

if __name__ == "__main__":
    # Load data
    stock_data_raw = {symbol: load_stock_data(symbol, START_DATE, END_DATE) for symbol in STOCK_SYMBOLS}
    crypto_data_raw = {symbol: load_crypto_data(symbol, START_DATE, END_DATE) for symbol in CRYPTO_SYMBOLS}

    # Preprocess data
    stock_data_cleaned = {symbol: clean_data(df) for symbol, df in stock_data_raw.items()}
    crypto_data_cleaned = {symbol: clean_data(df) for symbol, df in crypto_data_raw.items()}

    stock_data_engineered = {symbol: feature_engineer(df) for symbol, df in stock_data_cleaned.items()}
    crypto_data_engineered = {symbol: feature_engineer(df) for symbol, df in crypto_data_cleaned.items()}

    # Define strategy parameters
    short_window = 20
    long_window = 50

    # Initialize and run backtester for stocks
    for symbol, data in stock_data_engineered.items():
        strategy = MovingAverageCrossover(data, short_window, long_window)
        backtester = Backtester(data, strategy, INITIAL_CAPITAL, COMMISSION_PER_TRADE)
        backtester.run()
        results = backtester.get_results()
        sharpe = calculate_sharpe_ratio(results['returns'])
        drawdown = calculate_max_drawdown(results['equity_curve'])
        print(f"Stock: {symbol}, Sharpe Ratio: {sharpe}, Max Drawdown: {drawdown}")
        plot_equity_curve(results['equity_curve'])

    # Initialize and run backtester for crypto
    for symbol, data in crypto_data_engineered.items():
        strategy = MovingAverageCrossover(data, short_window, long_window)
        backtester = Backtester(data, strategy, INITIAL_CAPITAL, COMMISSION_PER_TRADE)
        backtester.run()
        results = backtester.get_results()
        sharpe = calculate_sharpe_ratio(results['returns'])
        drawdown = calculate_max_drawdown(results['equity_curve'])
        print(f"Crypto: {symbol}, Sharpe Ratio: {sharpe}, Max Drawdown: {drawdown}")
        plot_equity_curve(results['equity_curve'])

    # Pseudo-code for integrating and using the neural network for optimization