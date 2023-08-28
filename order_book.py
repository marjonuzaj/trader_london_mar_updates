from typing import List, Union
from structures import OrderBookModel, Order, Error, OrderStatus
from uuid import UUID, uuid4
from typing import Optional
from utils import utc_now


class OrderBook:
    data: OrderBookModel = None

    def __init__(self, active_book: List[Order]):
        self.data = active_book

    def get_current_spread(self) -> Optional[float]:
        # Filter out active bid and ask orders
        bid_orders = [order.price for order in self.data if
                      order.order_type == 'bid' and order.order_status == OrderStatus.ACTIVE]
        ask_orders = [order.price for order in self.data if
                      order.order_type == 'ask' and order.order_status == OrderStatus.ACTIVE]

        if not bid_orders or not ask_orders:
            return None  # Spread can't be calculated if there are no active bids or asks

        # Find the best bid and best ask
        best_bid = max(bid_orders)
        best_ask = min(ask_orders)

        # Calculate the spread
        spread = best_bid - best_ask
        return spread

    def cancel_order(self, order_id: UUID) -> Union[Order, Error]:
        """
        Cancel an order by its ID
        I am not sure if this is the right place (in OrderBook) to put this method. I think it should be in TradingSession.
        But for now let's leave it here, not to overload TradingSession with too many methods.
        """
        # Find the order by its ID
        print('WITHING')
        print(self.data)
        print('*' * 100)
        order_to_cancel = next((order for order in self.data if order.id == order_id), None)

        if not order_to_cancel:
            return Error(message="Order not found", created_at=utc_now())

        if not order_to_cancel.order_status == OrderStatus.ACTIVE:
            return Error(message="Order is already inactive", created_at=utc_now())

        # Mark the order as inactive
        order_to_cancel.order_status = OrderStatus.CANCELLED

        # Remove the order from the active_book
        self.data.remove(order_to_cancel)

        return order_to_cancel  # Return the cancelled order
