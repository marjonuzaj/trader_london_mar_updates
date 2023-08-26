from typing import List, Union
from structures import Trader, Order, TradingSessionModel, Transaction, Error
from uuid import UUID, uuid4


class TradingSession:
    def __init__(self):
        self.session_data = TradingSessionModel()
        self.traders = {}  # Dictionary to hold Trader instances

    def connect_trader(self, trader: Trader):
        self.session_data.active_traders.append(trader.data.id)
        self.traders[trader.data.id] = trader  # Add the Trader instance to the dictionary

    def get_trader(self, trader_id: UUID) -> Trader:
        return self.traders.get(trader_id, None)  # Fetch the Trader instance by UUID

    def place_order(self, trader_id: UUID, order_type: str, quantity: int, price: float) -> Union[Order, Error]:
        trader = next((t for t in self.session_data.active_traders if t.id == trader_id), None)
        if not trader:
            return Error(message="Trader not found")

        if order_type == "bid":
            required_cash = price * quantity
            if trader.cash - trader.blocked_cash < required_cash:
                return Error(message="Not enough cash for bid")
            trader.blocked_cash += required_cash  # Block the cash

        if order_type == "ask":
            if trader.stocks - trader.blocked_stocks < quantity:
                return Error(message="Not enough stocks for ask")
            trader.blocked_stocks += quantity  # Block the stocks

        # Create the order
        order = Order(trader=trader, order_type=order_type, quantity=quantity, price=price)
        self.session_data.active_book.append(order)
        self.session_data.full_order_history.append(order)

        return order

    def check_order_validity(self, order: Order) -> bool:
        # Validation logic here...
        pass

    def create_transaction(self, buyer_order: Order, seller_order: Order, quantity: int, price: float):
        buyer_order.active = False
        seller_order.active = False

        # Update portfolios
        transaction_value = quantity * price
        buyer_order.trader.cash -= transaction_value
        buyer_order.trader.stocks += quantity
        buyer_order.trader.blocked_cash -= transaction_value  # Unblock the cash

        seller_order.trader.cash += transaction_value
        seller_order.trader.stocks -= quantity
        seller_order.trader.blocked_stocks -= quantity  # Unblock the stocks

        # Remove fulfilled orders from the active book
        self.session_data.active_book = [order for order in self.session_data.active_book if order.active]

        # Create and record the transaction
        transaction = Transaction(buyer_order=buyer_order, seller_order=seller_order, quantity=quantity, price=price)
        self.session_data.transaction_history.append(transaction)
