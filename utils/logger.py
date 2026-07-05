import logging
import os
from datetime import datetime


def setup_logging(log_file: str = "output.log", verbose: bool = False) -> None:
    log_dir = os.path.join("logs", datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(log_dir, log_file)),
            logging.StreamHandler(),
        ],
    )
