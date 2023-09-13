import asyncio
import aio_pika
import json
import uuid


class TradingSystem:
    def __init__(self):
        self.id = uuid.uuid4()
        self.active_order_book = []
        self.broadcast_exchange_name = f'broadcast_{self.id}'
        self.queue_name = f'trading_system_queue_{self.id}'
        self.trader_exchange=None
        print(f"Trading System created with UUID: {self.id}")

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

    async def add_order(self, order):
        self.active_order_book.append(order)
        print("Added order:", order)

    async def cancel_order(self, order):
        self.active_order_book.remove(order)
        print("Cancelled order:", order)

    async def update_book_status(self, order):
        print("Updated book status:", self.active_order_book)

    async def on_individual_message(self, message):
        print("Received individual message:", message.body.decode())
        incoming_message = json.loads(message.body.decode())
        action = incoming_message.get('action', None)

        if action:
            method = getattr(self, action, None)
            if method:
                await method(incoming_message)
            else:
                print(f"Can't find such action: {action}")
        else:
            print("No action specified in message.")
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
    trader = Trader()
    await trader.initialize()
    await trader.connect_to_session(trading_session_uuid)

    await trading_system.send_broadcast({"content": "Market is open"})
    print('did we reach here?')
    await asyncio.sleep(5)  # Send a message every 5 seconds
    await trader.send_to_trading_system({"action": "add_order", "symbol": "AAPL", "quantity": 1})

    await trading_system.connection.close()
    await trader.connection.close()


if __name__ == "__main__":
    asyncio.run(main())
