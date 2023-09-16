import asyncio
import random
from traderabbit.custom_logger import setup_custom_logger
from traderabbit.trader import Trader
from traderabbit.trading_platform import TradingSystem

logger = setup_custom_logger(__name__)


async def generate_random_posts(trader):
    while True:
        await trader.post_new_order()
        await asyncio.sleep(random.uniform(2, 5))  # Wait between 2 to 5 seconds before posting the next order


async def main():
    try:
        trading_system = TradingSystem()
        await trading_system.initialize()
        trading_session_uuid = trading_system.id
        logger.info(f"Trading session UUID: {trading_session_uuid}")

        trader1 = Trader()
        await trader1.initialize()
        await trader1.connect_to_session(trading_session_uuid=trading_system.id)

        print(trading_system.connected_traders)

        await trading_system.send_broadcast({"content": "Market is open"})
        await trading_system.send_message_to_trader(trader1.id, {"content": "Welcome to the market"})

        trader_task = asyncio.create_task(generate_random_posts(trader1))
        trading_system_task = asyncio.create_task(trading_system.run())  # Assume this method exists

        await asyncio.gather(trader_task, trading_system_task)
    except KeyboardInterrupt:
        print("Interrupt received. Starting cleanup...")
    except Exception as e:
        logger.exception(e)
        print('------------------')
    finally:

        await trading_system.clean_up()  # Assume this method deletes queues, exchanges, etc.
        await trader1.clean_up()  # Similar cleanup for the trader


if __name__ == "__main__":
    # TODO: the keyboard interrupt doesn't work!
    asyncio.run(main())
