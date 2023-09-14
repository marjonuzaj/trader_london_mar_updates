# custom_logger.py

from termcolor import colored
import logging


class CustomFormatter(logging.Formatter):
    COLORS = {
        'WARNING': 'yellow',
        'INFO': 'green',
        'DEBUG': 'blue',
        'CRITICAL': 'red',
        'ERROR': 'red'
    }

    def format(self, record):
        log_message = super(CustomFormatter, self).format(record)
        return colored(log_message, self.COLORS.get(record.levelname))


def setup_custom_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = CustomFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)

    logger.addHandler(ch)
    return logger
