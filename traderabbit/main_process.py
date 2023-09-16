import asyncio
import random
from traderabbit.custom_logger import setup_custom_logger
from traderabbit.trader import Trader
from traderabbit.trading_platform import TradingSystem
import signal

logger = setup_custom_logger(__name__)


async def generate_random_posts(trader):
    while True:
        await trader.post_new_order()
        await asyncio.sleep(random.uniform(2, 5))  # Wait between 2 to 5 seconds before posting the next order


async def main(trading_system, trader1):
    await trading_system.initialize()
    trading_session_uuid = trading_system.id
    logger.info(f"Trading session UUID: {trading_session_uuid}")

    await trader1.initialize()
    await trader1.connect_to_session(trading_session_uuid=trading_system.id)

    print(trading_system.connected_traders)

    await trading_system.send_broadcast({"content": "Market is open"})
    await trading_system.send_message_to_trader(trader1.id, {"content": "Welcome to the market"})

    trader_task = asyncio.create_task(generate_random_posts(trader1))
    trading_system_task = asyncio.create_task(trading_system.run())  # Assume this method exists

    await asyncio.gather(trader_task, trading_system_task)


async def async_handle_exit(trading_system, trader1, loop):
    await trading_system.clean_up()
    await trader1.clean_up()

    # Cancel all running tasks
    for task in asyncio.all_tasks(loop=loop):

        task.cancel()
        print('task cancelled!')

    # Allow time for the tasks to cancel
    await asyncio.sleep(1)

    loop.stop()

def handle_exit(loop, trading_system, trader1):
    loop.create_task(async_handle_exit(trading_system, trader1, loop))


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    trading_system = TradingSystem()
    trader1 = Trader()

    # Add the signal handler for Ctrl+C and SIGTERM
    signal.signal(signal.SIGINT, lambda *args: handle_exit(loop, trading_system, trader1))
    signal.signal(signal.SIGTERM, lambda *args: handle_exit(loop, trading_system, trader1))

    loop.run_until_complete(main(trading_system, trader1))  # Your main async function

