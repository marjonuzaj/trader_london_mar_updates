from json import JSONEncoder
from datetime import datetime
from functools import wraps
import aio_pika
from enum import Enum
from uuid import UUID
from structures.structures import OrderModel
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
