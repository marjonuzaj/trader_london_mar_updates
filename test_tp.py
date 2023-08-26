from session import TradingSession
from trader import Trader
from pprint import pprint
# Create two traders

trader1 = Trader(cash=100, stocks=1)
trader2 = Trader(cash=200, stocks=2)
# Usage
# Create a trader and a trading session

session = TradingSession()

# # Connect the trader to the session
session.connect_trader(trader1)
session.connect_trader(trader2)
#
# # Retrieve the trader by UUID
retrieved_trader = session.get_trader(trader1.data.id)
print(retrieved_trader)
#
#
#
#
#
# # Trader1 places a bid order
bid_order_result = session.place_order(trader_id=trader1.id, order_type="bid", quantity=1, price=50)

#
# # Trader2 places an ask order
ask_order_result = session.place_order(trader_id=trader2.id, order_type="ask", quantity=1, price=40)
pprint(session.session_data.active_book)
#
# # Check for matching orders and create transactions
# session.match_orders()