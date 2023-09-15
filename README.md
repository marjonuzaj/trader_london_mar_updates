
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

##### Running the System:
- Open a terminal and navigate to the directory containing `main_process.py`.
- Run `python -m traderabbit.main_process`.

This should start the main trading process, assuming RabbitMQ is running and all Python dependencies are installed.
