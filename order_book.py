from typing import List, Union
from structures import OrderBookModel, Order, Error
from uuid import UUID, uuid4
from typing import Optional
from utils import  utc_now

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

    def cancel_order(self, order_id: UUID) -> Union[Order, Error]:
        # Find the order by its ID
        order_to_cancel = next((order for order in self.data.active_book if order.id == order_id), None)

        if not order_to_cancel:
            return Error(message="Order not found", created_at=utc_now())

        if not order_to_cancel.active:
            return Error(message="Order is already inactive", created_at=utc_now())

        # Mark the order as inactive
        order_to_cancel.active = False

        # Remove the order from the active_book
        self.data.active_book.remove(order_to_cancel)

        return order_to_cancel  # Return the cancelled order
