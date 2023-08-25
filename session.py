from typing import List
from structures import Trader, Order, TradingSessionModel, Transaction


class TradingSession:
    def __init__(self):
        self.session_data = TradingSessionModel()

    def connect_trader(self, trader: Trader):
        self.session_data.active_traders.append(trader)

    def place_order(self, order: Order):
        if self.check_order_validity(order):
            self.session_data.active_book.append(order)

    def check_order_validity(self, order: Order) -> bool:
        # Validation logic here...
        pass

    def create_transaction(self, buyer_order: Order, seller_order: Order, quantity: int, price: float):
        # Mark the orders as fulfilled
        buyer_order.active = False
        seller_order.active = False

        # Remove the orders from the active order book
        self.session_data.active_book = [order for order in self.session_data.active_book if order.active]

        # Create the transaction
        transaction = Transaction(buyer_order=buyer_order, seller_order=seller_order, quantity=quantity, price=price)
        self.session_data.transaction_history.append(transaction)

    # ...
