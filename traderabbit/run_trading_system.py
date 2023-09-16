
import asyncio
from traderabbit.custom_logger import setup_custom_logger
from traderabbit.trading_platform import TradingSystem

logger = setup_custom_logger(__name__)

async def run_trading_system():
    trading_system = TradingSystem()
    await trading_system.initialize()
    trading_session_uuid = trading_system.id
    logger.info(f"Trading session UUID: \n {trading_session_uuid}")
    await trading_system.run()

if __name__ == "__main__":
    asyncio.run(run_trading_system())
