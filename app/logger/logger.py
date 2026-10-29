"""コンソールと logs/collector_YYYYMMDD.log の両方へ出力するロガー。"""
import logging
import sys
from pathlib import Path

from app.models import now_jst

LOGGER_NAME = "collector"


def setup_logger(log_dir: Path) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "collector_{}.log".format(now_jst().strftime("%Y%m%d"))
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
