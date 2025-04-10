# Purpose: Generate plots from vectorbt portfolio results or signal data.

# Note: vectorbt plotting often requires matplotlib. Ensure it's installed.
# You might need to handle plot display (e.g., plt.show() or saving figures).

function plot_portfolio_summary(portfolio):
  # INPUT: vectorbt Portfolio object
  # OUTPUT: Displays vectorbt's default portfolio plot

  print("Generating portfolio summary plot...")
  portfolio.plot().show() # .show() displays the plot

end function

function plot_signals(price_df, entries, exits, short_ma=None, long_ma=None):
  # INPUT: Price DataFrame, entry/exit Series, optional indicator Series
  # OUTPUT: Displays a plot of price with entry/exit markers and indicators

  print("Generating signals plot...")
  # Use vectorbt's plotting capabilities or build manually with matplotlib/plotly
  # Example using vectorbt plotting:
  price_df['Close'].vbt.plot(
      trace_kwargs=dict(name='Close Price'),
      fig=None # Start a new figure
  ).add_signals(
      entries=entries,
      exits=exits,
      # Optional: Add indicator plots
      # plot_kwargs=dict(add_trace_kwargs=dict(name='Indicator')) # Example
  ).show()

  # Example adding MAs manually if needed (assuming using matplotlib)
  # fig, ax = plt.subplots()
  # ax.plot(price_df.index, price_df['Close'], label='Close')
  # if short_ma is not None: ax.plot(short_ma.index, short_ma, label='Short MA')
  # if long_ma is not None: ax.plot(long_ma.index, long_ma, label='Long MA')
  # ax.plot(price_df.index[entries], price_df['Close'][entries], '^', markersize=10, color='g', label='Buy Signal')
  # ax.plot(price_df.index[exits], price_df['Close'][exits], 'v', markersize=10, color='r', label='Sell Signal')
  # ax.legend()
  # plt.show()

end function