import asyncio
import random
from traderabbit.custom_logger import setup_custom_logger
from traderabbit.trader import Trader
from traderabbit.trading_platform import TradingSystem
import signal
from structures.structures import TraderType
logger = setup_custom_logger(__name__)


async def main(trading_system, traders=()):
    await trading_system.initialize()
    trading_session_uuid = trading_system.id
    logger.info(f"Trading session UUID: {trading_session_uuid}")
    for i in traders:
        await i.initialize()
        await i.connect_to_session(trading_session_uuid=trading_session_uuid)

    await trading_system.send_broadcast({"content": "Market is open"})
    trader_tasks = []
    for i in traders:
        trader_tasks.append(asyncio.create_task(i.run()))

    trading_system_task = asyncio.create_task(trading_system.run())

    await asyncio.gather(trading_system_task, *trader_tasks)


async def async_handle_exit(loop ,trading_system = None , traders=()):
    if trading_system:
        await trading_system.clean_up()
    for i in traders:
        await i.clean_up()

    # Cancel all running tasks
    for task in asyncio.all_tasks(loop=loop):
        task.cancel()
        print('task cancelled!')

    # Allow time for the tasks to cancel
    await asyncio.sleep(1)

    loop.stop()


def handle_exit(loop, trading_system=None, traders=()):
    loop.create_task(async_handle_exit(loop, trading_system,  traders))


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    trading_system = TradingSystem(buffer_delay=5)
    num_traders = 3
    traders = [Trader(trader_type=TraderType.NOISE) for _ in range(num_traders)]


    # Add the signal handler for Ctrl+C and SIGTERM
    signal.signal(signal.SIGINT, lambda *args: handle_exit(loop, trading_system, traders))
    signal.signal(signal.SIGTERM, lambda *args: handle_exit(loop, trading_system, traders))

    loop.run_until_complete(main(trading_system, traders))  # Your main async function
