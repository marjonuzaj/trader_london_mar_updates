import asyncio
import aio_pika
import json
import uuid
from structures.structures import OrderType, ActionType, TraderType
from main_platform.utils import ack_message, convert_to_noise_state, convert_to_book_format, convert_to_trader_actions
from main_platform.custom_logger import setup_custom_logger
from external_traders.noise_trader import get_noise_rule, get_signal_noise, settings_noise, settings, \
    get_noise_rule_unif

logger = setup_custom_logger(__name__)


class BaseTrader:
    orders = {}
    order_book = {'bids': [], 'asks': []}

    def __init__(self, trader_type: TraderType):
        self.trader_type = trader_type.value
        self.id = str(uuid.uuid4())
        logger.info(f"Trader created with UUID: {self.id}")
        self.connection = None
        self.channel = None
        self.trading_session_uuid = None
        self.trader_queue_name = f'trader_{self.id}'  # unique queue name based on Trader's UUID
        logger.info(f"Trader queue name: {self.trader_queue_name}")
        self.queue_name = None
        self.broadcast_exchange_name = None
        self.trading_system_exchange = None

    async def initialize(self):
        self.connection = await aio_pika.connect_robust("amqp://localhost")
        self.channel = await self.connection.channel()
        await self.channel.declare_queue(self.trader_queue_name, auto_delete=True)

    async def clean_up(self):
        try:
            # Close the channel and connection
            if self.channel:
                await self.channel.close()
                logger.info(f"Trader {self.id} channel closed")
            if self.connection:
                await self.connection.close()
                logger.info(f"Trader {self.id} connection closed")

        except Exception as e:
            print(f"An error occurred during Trader cleanup: {e}")

    async def connect_to_session(self, trading_session_uuid):
        self.trading_session_uuid = trading_session_uuid
        self.queue_name = f'trading_system_queue_{self.trading_session_uuid}'
        self.trader_queue_name = f'trader_{self.id}'  # unique queue name based on Trader's UUID

        self.broadcast_exchange_name = f'broadcast_{self.trading_session_uuid}'

        # Subscribe to group messages
        broadcast_exchange = await self.channel.declare_exchange(self.broadcast_exchange_name,
                                                                 aio_pika.ExchangeType.FANOUT,
                                                                 auto_delete=True)
        broadcast_queue = await self.channel.declare_queue("", auto_delete=True)
        await broadcast_queue.bind(broadcast_exchange)
        await broadcast_queue.consume(self.on_message_from_system)

        # For individual messages
        self.trading_system_exchange = await self.channel.declare_exchange(self.queue_name,
                                                                           aio_pika.ExchangeType.DIRECT,
                                                                           auto_delete=True)
        trader_queue = await self.channel.declare_queue(
            self.trader_queue_name,
            auto_delete=True
        )  # Declare a unique queue for this Trader
        await trader_queue.bind(self.trading_system_exchange, routing_key=self.trader_queue_name)
        await trader_queue.consume(self.on_message_from_system)

        await self.register()  # Register with the trading system

    async def register(self):
        message = {
            'action': ActionType.REGISTER.value,
            'trader_type': self.trader_type
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
    async def on_message_from_system(self, message):
        """Process incoming messages from trading system.
        For BaseTrader it updates order book and inventory if needed.

        """
        try:
            json_message = json.loads(message.body.decode())
            action_type = json_message.get('type')
            data = json_message.get('data')
            order_book = data.get('order_book')
            if order_book:
                self.order_book = order_book
            handler = getattr(self, f'handle_{action_type}', None)
            if handler:
                await handler(data)
                await self.post_processing_server_message(json_message)
            else:
                print(f"Invalid message format: {message}")
        except json.JSONDecodeError:
            print(f"Error decoding message: {message}")


    async  def post_processing_server_message(self, json_message):
        """for BaseTrader it is not implemented. For human trader we send updated info back to client.
        For other market maker types we need do some reactions on updated market if needed.
        """
        pass
    async def post_new_order(self,
                             amount, price, order_type: OrderType
                             ):
        new_order = {
            "action": ActionType.POST_NEW_ORDER.value,
            "amount": amount,
            "price": price,
            "order_type": order_type.value,
        }
        await self.send_to_trading_system(new_order)
        logger.debug(f"Trader {self.id} posted new {order_type} order: {new_order}")

    async def send_cancel_order_request(self, order_id: uuid.UUID):
        cancel_order_request = {
            "action": ActionType.CANCEL_ORDER.value,  # Assuming you have an ActionType Enum
            "trader_id": self.id,
            "order_id": order_id
        }

        await self.send_to_trading_system(cancel_order_request)
        logger.info(f"Trader {self.id} sent cancel order request: {cancel_order_request}")