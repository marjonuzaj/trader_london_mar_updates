from fastapi import FastAPI, HTTPException
from uuid import UUID
from session import TradingSession  # Replace 'your_project_name' with your actual module name
from trader import Trader
from structures import CreatingTraderModel, ConnectingTraderModel
from typing import List, Dict, Any

app = FastAPI()

# In-memory data stores (Replace these with databases in production)
traders = {}
sessions = {}


@app.post("/create_trader/")
def create_trader(trader: CreatingTraderModel):
    new_trader = Trader(cash=trader.cash, stocks=trader.stocks)
    traders[new_trader.id] = new_trader
    return {"trader_id": new_trader.id}


@app.get("/get_traders/")
def get_traders():
    return {str(trader_id): trader.to_dict() for trader_id, trader in traders.items()}


@app.post("/create_session/")
def create_session():
    new_session = TradingSession()
    sessions[new_session.id] = new_session
    return {"session_id": new_session.id}
@app.get("/get_sessions/")
def get_sessions():
    return {str(session_id): session.to_dict() for session_id, session in sessions.items()}
@app.post("/connect_trader/")
def connect_trader(info: ConnectingTraderModel):
    trader = traders.get(info.trader_id)
    session = sessions.get(info.session_id)

    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Assuming you have a method to check if a trader is already connected
    if session.is_trader_connected(trader):
        raise HTTPException(status_code=400, detail="Trader already connected to session")

    try:
        session.connect_trader(trader)
    except Exception as e:
        # Replace 'Exception' with a more specific exception type if possible
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": "Trader connected to session"}


@app.post("/place_order/")
def place_order(trader_id: UUID, session_id: UUID, order_type: str, quantity: int, price: float):
    trader = traders.get(trader_id)
    session = sessions.get(session_id)

    if not trader or not session:
        raise HTTPException(status_code=404, detail="Trader or Session not found")

    order_result = session.place_order(trader_id=trader_id, order_type=order_type, quantity=quantity, price=price)
    return {"order_result": order_result}
