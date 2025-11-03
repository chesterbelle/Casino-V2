"""
Centralized logging system for Casino V2.

This module provides a unified logging interface with structured logging,
performance monitoring, and configurable output formats.
"""

import logging
import logging.handlers
import sys
import time
from functools import wraps
from pathlib import Path
from typing import Any, Dict, Optional, Union


class CasinoLogger:
    """Centralized logger with structured logging and performance monitoring."""

    def __init__(self, name: str = "casino", level: int = logging.INFO):
        self.name = name
        self.level = level
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # Performance tracking
        self.performance_data: Dict[str, Dict[str, Any]] = {}

    def add_file_handler(
        self, log_file: Union[str, Path], max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5
    ) -> None:
        """Add rotating file handler."""
        file_handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
        file_handler.setLevel(self.level)
        file_formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

    def log_performance(self, operation: str, duration: float, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log performance metrics."""
        if operation not in self.performance_data:
            self.performance_data[operation] = {
                "count": 0,
                "total_time": 0.0,
                "avg_time": 0.0,
                "min_time": float("inf"),
                "max_time": 0.0,
            }

        data = self.performance_data[operation]
        data["count"] += 1
        data["total_time"] += duration
        data["avg_time"] = data["total_time"] / data["count"]
        data["min_time"] = min(data["min_time"], duration)
        data["max_time"] = max(data["max_time"], duration)

        extra = f" | Duration: {duration:.4f}s"
        if metadata:
            extra += f" | Metadata: {metadata}"

        self.logger.info(f"PERF | {operation}{extra}")

    def get_performance_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get performance statistics."""
        return self.performance_data.copy()

    def reset_performance_stats(self) -> None:
        """Reset performance statistics."""
        self.performance_data.clear()

    # Convenience methods
    def debug(self, message: str, *args, **kwargs) -> None:
        self.logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs) -> None:
        self.logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        self.logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        self.logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs) -> None:
        self.logger.critical(message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs) -> None:
        self.logger.exception(message, *args, **kwargs)


# Global logger instance
logger = CasinoLogger()


def performance_monitor(operation_name: Optional[str] = None):
    """Decorator to monitor function performance."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                op_name = operation_name or f"{func.__module__}.{func.__qualname__}"
                logger.log_performance(op_name, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                op_name = operation_name or f"{func.__module__}.{func.__qualname__}"
                logger.log_performance(op_name, duration, {"error": str(e)})
                raise

        return wrapper

    return decorator


def log_function_call(level: int = logging.DEBUG):
    """Decorator to log function calls."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = f"{func.__module__}.{func.__qualname__}"
            logger.logger.log(level, f"CALL | {func_name} | args={len(args)} kwargs={list(kwargs.keys())}")
            try:
                result = func(*args, **kwargs)
                logger.logger.log(level, f"RETURN | {func_name}")
                return result
            except Exception as e:
                logger.logger.log(level, f"EXCEPTION | {func_name} | {e}")
                raise

        return wrapper

    return decorator


# Setup function for easy configuration
def setup_logging(
    log_file: Optional[Union[str, Path]] = None, level: int = logging.INFO, name: str = "casino"
) -> CasinoLogger:
    """Setup logging with optional file output."""
    global logger
    logger = CasinoLogger(name, level)

    if log_file:
        logger.add_file_handler(log_file)

    return logger
