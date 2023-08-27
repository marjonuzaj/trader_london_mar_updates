from typing import List, Union
from structures import Order, TradingSessionModel, Transaction, Error
from uuid import UUID, uuid4
from order_book import OrderBook
from trader import Trader
from datetime import datetime, timezone
from utils import utc_now


class TradingSession:
    def __init__(self):
        self.id = uuid4()
        self.session_data = TradingSessionModel(created_at=utc_now(), id=self.id)
        self.created_at = utc_now()
        self.order_book = OrderBook()
        self.traders = {}  # Dictionary to hold Trader instances

    def __str__(self):
        return f'{self.session_data}'

    def is_trader_connected(self, trader: Trader) -> bool:
        trader_ids = [t.id for t in self.session_data.active_traders]
        return trader.id in trader_ids

    def connect_trader(self, trader: Trader):
        trader.data.joined_at = utc_now()
        self.session_data.active_traders.append(trader.data.id)
        self.traders[trader.data.id] = trader  # Add the Trader instance to the dictionary

    def to_dict(self):
        return self.session_data.model_dump()

    def get_trader(self, trader_id: UUID) -> Trader:
        return self.traders.get(trader_id, None)  # Fetch the Trader instance by UUID

    def place_order(self, trader_id: UUID, order_type: str, quantity: int, price: float) -> Union[Order, Error]:
        trader = self.get_trader(trader_id)  # Use the get_trader method to fetch the Trader instance
        if not trader:
            return Error(message="Trader not found", created_at=utc_now())

        if order_type == "bid":
            required_cash = price * quantity
            if trader.data.cash - trader.data.blocked_cash < required_cash:  # Use trader.data to access the fields
                return Error(message="Not enough cash for bid", created_at=utc_now())
            trader.data.blocked_cash += required_cash  # Block the cash

        if order_type == "ask":
            if trader.data.stocks - trader.data.blocked_stocks < quantity:  # Use trader.data to access the fields
                return Error(message="Not enough stocks for ask", created_at=utc_now())
            trader.data.blocked_stocks += quantity  # Block the stocks

        # Create the order
        order = Order(trader=trader.data, order_type=order_type, quantity=quantity,
                      price=price, created_at=utc_now())  # Use trader.data for the Order
        self.session_data.active_book.append(order)
        self.session_data.full_order_history.append(order)
        self.match_orders()

        return order

    def check_order_validity(self, order: Order) -> bool:
        # Validation logic here...
        pass

    def match_orders(self):
        # Sort bid orders in descending order and ask orders in ascending order by price
        bid_orders = sorted([order for order in self.session_data.active_book if order.order_type == "bid"],
                            key=lambda x: x.price, reverse=True)
        ask_orders = sorted([order for order in self.session_data.active_book if order.order_type == "ask"],
                            key=lambda x: x.price)

        # Check for matching orders
        for ask_order in ask_orders:
            for bid_order in bid_orders:
                if bid_order.price >= ask_order.price:
                    # Match found, create a transaction
                    self.create_transaction(buyer_order=bid_order, seller_order=ask_order,
                                            quantity=min(bid_order.quantity, ask_order.quantity), price=ask_order.price)
                    return  # Assuming that one transaction is made at a time, you can return here

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
        transaction = Transaction(buyer_order=buyer_order, seller_order=seller_order, quantity=quantity, price=price,
                                  created_at=utc_now())

        self.session_data.transaction_history.append(transaction)
        print('Transaction created:', transaction.quantity, transaction.price)
        return transaction
