import asyncio
import aio_pika
import json
import uuid
import random
from structures.structures import OrderModel, OrderStatus, OrderType
from datetime import datetime
from traderabbit.utils import ack_message
from traderabbit.custom_logger import setup_custom_logger

logger = setup_custom_logger(__name__)





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
        }

        await self.send_to_trading_system(message)

    async def send_to_trading_system(self, message):
        # we add to any message the trader_id
        message['trader_id'] = str(self.id)
        await self.trading_system_exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key=self.queue_name  # Use the dynamic queue_name
        )
    @ack_message
    async def on_message(self, message):
        logger.info(f"Trader {self.id} received message: {message.body.decode()}")

    async def post_new_order(self, amount, price, order_type: OrderType):
        # todo: here we should call a generating function passing there the current book state etc,
        # and it will return price, amount, order_type

        # TODO: all the following should be removed, it's now only for generating some prices for bids and asks
        order_type= random.choice([OrderType.ASK, OrderType.BID])
        if order_type == OrderType.ASK:
            price = random.choice([1, 2, 3, 4, 5])
        else:
            price = random.choice([5, 6, 7, 8, 9])

        new_order = {

            "amount": 1,
            "price": price,
            "order_type": order_type.value,
        }

        resp = await self.send_to_trading_system(new_order)
        logger.debug(f"Trader {self.id} posted new {order_type.value.upper()} order: {new_order}")



    # async def cancel_order(self, order_id):
    #     if order_id in self.orders:
    #         self.orders[order_id]['status'] = OrderStatus.CANCELLED.value
    #         logger.debug(f"Cancelled order: {order_id}")
    #
    #         # Here you could add code to send the cancellation to a RabbitMQ queue or other system
    #     else:
    #         logger.warning(f"Order ID {order_id} not found. Cannot cancel.")
    #


