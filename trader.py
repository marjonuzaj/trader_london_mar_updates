from structures import TraderModel
from uuid import uuid4


class Trader:
    def __str__(self):
        return f'{self.data}'

    def __init__(self, cash: float, stocks: int):
        self.id = uuid4()  # Generate a new UUID
        self.data = TraderModel(id=self.id, cash=cash, stocks=stocks)
