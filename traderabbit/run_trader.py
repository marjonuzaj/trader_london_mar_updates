
import asyncio
import argparse
import random
from traderabbit.custom_logger import setup_custom_logger
from traderabbit.trader import Trader

logger = setup_custom_logger(__name__)

async def generate_random_posts(trader):
    while True:
        await trader.post_new_order()
        await asyncio.sleep(random.uniform(2, 5))  # Wait between 2 to 5 seconds before posting the next order

async def run_trader(platform_id):
    trader = Trader()
    await trader.initialize()
    await trader.connect_to_session(trading_session_uuid=platform_id)
    await generate_random_posts(trader)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run a trader connected to a specific trading platform.')
    parser.add_argument('--platform_id', required=True, help='The ID of the trading platform to connect to.')

    args = parser.parse_args()
    asyncio.run(run_trader(args.platform_id))
