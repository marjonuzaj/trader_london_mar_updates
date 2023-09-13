import asyncio
import aio_pika
import json


class TradingSystem:
    async def initialize(self):
        self.connection = await aio_pika.connect_robust("amqp://localhost")
        self.channel = await self.connection.channel()

        # For sending broadcasts
        await self.channel.declare_exchange('broadcast', aio_pika.ExchangeType.FANOUT)

        # For receiving individual messages from Traders
        self.trader_exchange = await self.channel.declare_exchange('trading_system', aio_pika.ExchangeType.DIRECT)
        trader_queue = await self.channel.declare_queue('trading_system_queue')
        await trader_queue.bind(self.trader_exchange, 'trading_system_queue')

        await trader_queue.consume(self.on_individual_message)

    async def send_broadcast(self, message):
        exchange = await self.channel.get_exchange('broadcast')
        await exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key=''  # routing_key is typically ignored in FANOUT exchanges
        )

    async def on_individual_message(self, message):
        print("Received individual message:", json.loads(message.body.decode()))


class Trader:
    async def initialize(self):
        self.connection = await aio_pika.connect_robust("amqp://localhost")
        self.channel = await self.connection.channel()
        exchange = await self.channel.declare_exchange('broadcast', aio_pika.ExchangeType.FANOUT)
        queue = await self.channel.declare_queue("", auto_delete=True)
        await queue.bind(exchange)

        await queue.consume(self.on_message)
        # For sending messages to TradingSystem
        self.trading_system_exchange = await self.channel.declare_exchange('trading_system',
                                                                           aio_pika.ExchangeType.DIRECT)

    async def on_message(self, message):
        print("Received message:", json.loads(message.body.decode()))
    async def send_to_trading_system(self, message):
        await self.trading_system_exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key='trading_system_queue'
        )
async def main():
    trading_system = TradingSystem()
    trader = Trader()

    await trading_system.initialize()
    await trader.initialize()

    await trading_system.send_broadcast({"content": "Market is open"})
    await asyncio.sleep(2)  # Give it some time to process the message
    await asyncio.sleep(5)  # Send a message every 5 seconds
    await trader.send_to_trading_system({"action": "buy", "symbol": "AAPL", "quantity": 1})

    await trading_system.connection.close()
    await trader.connection.close()

if __name__ == "__main__":
    asyncio.run(main())
