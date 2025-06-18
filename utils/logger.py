import logging
import sys
import os
from logging.handlers import RotatingFileHandler

LOG_FILENAME = "kindergarten_app.log"
LOG_DIR = "logs"

_logger_configured = False


def setup_logger(log_level=logging.INFO):
    """
    Настраивает и возвращает корневой логгер 'KindergartenApp'.
    Args:
        log_level: Минимальный уровень логирования для обработчиков (по умолчанию INFO).
                   В файл все равно будет писаться с уровня DEBUG.
    """
    global _logger_configured
    logger = logging.getLogger("KindergartenApp")

    if _logger_configured or logger.hasHandlers():
        return logger

    logger.setLevel(logging.DEBUG)

    log_formatter = logging.Formatter(...)
    # --- Используем log_level для консоли ---
    try:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(log_formatter)

        stream_handler.setLevel(log_level)
        logger.addHandler(stream_handler)
    except Exception as e:
        print(...)

    try:

        log_path = os.path.join(...)
        file_handler = RotatingFileHandler(...)
        file_handler.setFormatter(log_formatter)

        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
        print(...)
    except Exception as e:
        print(...)
        logger.error(...)

    _logger_configured = True
    logger.info(
        f"Logger setup complete. Console level: {logging.getLevelName(log_level)}, File level: DEBUG"
    )
    return logger
