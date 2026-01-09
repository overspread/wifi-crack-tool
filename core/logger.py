# -*- coding: utf-8 -*-
"""
Logger configuration for WiFi Crack Tool
"""
import logging
import datetime
from pathlib import Path
from typing import Optional

_logger: Optional[logging.Logger] = None


def setup_logger(log_dir: Path, name: str = 'wifi_crack_tool') -> logging.Logger:
    """
    Setup and configure the logger
    
    :param log_dir: Directory path for log files
    :param name: Logger name
    :return: Configured logger instance
    """
    global _logger
    
    # Create log directory if not exists
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    # Create file handler
    log_file = log_dir / f"wifi_crack_{datetime.date.today():%Y%m%d}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """
    Get the configured logger instance
    
    :return: Logger instance
    """
    global _logger
    if _logger is None:
        # Return a default logger if not setup
        return logging.getLogger('wifi_crack_tool')
    return _logger
