from structures import TraderModel
from uuid import uuid4, UUID


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
