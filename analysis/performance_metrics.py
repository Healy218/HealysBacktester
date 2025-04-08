# performance_metrics.py
import numpy as np

def calculate_sharpe_ratio(returns, risk_free_rate=0.02):
    """
    Calculates the Sharpe Ratio.
    """
    excess_returns = returns - risk_free_rate / np.sqrt(252) # Assuming daily returns
    sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns)
    return sharpe_ratio

def calculate_max_drawdown(equity_curve):
    """
    Calculates the maximum drawdown.
    """
    # Calculate cumulative returns
    # Find the peak equity value
    # Calculate drawdown as the percentage drop from the peak
    # Return the maximum drawdown
    pass

# Pseudo-code for other performance metrics (Sortino Ratio, annualized returns, etc.)