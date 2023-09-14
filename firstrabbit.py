import asyncio
import aio_pika
import json
import uuid
from datetime import datetime
from pprint import pprint
from custom_logger import setup_custom_logger
logger = setup_custom_logger(__name__)
from json import JSONEncoder
import random
from collections import defaultdict
class CustomEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return JSONEncoder.default(self, obj)
class TradingSystem:
    def __init__(self):
        self.id = uuid.uuid4()
        self.active_orders = []
        self.broadcast_exchange_name = f'broadcast_{self.id}'
        self.queue_name = f'trading_system_queue_{self.id}'
        self.trader_exchange = None
        logger.info(f"Trading System created with UUID: {self.id}")
        self.connected_traders = {}

    async def initialize(self):
        self.connection = await aio_pika.connect_robust("amqp://localhost")
        self.channel = await self.connection.channel()

        await self.channel.declare_exchange(self.broadcast_exchange_name, aio_pika.ExchangeType.FANOUT)
        self.trader_exchange = await self.channel.declare_exchange(self.queue_name, aio_pika.ExchangeType.DIRECT)
        trader_queue = await self.channel.declare_queue(self.queue_name)
        await trader_queue.bind(self.trader_exchange)  # bind the queue to the exchange
        await trader_queue.consume(self.on_individual_message)  # Assuming you have a method named on_individual_message

        await trader_queue.purge()

    async def send_broadcast(self, message):
        exchange = await self.channel.get_exchange(self.broadcast_exchange_name)
        await exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key=''  # routing_key is typically ignored in FANOUT exchanges
        )

    async def send_message_to_trader(self, trader_id, message):
        print(f"Sending message to trader {trader_id}")
        await self.trader_exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key=f'trader_{trader_id}'
        )
    async def handle_add_order(self, order):
        order_with_metadata = order.copy()
        order_with_metadata['session_id'] = str(self.id)
        order_with_metadata['timestamp'] = datetime.utcnow()

        self.active_orders.append(order_with_metadata)
        logger.info(f"Added order: {json.dumps(order_with_metadata, indent=4, cls=CustomEncoder)}")
        updated_order_book = self.generate_order_book()
        return dict(respond=True,  order_book=updated_order_book)
    async def handle_cancel_order(self, order):
        self.active_orders.remove(order)
        logger.info(    "Cancelled order: {order}")

    async def handle_update_book_status(self, order):
        "This one returns the most recent book to the trader who requested it."
        pass

    async def handle_register_me(self, msg_body):
        trader_id = msg_body.get('trader_id')
        self.connected_traders[trader_id] = "Connected"
        logger.info(f"Trader {trader_id} connected.")

    async def on_individual_message(self, message):
        logger.info(f"Received individual message: {message.body.decode()}")

        incoming_message = json.loads(message.body.decode())
        action = incoming_message.pop('action', None)
        trader_id = incoming_message.get('trader_id', None)  # Assuming the trader_id is part of the message

        handler_method = getattr(self, f"handle_{action}", None)
        if action:
            if handler_method:
                result= await handler_method(incoming_message)
                if result and result.pop('respond',None) and trader_id:
                    await self.send_message_to_trader(trader_id, result)

            else:
                logger.warning(f"No handler method found for action: {action}")
        else:
            logger.warning(f"No action found in message: {incoming_message}")
        await message.ack()

    from collections import defaultdict

    def generate_order_book(self):
        active_orders = self.active_orders
        asks = defaultdict(int)
        bids = defaultdict(int)
        min_ask_price = float('inf')
        max_bid_price = float('-inf')

        for order in active_orders:
            price = order['price']
            order_type = order['order_type']

            if order_type == 'ask':
                asks[price] += 1
                min_ask_price = min(min_ask_price, price)
            elif order_type == 'bid':
                bids[price] += 1
                max_bid_price = max(max_bid_price, price)

        # Calculate the current spread
        current_spread = None
        if min_ask_price != float('inf') and max_bid_price != float('-inf'):
            current_spread = min_ask_price - max_bid_price

        order_book = {
            'asks': dict(asks),
            'bids': dict(bids),
            'current_spread': current_spread
        }

        return order_book



class Trader:
    def __init__(self):
        self.id = uuid.uuid4()
        print(f"Trader created with UUID: {self.id}")
        self.connection = None
        self.channel = None
        self.trading_session_uuid = None
        self.trader_queue_name = f'trader_{self.id}'  # unique queue name based on Trader's UUID
        print(f"Trader queue name: {self.trader_queue_name}")
        self.queue_name = None
        self.broadcast_exchange_name = None
        self.trading_system_exchange = None

    async def initialize(self):
        self.connection = await aio_pika.connect_robust("amqp://localhost")
        self.channel = await self.connection.channel()
        await self.channel.declare_queue(self.trader_queue_name)

    async def connect_to_session(self, trading_session_uuid):
        self.trading_session_uuid = trading_session_uuid
        self.queue_name = f'trading_system_queue_{self.trading_session_uuid}'
        self.trader_queue_name = f'trader_{self.id}'  # unique queue name based on Trader's UUID

        self.broadcast_exchange_name = f'broadcast_{self.trading_session_uuid}'

        # Subscribe to group messages
        broadcast_exchange = await self.channel.declare_exchange(self.broadcast_exchange_name,
                                                                 aio_pika.ExchangeType.FANOUT)
        broadcast_queue = await self.channel.declare_queue("", auto_delete=True)
        await broadcast_queue.bind(broadcast_exchange)
        await broadcast_queue.consume(self.on_message)

        # For individual messages
        self.trading_system_exchange = await self.channel.declare_exchange(self.queue_name,
                                                                           aio_pika.ExchangeType.DIRECT)
        trader_queue = await self.channel.declare_queue(
            self.trader_queue_name)  # Declare a unique queue for this Trader
        await trader_queue.bind(self.trading_system_exchange, routing_key=self.trader_queue_name)
        await trader_queue.consume(self.on_message)  # Assuming you have a method named on_message

        await self.register()  # Register with the trading system

    async def register(self):
        message = {
            'action': 'register_me',
            'trader_id': str(self.id)
        }
        await self.send_to_trading_system(message)

    async def send_to_trading_system(self, message):
        await self.trading_system_exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key=self.queue_name  # Use the dynamic queue_name
        )

    async def on_message(self, message):
        logger.info(f"Trader {self.id} received message: {message.body.decode()}")
        await message.ack()


async def main():
    trading_system = TradingSystem()
    await trading_system.initialize()
    trading_session_uuid = trading_system.id
    print(f"Trading session UUID: {trading_session_uuid}")
    trader1 = Trader()
    await trader1.initialize()
    await trader1.connect_to_session(trading_session_uuid=trading_system.id)

    # The trading_session.connected_traders should now have the trader1's id.
    # print(trading_system.connected_traders)

    await trading_system.send_broadcast({"content": "Market is open"})
    await trading_system.send_message_to_trader(trader1.id, {"content": "Welcome to the market"})
    async def generate_random_posts(trader):
        for _ in range(10):
            new_post = {
                "action": "add_order",
                "order_type": random.choice(["ask", "bid"]),
                "price": random.choice(range(100,110)),
                "trader_id": str(trader.id)
            }
            await trader.send_to_trading_system(new_post)
            print(f"Sent post {_}: {json.dumps(new_post, indent=4)}")
            await asyncio.sleep(random.uniform(0.5, 2.0))  # wait between 0.5 to 2 seconds before the next post

    await generate_random_posts(trader1)
    await trading_system.connection.close()
    await trader1.connection.close()


if __name__ == "__main__":
    asyncio.run(main())
