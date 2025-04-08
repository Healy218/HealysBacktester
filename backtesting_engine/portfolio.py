# portfolio.py
class Portfolio:
    def __init__(self, initial_capital):
        self.cash = initial_capital
        self.positions = {}
        self.trade_history = {}

    def update(self, symbol, quantity, price, commission):
        """
        Updates the portfolio based on a trade.
        """
        # Update cash balance
        # Update position for the symbol
        # Add trade to history
        pass

    def get_value(self, current_prices):
        """
        Calculates the current value of the portfolio.
        """
        # Calculate value of holdings
        # Add cash balance
        return total_value