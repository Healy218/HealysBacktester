# backtester.py
class Backtester:
    def __init__(self, data, strategy, initial_capital, commission):
        self.data = data
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.commission = commission
        self.portfolio = Portfolio(initial_capital)
        self.event_handler = EventHandler()

    def run(self):
        """
        Runs the backtesting simulation.
        """
        # Loop through the historical data
        # Generate signals from the strategy
        # Handle events (orders, portfolio updates)
        # Calculate performance metrics
        pass

    def get_results(self):
        """
        Returns the results of the backtest.
        """
        # Return performance metrics, trade history, etc.
        pass