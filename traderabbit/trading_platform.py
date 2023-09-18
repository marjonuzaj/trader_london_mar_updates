import aio_pika
import json
import uuid
from datetime import datetime
from traderabbit.utils import ack_message
from traderabbit.custom_logger import setup_custom_logger
from typing import List, Dict
from structures import OrderStatus, OrderModel, OrderType, TransactionModel
import asyncio
from collections import defaultdict
from traderabbit.utils import CustomEncoder, dump_transactions_to_csv, dump_orders_to_csv
from asyncio import Lock, Event
from pprint import pprint

logger = setup_custom_logger(__name__)


class TradingSystem:
    transactions = List[TransactionModel]
    all_orders = Dict[uuid.UUID, Dict]
    active_orders = Dict[uuid.UUID, Dict]
    buffered_orders = Dict[uuid.UUID, Dict]

    def __init__(self, buffer_delay=5):
        """
        buffer_delay: The delay in seconds before the Trading System processes the buffered orders.
        """
        # self.id = uuid.uuid4()
        self.id = "1234"  # for testing purposes
        self.all_orders = {}
        self.active_orders = {}
        self.buffered_orders = {}
        self.transactions = []
        self.broadcast_exchange_name = f'broadcast_{self.id}'
        self.queue_name = f'trading_system_queue_{self.id}'
        self.trader_exchange = None
        logger.info(f"Trading System created with UUID: {self.id}. Buffer delay is: {buffer_delay} seconds")
        self.connected_traders = {}
        self.buffer_delay = buffer_delay

        self.release_task = None
        self.lock = Lock()
        self.release_event = Event()

    async def initialize(self):
        self.connection = await aio_pika.connect_robust("amqp://localhost")
        self.channel = await self.connection.channel()

        await self.channel.declare_exchange(self.broadcast_exchange_name, aio_pika.ExchangeType.FANOUT,
                                            auto_delete=True)
        self.trader_exchange = await self.channel.declare_exchange(self.queue_name, aio_pika.ExchangeType.DIRECT,
                                                                   auto_delete=True)
        trader_queue = await self.channel.declare_queue(self.queue_name, auto_delete=True)
        await trader_queue.bind(self.trader_exchange)  # bind the queue to the exchange
        await trader_queue.consume(self.on_individual_message)  # Assuming you have a method named on_individual_message

        await trader_queue.purge()

    async def clean_up(self):
        try:
            # Unbind the queue from the exchange (optional, as auto_delete should handle this)
            trader_queue = await self.channel.get_queue(self.queue_name)
            await trader_queue.unbind(self.trader_exchange)

            # Close the channel and connection
            await self.channel.close()
            logger.info(f"Trading System {self.id} channel closed")
            await self.connection.close()
            logger.info(f"Trading System {self.id} connection closed")
            #     dump transactions and orders to files
            await dump_transactions_to_csv(self.transactions, f'transactions_{self.id}.csv')

            # Dump all_orders to CSV
            await dump_orders_to_csv(self.all_orders, f'all_orders_{self.id}.csv')
        except Exception as e:
            print(f"An error occurred during cleanup: {e}")

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

    def place_order(self, order_dict: Dict, trader_id: uuid.UUID):
        """ This one is called by handle_add_order, and is the one that actually places the order in the system.
        It adds automatically - we do all the validation (whether a trader allowed to place an order, etc) in the
        handle_add_order method.
        """
        order_id = order_dict['id']
        order_dict.update({
            'status': OrderStatus.ACTIVE.value,
        })
        self.all_orders[order_id] = order_dict
        self.active_orders[order_id] = order_dict
        return order_dict

    def fulfill_order(self, order_id: uuid.UUID):
        if order_id in self.active_orders:
            self.active_orders[order_id]['status'] = OrderStatus.FULFILLED.value
            del self.active_orders[order_id]

    def cancel_order(self, order_id: uuid.UUID):
        if order_id in self.active_orders:
            self.active_orders[order_id]['status'] = OrderStatus.CANCELLED.value
            del self.active_orders[order_id]

    async def add_order_to_buffer(self, order):
        async with self.lock:
            trader_id = order['trader_id']
            self.buffered_orders[trader_id] = order
            # self.buffered_orders[trader_id] = order.model_dump()

            if len(self.buffered_orders) == len(self.connected_traders):
                self.release_event.set()

            if self.release_task is None:
                self.release_task = asyncio.create_task(self.release_buffered_orders())

    async def release_buffered_orders(self):
        sleep_task = asyncio.create_task(asyncio.sleep(self.buffer_delay))
        release_event_task = asyncio.create_task(self.release_event.wait())

        await asyncio.wait([sleep_task,
                            release_event_task
                            ], return_when=asyncio.FIRST_COMPLETED)

        async with self.lock:
            common_timestamp = datetime.utcnow()

            for trader_id, order_dict in self.buffered_orders.items():
                order_dict['timestamp'] = common_timestamp

                self.place_order(order_dict, trader_id)

            logger.info(f"Total of {len(self.buffered_orders)} orders released from buffer")
            await self.clear_orders()
            self.buffered_orders.clear()

            self.release_task = None  # Reset the task so it can be recreated
            self.release_event.clear()  # Reset the event

    async def clear_orders(self):
        logger.info(f'Total amount of active orders: {len(self.active_orders)}')
        # Separate active orders into asks and bids
        asks = [order for order in self.active_orders.values() if order['order_type'] == OrderType.ASK.value]
        bids = [order for order in self.active_orders.values() if order['order_type'] == OrderType.BID.value]

        # Sort by price (lowest first for asks), and then by timestamp (oldest first - FIFO)
        # TODO: remember that this is FIFO. We need to adjust the rule (or make it adjustable in the config) if we want
        asks.sort(key=lambda x: (x['price'], x['timestamp']))
        # Sort by price (highest first for bids), and then by timestamp (oldest first)
        bids.sort(key=lambda x: (-x['price'], x['timestamp']))

        # Calculate the spread
        if asks and bids:
            lowest_ask = asks[0]['price']
            highest_bid = bids[0]['price']
            spread = highest_bid - lowest_ask
        else:
            logger.info("No overlapping orders.")
            return

        # Check if any transactions are possible
        if spread < 0:
            logger.info(f"No overlapping orders. Spread is negative: {spread}. Lowest ask: {lowest_ask}, highest bid: {highest_bid}")

            return
        logger.info(f"Spread: {spread}")
        # Filter the bids and asks that could be involved in a transaction
        viable_asks = [ask for ask in asks if ask['price'] <= highest_bid]
        viable_bids = [bid for bid in bids if bid['price'] >= lowest_ask]
        logger.info(f'Viable asks: {len(viable_asks)}')
        logger.info(f'Viable bids: {len(viable_bids)}')
        to_remove = []
        transactions = []

        # Create transactions
        while viable_asks and viable_bids:
            ask = viable_asks.pop(0)
            bid = viable_bids.pop(0)

            # Change the status to 'FULFILLED' in the all_orders dictionary
            self.all_orders[ask['id']]['status'] = OrderStatus.FULFILLED.value
            self.all_orders[bid['id']]['status'] = OrderStatus.FULFILLED.value

            # Create a transaction
            transaction_price = (ask['price'] + bid['price']) / 2  # Mid-price
            transaction = TransactionModel(
                id=uuid.uuid4(),
                bid_order_id=bid['id'],
                ask_order_id=ask['id'],
                timestamp=datetime.utcnow(),
                price=transaction_price
            )
            transactions.append(transaction.model_dump())

            to_remove.extend([ask['id'], bid['id']])

        # Remove cleared orders from active_orders
        for order_id in to_remove:
            self.active_orders.pop(order_id, None)

        # Add transactions to self.transactions
        self.transactions.extend(transactions)

        # Log the number of cleared and transacted orders
        logger.info(f"Cleared {len(to_remove)} orders.")
        logger.info(f"Created {len(transactions)} transactions.")

    async def handle_add_order(self, order):
        # TODO: Validate the order
        trader_id = order.get('trader_id')
        clean_order = {
            'id': uuid.uuid4(),
            'status': OrderStatus.BUFFERED.value,
            'amount': order.get('amount'),
            'price': order.get('price'),
            'order_type': order.get('order_type'),
            'timestamp': datetime.utcnow(),
            # we add the timestamp here but when we release an order out of the buffer we set a common tiestmap for them that points to the release time.
            'session_id': self.id,
            'trader_id': trader_id
        }
        resp = await self.add_order_to_buffer(clean_order)
        if resp:
            logger.info(f'Total active orders: {len(self.active_orders)}')
            logger.info(f"Added order: {json.dumps(resp, indent=4, cls=CustomEncoder)}")

        # updated_order_book = self.generate_order_book()
        # return dict(respond=True, order_book=updated_order_book,
        #             outstanding_orders=self.get_outstanding_orders(trader_id))

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
        logger.info(f"Total connected traders: {len(self.connected_traders)}")

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

    async def run(self):
        """
        keeps system active
        """
        while True:
            await asyncio.sleep(1)

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
