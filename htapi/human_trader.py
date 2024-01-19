import uuid
import asyncio
import random
import time
import json


class HumanTrader:
    def __init__(self):
        self.uuid = str(uuid.uuid4())
        self.update_task = None
        self.order_book = self.generate_initial_order_book()
        self.transaction_history = self.generate_initial_history()

    def calculate_spread(self):
        # Ensure there are both bids and asks in the order book
        if not self.order_book['bid'] or not self.order_book['ask']:
            return None

        highest_bid = max(self.order_book['bid'], key=lambda x: x['x'])['x']
        lowest_ask = min(self.order_book['ask'], key=lambda x: x['x'])['x']

        # Spread is the difference between the lowest ask and the highest bid
        return lowest_ask - highest_bid

    def generate_initial_order_book(self):
        # Generate an initial order book with random data
        bids = [{'x': random.randint(9500, 10000), 'y': 1} for _ in range(10)]
        asks = [{'x': random.randint(10000, 10500), 'y': 1} for _ in range(10)]
        return {'bid': bids, 'ask': asks}

    def generate_initial_history(self):
        # Generate some initial transaction history
        history = [{'price': random.randint(9500, 10500), 'timestamp': time.time()} for _ in range(10)]
        return history

    async def run(self, websocket):
        n = 5  # Interval in seconds
        while True:
            print('PERIODIC UPDATE')
            self.generate_order()
            self.execute_orders()

            spread = self.calculate_spread()
            await websocket.send_json(
                {
                    'type': 'update',
                    'order_book': self.order_book,
                    'history': self.transaction_history,
                    'spread': spread
                }
            )
            await asyncio.sleep(n)

    def generate_order(self):
        # Generate a new order
        new_order_price = self.calculate_new_order_price()
        order_type = random.choice(['bid', 'ask'])
        new_order = {'x': new_order_price, 'y': 1}
        self.order_book[order_type].append(new_order)

    def execute_orders(self):
        # Check and execute orders where bid >= ask
        bids = self.order_book['bid']
        asks = self.order_book['ask']
        bids.sort(key=lambda x: x['x'], reverse=True)
        asks.sort(key=lambda x: x['x'])

        while bids and asks and bids[0]['x'] >= asks[0]['x']:
            executed_price = (bids[0]['x'] + asks[0]['x']) / 2  # Average price as execution price
            self.transaction_history.append({'price': executed_price, 'timestamp': time.time()})

            # Decrease the quantity of the bid and ask by 1
            bids[0]['y'] -= 1
            asks[0]['y'] -= 1

            # If the quantity becomes 0, remove the order from the book
            if bids[0]['y'] <= 0:
                bids.pop(0)
            if asks[0]['y'] <= 0:
                asks.pop(0)

    def calculate_new_order_price(self):
        # Implement logic to calculate the price of the new order
        return random.randint(9500, 10500)  # Placeholder logic

    def handle_message(self, message):
        return f"{message} PING"

    def start_updates(self, websocket):
        self.update_task = asyncio.create_task(self.run(websocket))
        self.update_task.add_done_callback(self.task_done_callback)

    def task_done_callback(self, task):
        try:
            task.result()
        except Exception as e:
            print(f"Exception in task: {e}")
            raise e

    def stop_updates(self):
        if self.update_task:
            self.update_task.cancel()

    async def handle_incoming_message(self, websocket, message):
        """
        Handle incoming messages to add new orders and check for executions.
        """
        try:
            data = json.loads(message)
            action_type = data.get('type')
            print('*' * 50)
            print(f"Received message: {message}")
            if action_type in ['aggressiveAsk', 'passiveAsk', 'aggressiveBid', 'passiveBid']:
                print('are we gonna process?')
                self.process_order(action_type)
                await websocket.send_json(
                    {'type': 'update', 'order_book': self.order_book, 'history': self.transaction_history})
            else:
                print(f"Invalid message format: {message}")
        except json.JSONDecodeError:
            print(f"Error decoding message: {message}")

    def process_order(self, action_type):
        if action_type == 'aggressiveAsk':
            # Put an ask at the best bid level, so it's immediately executed
            price = max(self.order_book['bid'], key=lambda x: x['x'])['x'] if self.order_book['bid'] else None
        elif action_type == 'passiveAsk':
            # Put an ask at the best ask level
            price = min(self.order_book['ask'], key=lambda x: x['x'])['x'] if self.order_book['ask'] else None
        elif action_type == 'aggressiveBid':
            # Put a bid at the best ask level, so it's immediately executed
            price = min(self.order_book['ask'], key=lambda x: x['x'])['x'] if self.order_book['ask'] else None
        elif action_type == 'passiveBid':
            # Put a bid at the best bid level
            price = max(self.order_book['bid'], key=lambda x: x['x'])['x'] if self.order_book['bid'] else None
            print(price, 'price')
            print('*' * 50)
        if price is not None:
            print('adding order')
            self.add_order(action_type, price)

    def add_order(self, order_type, price):
        size = 1  # Assuming a fixed size for simplicity

        if 'Ask' in order_type:
            if 'passive' in order_type and self.order_book['ask']:
                # Increase quantity of the best ask
                best_ask = min(self.order_book['ask'], key=lambda x: x['x'])
                best_ask['y'] += size
            elif 'aggressive' in order_type and self.order_book['bid']:
                # Place an aggressive ask at the best bid level
                best_bid_price = max(self.order_book['bid'], key=lambda x: x['x'])['x']
                new_order = {'x': best_bid_price, 'y': size}
                self.order_book['ask'].append(new_order)
        else:  # For bids
            if 'passive' in order_type and self.order_book['bid']:
                # Increase quantity of the best bid
                best_bid = max(self.order_book['bid'], key=lambda x: x['x'])
                best_bid['y'] += size
            elif 'aggressive' in order_type and self.order_book['ask']:
                # Place an aggressive bid at the best ask level
                best_ask_price = min(self.order_book['ask'], key=lambda x: x['x'])['x']
                new_order = {'x': best_ask_price, 'y': size}
                self.order_book['bid'].append(new_order)

        self.execute_orders()

