from json import JSONEncoder
from datetime import datetime
from functools import wraps
import aio_pika
from enum import Enum
from pprint import pprint
from enum import IntEnum
from uuid import UUID
from structures.structures import OrderModel, OrderType, ActionType, LobsterEventType
from collections import defaultdict
from typing import List, Dict
import pandas as pd
import numpy as np
import asyncio
import os
import csv
from traderabbit.custom_logger import setup_custom_logger
from traders.noise_trader import settings

np.set_printoptions(floatmode='fixed', precision=0)

logger = setup_custom_logger(__name__)

dict_keys = type({}.keys())
dict_values = type({}.values())
DATA_PATH = 'data'
LOBSTER_MONEY_CONSTANT = 10000


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


def expand_dataframe(df, max_depth=10, step=1, reverse=False, default_price=0):
    """
    Expand a DataFrame to a specified max_depth.

    Parameters:
        df (DataFrame): DataFrame containing 'price' and 'amount' columns.
        max_depth (int, optional): Maximum length to which the DataFrame should be expanded. Default is 10.
        step (int, optional): Step to be used for incrementing the price levels. Default is 1.
        reverse (bool, optional): Whether to reverse the order of the DataFrame. Default is False.
        default_price (float, optional): Default starting price if DataFrame is empty. Default is 0.

    Returns:
        DataFrame: Expanded DataFrame.
    """

    # Check if DataFrame is empty
    if df.empty:
        df = pd.DataFrame({'price': [default_price], 'amount': [0]})

    # Sort the DataFrame based on 'price'
    df = df.sort_values('price', ascending=not reverse)

    # Sort the DataFrame based on 'price'
    df.sort_values('price', ascending=not reverse, inplace=True)

    # Calculate the number of additional rows needed
    additional_rows_count = max_depth - len(df)

    if additional_rows_count <= 0:
        return df.iloc[:max_depth]

    # Determine the direction of the step based on 'reverse'
    step_direction = -1 if reverse else 1

    # Generate additional elements for price levels
    last_price = df['price'].iloc[-1 if reverse else 0]
    existing_prices = set(df['price'].values)
    additional_price_elements = []

    i = 1
    while len(additional_price_elements) < additional_rows_count:
        new_price = last_price + i * step * step_direction
        if new_price not in existing_prices:
            additional_price_elements.append(new_price)
            existing_prices.add(new_price)
        i += 1
    # Generate additional elements for amount (all zeros)
    additional_amount_elements = [0] * additional_rows_count

    # Create a DataFrame for the additional elements
    df_additional = pd.DataFrame({'price': additional_price_elements, 'amount': additional_amount_elements})

    # Concatenate the original DataFrame with the additional elements
    df_expanded = pd.concat([df, df_additional]).reset_index(drop=True)

    # Sort the DataFrame based on 'price' if 'reverse' is True
    if reverse:
        df_expanded.sort_values('price', ascending=False, inplace=True)
        df_expanded.reset_index(drop=True, inplace=True)

    return df_expanded


class OrderType(IntEnum):
    ASK = -1  # sell
    BID = 1  # buy


def convert_to_book_format(active_orders, levels_n=10, default_price=2000):
    # Create a DataFrame from the list of active orders

    if active_orders:
        df = pd.DataFrame(active_orders)
    else:
        # Create an empty DataFrame with default columns
        df = pd.DataFrame(columns=[field for field in OrderModel.__annotations__])
    df['price'] = df['price'].round(5)
    df = df.astype({"price": int, "amount": int})

    # Aggregate orders by price, summing the amounts
    df_asks = df[df['order_type'] == OrderType.ASK.value].groupby('price')['amount'].sum().reset_index().sort_values(
        by='price').head(
        levels_n)
    df_bids = df[df['order_type'] == OrderType.BID.value].groupby('price')['amount'].sum().reset_index().sort_values(
        by='price',
        ascending=False).head(
        levels_n)

    df_asks = expand_dataframe(df_asks, max_depth=10, step=1, reverse=False, default_price=default_price)
    df_bids = expand_dataframe(df_bids, max_depth=10, step=1, reverse=True, default_price=default_price - 1)

    ask_prices = df_asks['price'].tolist()

    ask_quantities = df_asks['amount'].tolist()
    bid_prices = df_bids['price'].tolist()

    bid_quantities = df_bids['amount'].tolist()

    # Interleave the lists using np.ravel and np.column_stack
    interleaved_array = np.ravel(np.column_stack((ask_prices, ask_quantities, bid_prices, bid_quantities)))
    interleaved_array = interleaved_array.astype(np.float64)
    return interleaved_array


