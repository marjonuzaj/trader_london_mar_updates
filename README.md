
### Short Description of the Trading System Structure

#### Files Overview:
1. **trader.py**: Manages individual trading operations.
2. **trading_platform.py**: Handles communication with the trading platform and executes orders.
3. **main_process.py**: The main script that initializes and controls the entire trading system.

#### How to Run the System:

##### Requirements:
- **RabbitMQ**: Message broker for communication between different parts of the system.

###### Installing RabbitMQ:
1. On Ubuntu: `sudo apt-get install rabbitmq-server`
2. On macOS: `brew install rabbitmq`

###### Checking if RabbitMQ is Active:
- Run `sudo systemctl status rabbitmq-server` or `rabbitmqctl status` to check if the RabbitMQ service is running.


## Running the Application

### Running Simultaneously from a Single File

You can run both the trading system and the trader simultaneously from the same file using the following command:

```bash
python -m traderabbit.main_process
```

This command will initiate both the trading system and the trader as part of the same process. They will communicate with each other via RabbitMQ queues.

### Running as Separate Processes

Alternatively, you can run the trading system and the trader as separate processes. This can be useful for development or debugging purposes.

#### Running the Trading System

To run only the trading system, execute the following command:

```bash
python run_trading_system.py
```

#### Running a Trader

To run a trader that connects to a specific trading platform, first run the trading system so you will 
a have a trading platform to connect to. Then, knowing trading platform's ID,
execute the following command:

```bash
python run_trader.py --platform_id <Your_Platform_ID>
```

Replace `<Your_Platform_ID>` with the ID of the trading platform you want the trader to connect to.

---

Both methods use RabbitMQ for inter-process communication. Make sure RabbitMQ is running before you start either the trading system or the trader.


#### Running for development

Remember that you can use nodemon to run the above mentioned proccesses to automatically restart them when a file changes. For example, to run the trading system, you can use the following command:

```bash
nodemon --exec python -m  traderabbit.run_trading_system
```
OR:
```bash 
nodemon --exec python -m traderabbit.main_process
```
OR to run a trader:
```bash
nodemon --exec python -m traderabbit.run_trader --platform_id <Your_Platform_ID>
```

