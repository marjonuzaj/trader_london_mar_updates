from session import TradingSession
from external_traders import Trader
from pprint import pprint
# Create two traders

trader1 = Trader(cash=100, stocks=1)
trader2 = Trader(cash=200, stocks=2)
trader3 = Trader(cash=200, stocks=222)

# Usage
# Create a traders and a trading session

session = TradingSession()

# # Connect the traders to the session
session.connect_trader(trader1)
session.connect_trader(trader2)
session.connect_trader(trader3)


# pprint(session.is_trader_connected(trader1))
#
# # Retrieve the traders by UUID
retrieved_trader = session.get_trader(trader1.data.id)
print(retrieved_trader)
#
#
#
#
#
# # Trader1 places a bid order
bid_order_result1 = session.place_order(trader_id=trader1.id, order_type="bid", quantity=1, price=50)
bid_order_result2 = session.place_order(trader_id=trader1.id, order_type="bid", quantity=1, price=50)
bid_order_result3 = session.place_order(trader_id=trader1.id, order_type="bid", quantity=1, price=50)
print('-'*100)
print('ACTIVE BOOK')
pprint(session.session_data.active_book)
print('-'*100)
# # Trader2 places an ask order
ask_order_result = session.place_order(trader_id=trader2.id, order_type="ask", quantity=1, price=40)


print('-'*100)
print('ACTIVE BOOK')
pprint(session.session_data.active_book)
print('-'*100)

print('-'*100)
print('ORDER HISTORY BOOK')
pprint(session.session_data.full_order_history)
print('-'*100)


print('TRYING TO CANCEL ORDER')
print('-'*100)
pprint(session.session_data.active_book)
print(bid_order_result2.id)
resp=session.order_book.cancel_order(order_id=bid_order_result2.id)
pprint(resp)
print('-'*100)
# pprint(session.session_data.active_book)
# pprint(session.session_data.transaction_history)

# # Check for matching orders and create transactions
# session.match_orders()
