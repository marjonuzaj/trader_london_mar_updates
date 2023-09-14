import asyncio
import aio_pika
import json
import uuid
from datetime import datetime
from pprint import pprint
from custom_logger import setup_custom_logger
logger = setup_custom_logger(__name__)

class TradingSystem:
    def __init__(self):
        self.id = uuid.uuid4()
        self.active_order_book = []
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

    async def handle_add_order(self, order):
        order_with_metadata = order.copy()
        order_with_metadata['session_id'] = str(self.id)
        order_with_metadata['timestamp'] = datetime.utcnow()

        self.active_order_book.append(order_with_metadata)
        logger.info(f"Added order: {order_with_metadata}")

    async def handle_cancel_order(self, order):
        self.active_order_book.remove(order)
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

        handler_method = getattr(self, f"handle_{action}", None)
        if action:
            if handler_method:
                await handler_method(incoming_message)
            else:
                logger.warning(f"No handler method found for action: {action}")
        else:
            logger.warning(f"No action found in message: {incoming_message}")
        await message.ack()


class Trader:
    def __init__(self):
        self.id = uuid.uuid4()
        print(f"Trader created with UUID: {self.id}")
        self.connection = None
        self.channel = None
        self.trading_session_uuid = None

    async def initialize(self):
        self.connection = await aio_pika.connect_robust("amqp://localhost")
        self.channel = await self.connection.channel()
        self.queue_name = None
        self.broadcast_exchange_name = None
        self.trading_system_exchange = None

    async def connect_to_session(self, trading_session_uuid):
        self.trading_session_uuid = trading_session_uuid

        self.queue_name = f'trading_system_queue_{self.trading_session_uuid}'

        self.broadcast_exchange_name = f'broadcast_{self.trading_session_uuid}'

        # Subscribe to group messages
        exchange = await self.channel.declare_exchange(self.broadcast_exchange_name, aio_pika.ExchangeType.FANOUT)
        queue = await self.channel.declare_queue("", auto_delete=True)
        await queue.bind(exchange)
        await queue.consume(self.on_message)

        # For individual messages
        self.trading_system_exchange = await self.channel.declare_exchange(self.queue_name,
                                                                           aio_pika.ExchangeType.DIRECT)
        #     Register with the trading system
        await self.register()

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
        print("Received message:", json.loads(message.body.decode()))


async def main():
    trading_system = TradingSystem()
    await trading_system.initialize()
    trading_session_uuid = trading_system.id
    print(f"Trading session UUID: {trading_session_uuid}")
    trader1 = Trader()
    await trader1.initialize()
    await trader1.connect_to_session(trading_session_uuid=trading_system.id)

    # The trading_session.connected_traders should now have the trader1's id.
    print(trading_system.connected_traders)

    await trading_system.send_broadcast({"content": "Market is open"})
    print('did we reach here?')
    await asyncio.sleep(5)  # Send a message every 5 seconds
    new_post = {
        "action": "add_order",
        "order_type": "ask",
        "price": 100.25,
        "trader_id": str(trader1.id)
    }

    await trader1.send_to_trading_system(new_post)

    await trading_system.connection.close()
    await trader1.connection.close()


if __name__ == "__main__":
    asyncio.run(main())
