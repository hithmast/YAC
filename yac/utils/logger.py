import logging
import os
from datetime import datetime

def setup_logging(log_file):
    log_dir = os.path.join('logs', datetime.now().strftime('%Y-%m-%d'))
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',
                        handlers=[logging.FileHandler(os.path.join(log_dir, log_file)),
                                  logging.StreamHandler()])
