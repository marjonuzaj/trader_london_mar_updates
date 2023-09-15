import asyncio
import aio_pika
import json
import uuid
from datetime import datetime
from traderabbit.utils import ack_message
from traderabbit.custom_logger import setup_custom_logger

logger = setup_custom_logger(__name__)

import random
from collections import defaultdict
from traderabbit.utils import CustomEncoder


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
    @ack_message
    async def on_message(self, message):
        logger.info(f"Trader {self.id} received message: {message.body.decode()}")


