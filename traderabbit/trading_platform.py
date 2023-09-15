import aio_pika
import json
import uuid
from datetime import datetime
from traderabbit.utils import ack_message
from traderabbit.custom_logger import setup_custom_logger

logger = setup_custom_logger(__name__)

from collections import defaultdict
from traderabbit.utils import CustomEncoder


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
        await self.trader_exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key=f'trader_{trader_id}'
        )

    async def handle_add_order(self, order):
        trader_id = order.get('trader_id')
        order_with_metadata = order.copy()
        order_with_metadata['session_id'] = str(self.id)
        order_with_metadata['timestamp'] = datetime.utcnow()
        order_with_metadata['order_id'] = str(uuid.uuid4())
        self.active_orders.append(order_with_metadata)

        logger.info(f'Total active orders: {len(self.active_orders)}')
        logger.info(f"Added order: {json.dumps(order_with_metadata, indent=4, cls=CustomEncoder)}")
        updated_order_book = self.generate_order_book()
        return dict(respond=True, order_book=updated_order_book,
                    outstanding_orders=self.get_outstanding_orders(trader_id))

    async def handle_cancel_order(self, order):
        self.active_orders.remove(order)
        logger.info("Cancelled order: {order}")

    async def handle_update_book_status(self, order):
        "This one returns the most recent book to the trader who requested it."
        pass

    async def handle_register_me(self, msg_body):
        trader_id = msg_body.get('trader_id')
        self.connected_traders[trader_id] = "Connected"
        logger.info(f"Trader {trader_id} connected.")

    @ack_message
    async def on_individual_message(self, message):

        incoming_message = json.loads(message.body.decode())
        logger.info(f"TS {self.id} received message: {incoming_message}")
        action = incoming_message.pop('action', None)
        trader_id = incoming_message.get('trader_id', None)  # Assuming the trader_id is part of the message

        handler_method = getattr(self, f"handle_{action}", None)
        if action:
            if handler_method:
                result = await handler_method(incoming_message)
                if result and result.pop('respond', None) and trader_id:
                    await self.send_message_to_trader(trader_id, result)

            else:
                logger.warning(f"No handler method found for action: {action}")
        else:
            logger.warning(f"No action found in message: {incoming_message}")

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

    def get_outstanding_orders(self, trader_id):
        outstanding_orders = {'bid': defaultdict(int), 'ask': defaultdict(int)}

        for order in self.active_orders:
            if order['trader_id'] == trader_id:
                order_type = order['order_type']
                price = order['price']
                outstanding_orders[order_type][price] += 1

        # Convert defaultdict to regular dict for JSON serialization if needed
        outstanding_orders['bid'] = dict(outstanding_orders['bid'])
        outstanding_orders['ask'] = dict(outstanding_orders['ask'])

        return outstanding_orders
