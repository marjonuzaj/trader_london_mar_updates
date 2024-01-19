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

    def generate_initial_order_book(self):
        # Generate an initial order book with random data
        bids = [{'x': random.randint(9500, 10000), 'y': 1} for _ in range(5)]
        asks = [{'x': random.randint(10000, 10500), 'y': 1} for _ in range(5)]
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
            print(f'LEN OF HISTORY: {len(self.transaction_history)}')
            print('*' * 50)
            await websocket.send_json(
                {'status': 'update', 'order_book': self.order_book, 'history': self.transaction_history})
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
            bids.pop(0)
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
            order_type = data.get('type')
            price = data.get('price')
            size = data.get('size', 1)  # Default size to 1 if not specified

            if order_type in ['bid', 'ask'] and isinstance(price, (int, float)):
                new_order = {'x': price, 'y': size}
                self.order_book[order_type].append(new_order)
                self.execute_orders()
                await websocket.send_json(
                    {'status': 'update', 'order_book': self.order_book, 'history': self.transaction_history})
            else:
                print(f"Invalid message format: {message}")
        except json.JSONDecodeError:
            print(f"Error decoding message: {message}")
