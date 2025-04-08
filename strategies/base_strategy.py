# base_strategy.py
class BaseStrategy:
    def __init__(self, data):
        self.data = data

    def generate_signals(self):
        """
        Generates trading signals based on the data.
        This method should be implemented by subclasses.
        """
        raise NotImplementedError