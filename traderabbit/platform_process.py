import asyncio
import random
from traderabbit.custom_logger import setup_custom_logger
from traderabbit.trader import Trader
from traderabbit.trading_platform import TradingSystem
import signal
from traderabbit.main_process import main, handle_exit

logger = setup_custom_logger(__name__)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    trading_system = TradingSystem(buffer_delay=5)

    traders = []

    # Add the signal handler for Ctrl+C and SIGTERM
    signal.signal(signal.SIGINT, lambda *args: handle_exit(loop, trading_system, traders))
    signal.signal(signal.SIGTERM, lambda *args: handle_exit(loop, trading_system, traders))

    loop.run_until_complete(main(trading_system, traders))  # Your main async function
