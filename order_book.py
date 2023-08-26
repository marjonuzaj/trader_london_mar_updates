from typing import List, Union
from structures import   OrderBookModel
from uuid import UUID, uuid4


class OrderBook:
    def __init__(self):
        self.data = OrderBookModel()