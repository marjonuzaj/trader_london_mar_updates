from fastapi import FastAPI, HTTPException, WebSocket
from uuid import UUID
from session import TradingSession  # Replace 'your_project_name' with your actual module name
from traders import Trader
from structures import CreatingTraderModel, ConnectingTraderModel, NewOrderRequest
from typing import List, Dict, Any
from pprint import pprint
app = FastAPI()

# In-memory data stores (Replace these with databases in production)
traders = {}
sessions = {}

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

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

    # Assuming you have a method to check if a traders is already connected
    if session.is_trader_connected(trader):
        raise HTTPException(status_code=400, detail="Trader already connected to session")

    try:
        session.connect_trader(trader)
    except Exception as e:
        # Replace 'Exception' with a more specific exception type if possible
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": "Trader connected to session"}


@app.post("/place_order/")
def place_order(new_order: NewOrderRequest):
    trader_id = new_order.trader_id
    order_type = new_order.order_type
    quantity = new_order.quantity
    price = new_order.price
    trader = traders.get(new_order.trader_id)
    session = sessions.get(new_order.session_id)

    if not trader or not session:
        raise HTTPException(status_code=404, detail="Trader or Session not found")
        # Check if traders has a session_id
    if trader.data.session_id is None:
        raise HTTPException(status_code=400, detail="Trader not connected to any session")

    order_result = session.place_order(trader_id=trader_id, order_type=order_type, quantity=quantity, price=price)
    return {"order_result": order_result}




# 1. Get all currently connected traders for a given session_id
@app.get("/session/{session_id}/traders/")
def get_connected_traders(session_id: UUID) -> List[str]:
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return [str(trader) for trader in session.session_data.active_traders]

# 2. Get the active book for a given session_id
@app.get("/session/{session_id}/active_book/")
def get_active_book(session_id: UUID):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.session_data.active_book

# 3. Get all active orders for a given traders
@app.get("/trader/{trader_id}/active_orders/")
def get_active_orders(trader_id: UUID):
    trader = traders.get(trader_id)
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
    # Assuming traders has an 'active_orders' attribute
    return trader.active_orders(sessions)

# 4. Get all orders for a given traders
@app.get("/trader/{trader_id}/all_orders/")
def get_all_orders(trader_id: UUID):
    trader = traders.get(trader_id)
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
    # this is not an ideal solution. We pass the entire set of sessions there. But when we move from in-memory data to a database we'll have to change this
    # lets add it to TODO list
    return trader.all_orders(sessions)

# 5. Get all transactions for a given traders
@app.get("/trader/{trader_id}/transactions/")
def get_all_transactions(trader_id: UUID):
    trader = traders.get(trader_id)
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")

    return trader.transactions(sessions)


@app.get("/session/{session_id}/transaction_history/")
def get_transaction_history(session_id: UUID):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.session_data.transaction_history  # Assuming the transaction history is stored here


# WebSocket connection pool
active_connections: List[WebSocket] = []
@app.websocket("/ws/{trader_id}")
async def websocket_endpoint(websocket: WebSocket, trader_id: str):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle received data (Optional)
            # Broadcast updates to all connected clients
            for connection in active_connections:
                await connection.send_text(f"Update: {data}")
    except:
        active_connections.remove(websocket)
