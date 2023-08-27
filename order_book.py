from typing import List, Union
from structures import OrderBookModel
from uuid import UUID, uuid4
from typing import Optional


class OrderBook:
    def __init__(self):
        self.data = OrderBookModel()

    def get_current_spread(self) -> Optional[float]:
        # Filter out active bid and ask orders
        bid_orders = [order.price for order in self.active_book if order.order_type == 'bid' and order.active]
        ask_orders = [order.price for order in self.active_book if order.order_type == 'ask' and order.active]

        if not bid_orders or not ask_orders:
            return None  # Spread can't be calculated if there are no active bids or asks

        # Find the best bid and best ask
        best_bid = max(bid_orders)
        best_ask = min(ask_orders)

        # Calculate the spread
        spread = best_bid - best_ask
        return spread
