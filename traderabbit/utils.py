from json import JSONEncoder
from datetime import datetime
from functools import wraps
import aio_pika
from enum import Enum
from uuid import UUID
from structures.structures import OrderModel, OrderType, ActionType
from collections import defaultdict
from typing import List, Dict
import numpy as np
dict_keys = type({}.keys())
dict_values = type({}.values())
DATA_PATH='data'
class CustomEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, OrderModel):
            return obj.model_dump()
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, dict_keys):
            return list(obj)
        if isinstance(obj, dict_values):
            return list(obj)
        return JSONEncoder.default(self, obj)


import csv


async def dump_orders_to_csv(orders: dict, file_name='all_orders_history.csv'):
    # Convert the dict of orders to a list of orders (which are also dicts)
    # Also include the 'order_id' in each dictionary
    orders_list = [{**{'order_id': k}, **v} for k, v in orders.items()]

    # Open the file in write mode ('w') to overwrite any existing data
    with open(file_name, 'w', newline='') as f:
        # Assume all dictionaries in the list have the same keys
        writer = csv.DictWriter(f, fieldnames=orders_list[0].keys())

        # Write the headers
        writer.writeheader()

        # Write the orders
        writer.writerows(orders_list)


async def dump_transactions_to_csv(transactions: list, file_name='transaction_history.csv'):
    # Open the file in write mode ('w') to overwrite any existing data
    with open(file_name, 'w', newline='') as f:
        # Assume all dictionaries in the list have the same keys
        writer = csv.DictWriter(f, fieldnames=transactions[0].keys())

        # Write the headers
        writer.writeheader()

        # Write the transactions
        writer.writerows(transactions)


def ack_message(func):
    @wraps(func)
    async def wrapper(self, message: aio_pika.IncomingMessage):
        await func(self, message)
        await message.ack()

    return wrapper


def convert_to_book_format(active_orders, levels_n=10, default_price=2000):
    # Initialize empty book and indices
    book = defaultdict(list)
    ind_ask_price = []
    ind_ask_size = []
    ind_bid_price = []
    ind_bid_size = []

    # Populate the book from active orders
    for order in active_orders:
        price = order['price']
        size = order['amount']
        order_type = order['order_type']

        if order_type == 'ask':
            ind_ask_price.append(price)
            ind_ask_size.append(size)
        elif order_type == 'bid':
            ind_bid_price.append(price)
            ind_bid_size.append(size)

    # Sort the prices and sizes
    sorted_ask_indices = sorted(range(len(ind_ask_price)), key=lambda k: ind_ask_price[k])
    sorted_bid_indices = sorted(range(len(ind_bid_price)), key=lambda k: ind_bid_price[k], reverse=True)

    ind_ask_price = [ind_ask_price[i] for i in sorted_ask_indices]
    ind_ask_size = [ind_ask_size[i] for i in sorted_ask_indices]
    ind_bid_price = [ind_bid_price[i] for i in sorted_bid_indices]
    ind_bid_size = [ind_bid_size[i] for i in sorted_bid_indices]

    # Fill to ensure minimum depth (levels_n)
    while len(ind_ask_price) < levels_n:
        ind_ask_price.append(default_price + len(ind_ask_price) + 1)
        ind_ask_size.append(0)

    while len(ind_bid_price) < levels_n:
        ind_bid_price.append(default_price - (levels_n - len(ind_bid_price)))
        ind_bid_size.append(0)

    # Create a numpy array for the book
    book_with_depth = np.zeros(4 * levels_n)
    book_with_depth[::4] = ind_ask_price[:levels_n]
    book_with_depth[1::4] = ind_ask_size[:levels_n]
    book_with_depth[2::4] = ind_bid_price[:levels_n]
    book_with_depth[3::4] = ind_bid_size[:levels_n]

    return book_with_depth






def convert_to_noise_state(active_orders: List[Dict]) -> Dict:
    noise_state = {
        'outstanding_orders': {
            'bid': defaultdict(int),
            'ask': defaultdict(int)
        }
    }

    for order in active_orders:
        if order['status'] == 'active':
            order_type = order['order_type']
            price = order['price']
            amount = order['amount']
            noise_state['outstanding_orders'][order_type][price] += amount

    # Convert defaultdicts to regular dicts for easier use later
    noise_state['outstanding_orders']['bid'] = dict(noise_state['outstanding_orders']['bid'])
    noise_state['outstanding_orders']['ask'] = dict(noise_state['outstanding_orders']['ask'])

    return noise_state

def convert_to_trader_actions(response_dict):
    actions = []

    for order_type, order_details in response_dict.items():
        for price, size_list in order_details.items():
            size = size_list[0]
            action = {}
            if size > 0:
                action['action_type'] = ActionType.POST_NEW_ORDER.value
                action['order_type'] = order_type
                action['price'] = price
                action['amount'] = size
            elif size < 0:
                action['action_type'] = ActionType.CANCEL_ORDER.value
                action['order_type'] = order_type
                action['price'] = price
            if action:
                actions.append(action)

    return actions


def generate_file_name(session_uuid, file_type, extension='csv'):
    """
    Generate a filename for the given file type and session UUID.
    """
    # Format the current date and time to a string
    date_str = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    # Generate the filename
    file_name = f"{file_type}_{session_uuid}_{date_str}.{extension}"
    # Return the filename prefixed with the "data/" directory
    return f"{DATA_PATH}/{file_name}"