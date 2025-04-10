# Purpose: Extract and display key performance metrics from a vectorbt portfolio.

function get_summary_stats(portfolio):
  # INPUT: vectorbt Portfolio object
  # OUTPUT: Dictionary (or pandas Series/DataFrame) of performance stats

  stats = {
      "Start Date": portfolio.stats['Start'],
      "End Date": portfolio.stats['End'],
      "Period": portfolio.stats['Period'],
      "Initial Capital": portfolio.init_cash,
      "Final Value": portfolio.final_value(),
      "Total Return [%]": portfolio.total_return() * 100,
      "Sharpe Ratio": portfolio.sharpe_ratio(),
      "Max Drawdown [%]": portfolio.max_drawdown() * 100,
      "Total Trades": portfolio.trades.count(),
      "Win Rate [%]": portfolio.trades.win_rate() * 100,
      # Add more stats as needed from portfolio.stats() or specific methods
  }
  return stats

end function

function display_metrics(stats_dict):
  # INPUT: Dictionary of stats from get_summary_stats
  # OUTPUT: Prints formatted stats to console

  print("--- Backtest Performance Metrics ---")
  for key, value in stats_dict.items():
    # Format numbers nicely (e.g., percentages, decimals)
    print(f"{key}: {format_value(value)}")
  print("------------------------------------")

end function

function get_trade_records(portfolio):
    # INPUT: vectorbt Portfolio object
    # OUTPUT: pandas DataFrame of readable trade records
    return portfolio.trades.records_readable

end function
