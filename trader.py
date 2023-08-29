from structures import TraderModel, Order, Transaction, OrderStatus
from uuid import uuid4, UUID
from typing import List, Optional


class Trader:
    def __str__(self):
        return f'{self.data}'

    def __repr__(self):
        return f'{self.data}'

    def __init__(self, cash: float, stocks: int):
        self.id = uuid4()  # Generate a new UUID
        self.data = TraderModel(id=self.id, cash=cash, stocks=stocks)

    def join_session(self, session_id: UUID):
        self.data.session_id = session_id  # Update session ID when trader joins a session

    def to_dict(self):
        return self.data.model_dump()  # Convert the TraderModel to a dictionary

    def active_orders(self, sessions: dict) -> Optional[List[Order]]:
        session_id = self.data.session_id
        if not session_id:
            return None
        session = sessions.get(session_id)
        if not session:
            return None
        return [order for order in session.session_data.active_book if
                order.trader.id == self.id and order.order_status == OrderStatus.ACTIVE]

    def all_orders(self, sessions: dict) -> Optional[List[Order]]:
        session_id = self.data.session_id
        if not session_id:
            return None
        session = sessions.get(session_id)
        if not session:
            return None
        return [order for order in session.session_data.full_order_history if order.trader.id == self.id]

    def transactions(self, sessions: dict) -> Optional[List[Transaction]]:
        session_id = self.data.session_id
        if not session_id:
            return None
        session = sessions.get(session_id)
        if not session:
            return None
        return [transaction for transaction in session.session_data.transaction_history
                if transaction.buyer_order.trader.id == self.id or transaction.seller_order.trader.id == self.id]
