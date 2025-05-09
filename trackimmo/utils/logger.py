"""
Logger module for TrackImmo backend.

This module configures loguru for structured logging.
"""
import sys
import os
from loguru import logger
from trackimmo.config import settings


# Remove default logger
logger.remove()

# Add console logger
logger.add(
    sys.stderr,
    level=settings.LOG_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)

# Add file logger for errors
os.makedirs("logs", exist_ok=True)
logger.add(
    "logs/error.log",
    level="ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="10 MB",
    retention="1 month",
)

# Add file logger for all levels
logger.add(
    "logs/trackimmo.log",
    level=settings.LOG_LEVEL,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="10 MB",
    retention="1 week",
)


def get_logger(name):
    """Get a logger with the specified name."""
    return logger.bind(name=name) 