def convert_active_orders_to_lobster_format(active_orders, levels_n=10):
    # Create a DataFrame from the active orders
    df = pd.DataFrame(active_orders)

    # Separate bids and asks
    df_bids = df[df['order_type'] == 1]  # Assuming 1 for bids based on the IntEnum
    df_asks = df[df['order_type'] == -1]  # Assuming -1 for asks based on the IntEnum

    # Sort bids and asks
    df_bids = df_bids.sort_values(by=['price', 'timestamp'], ascending=[False, True])
    df_asks = df_asks.sort_values(by=['price', 'timestamp'], ascending=[True, True])

    # Take the top 'levels_n' levels
    df_bids = df_bids.head(levels_n)
    df_asks = df_asks.head(levels_n)

    # Create the LOBSTER format DataFrame
    lobster_columns = []
    for i in range(1, levels_n + 1):
        lobster_columns.extend([f'Ask Price {i}', f'Ask Size {i}', f'Bid Price {i}', f'Bid Size {i}'])

    df_lobster = pd.DataFrame(columns=lobster_columns)

    for i in range(levels_n):
        ask_price = df_asks['price'].iloc[i] if i < len(df_asks) else None
        ask_size = df_asks['amount'].iloc[i] if i < len(df_asks) else None
        bid_price = df_bids['price'].iloc[i] if i < len(df_bids) else None
        bid_size = df_bids['amount'].iloc[i] if i < len(df_bids) else None

        df_lobster.loc[0, f'Ask Price {i + 1}'] = ask_price
        df_lobster.loc[0, f'Ask Size {i + 1}'] = ask_size
        df_lobster.loc[0, f'Bid Price {i + 1}'] = bid_price
        df_lobster.loc[0, f'Bid Size {i + 1}'] = bid_size

    return df_lobster


def _append_order_book_to_csv(order_book, file_name, timestamp):
    csv_file_path = os.path.join(DATA_PATH, f"book_{file_name}.csv")

    # Check if the file exists to decide if headers need to be written
    write_header = not os.path.exists(csv_file_path)

    with open(csv_file_path, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)

        # Write the header only if the file didn't exist
        if write_header:
            header = ["Timestamp"]
            for i in range(1, (len(order_book) // 4) + 1):
                header.extend([f"Ask_Price_{i}", f"Ask_Size_{i}", f"Bid_Price_{i}", f"Bid_Size_{i}"])
            writer.writerow(header)

        # Write the book data with timestamp as a separate column
        writer.writerow([timestamp] + list(order_book))


async def append_order_book_to_csv(order_book, file_name, timestamp):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _append_order_book_to_csv, order_book, file_name, timestamp)


async def append_order_book_to_csv(order_book, file_name, timestamp):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _append_order_book_to_csv, order_book, file_name, timestamp)


def _append_lobster_message_to_csv(lobster_msg, file_name):
    csv_file_path = os.path.join(DATA_PATH, f"messages_{file_name}.csv")

    # Define the header (column names) for the LOBSTER-formatted CSV file
    fieldnames = ['Trader type', 'Time', 'Event Type', 'Order ID', 'Size', 'Price', 'Direction']

    # Check if the file exists to decide if headers need to be written
    write_header = not os.path.exists(csv_file_path)

    # Open the file in append mode ('a'). This creates the file if it doesn't exist.
    with open(csv_file_path, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # Write the header only if the file didn't exist
        if write_header:
            writer.writeheader()

        # Write the data
        writer.writerow(lobster_msg)


async def append_lobster_message_to_csv(lobster_msg, file_name):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _append_lobster_message_to_csv, lobster_msg, file_name)


def create_lobster_message(order_dict, event_type: LobsterEventType, trader_type: int, timestamp: datetime):
    """Creates a LOBSTER-formatted message dictionary."""

    lobster_message = {
        'Trader type': trader_type,
        'Time': timestamp.timestamp(),
        'Event Type': event_type,
        'Order ID': order_dict['id'],
        'Size': order_dict['amount'],
        'Price': order_dict['price'] * LOBSTER_MONEY_CONSTANT,
        'Direction': order_dict['order_type']  # Convert the string to its enum value
    }

    return lobster_message


def convert_to_noise_state(active_orders: List[Dict]) -> Dict:
    noise_state = {
        'outstanding_orders': {
            'bid': defaultdict(int),
            'ask': defaultdict(int)
        }
    }

    for order in active_orders:
        if order['status'] == 'active':
            order_type_value = order['order_type']
            order_type = OrderType(order_type_value).name.lower()

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
