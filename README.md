

### Short Description of the Trading System Structure

#### Files Overview:
1. **trader.py**: Manages individual trading operations.
2. **trading_platform.py**: Handles communication with the trading platform and executes orders.
3. **main_process.py**: The main script that initializes and controls the entire trading system.
4. **utils.py**: Contains utility functions used by the trading system. This file contains also important
converters between format used by noise_trader functions (such as `get_noise_rule`) and the format used by the trading system.
5. The noise trader functions are located in `traders/noise_trader.py` file
6. Current `Trader` class has a method `run()` that passes the book and current orders to the noise trader function,
gets the orders from there, converts them to a format understandable by the trading system and sends them to the trading platform.


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


## Application Parameters

When running the application, you can specify the following command-line parameters:

1. `--buffer_delay`: The delay in seconds before the Trading System processes the buffered orders. 
   - Default: `5`
   - Usage: `--buffer_delay 5`

2. `--max_buffer_releases`: The maximum number of buffer releases allowed before the Trading System stops. 
   - Default: `10`
   - Usage: `--max_buffer_releases 10`

3. `--num_traders`: The number of trader instances to run. 
   - Default: `3`
   - Usage: `--num_traders 3`

These parameters allow you to customize the behavior of the Trading System and the traders. You can specify these parameters when running the application as shown in the example below:

```bash
python -m traderabbit.main_process --buffer_delay 5 --max_buffer_releases 10 --num_traders 3
```


### Running as Separate Processes

Alternatively, you can run the trading system and the trader as separate processes. This can be useful for development or debugging purposes.

#### Running the Trading System

To run only the trading system, execute the following command:

```bash
python -m traderabbit.platform_process
```

#### Running a Trader

To run a trader that connects to a specific trading platform, first run the trading system so you will 
a have a trading platform to connect to. Then, knowing trading platform's ID,
execute the following command:

```bash
python -m traderabbit.trader_process --session-id=<Your_Session_UUID> --num-traders=<Number_of_Traders>
```

Replace `<Your_Session_UUID>` with the ID of the trading platform you want the trader to connect to.
The default value for session is 1234. It is for development purposes only: in real life each
new trading session will have a unique ID (UUID).

The default number of traders are 3. You can change it by replacing `<Number_of_Traders>` with the number of traders you want to run.


---

Both methods use RabbitMQ for inter-process communication. Make sure RabbitMQ is running before you start either the trading system or the trader.


#### Running for Development

For automatic code reloading during development, you can use `hupper` to monitor for file changes and restart the processes accordingly. Below are the commands to run the trading system and traders using `hupper`.

To run the trading system:
```bash
hupper -m traderabbit.platform_process
```

OR to run the main process:
```bash
hupper -m traderabbit.main_process
```

To run a trader with a specific trading session UUID and a given number of traders:
```bash
hupper -m traderabbit.trader_process --session-id=<Your_Session_UUID> --num-traders=<Number_of_Traders>
```

(The default number of traders is 3. The default session id is 1234.)


This will automatically restart the selected process if you make changes to any of the Python files.
