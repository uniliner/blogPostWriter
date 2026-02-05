"""
Logging configuration for the Blog Post Writer application.

This module provides a centralized logging configuration that replaces
print statements with Python's logging system.
"""
import logging
import sys
from pathlib import Path


# Define custom log levels if needed
# Standard levels: DEBUG=10, INFO=20, WARNING=30, ERROR=40, CRITICAL=50


def setup_logger(
    name: str,
    level: int = logging.DEBUG,
    log_file: str = None,
    console_output: bool = True
) -> logging.Logger:
    """
    Set up and configure a logger with both file and console handlers.

    Args:
        name: Logger name (typically __name__ or a specific module name)
        level: Logging level (default: INFO)
        log_file: Path to log file. If None, logs only to console.
        console_output: Whether to output logs to console (default: True)

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logger("my_app", level=logging.DEBUG, log_file="app.log")
        >>> logger.info("Application started")
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter with detailed information
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler - simple format for user output
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        # Simple format for console (no timestamp needed for interactive use)
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # File handler - detailed format with timestamps
    if log_file:
        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False

    return logger


# Module-level logger instances
main_logger = None
agent_logger = None


def get_main_logger() -> logging.Logger:
    """Get or create the main application logger."""
    global main_logger
    if main_logger is None:
        main_logger = setup_logger(
            name="main",
            level=logging.DEBUG,
            log_file="logs/blog_writer.log",
            console_output=True
        )
    return main_logger


def get_agent_logger() -> logging.Logger:
    """Get or create the agent logger."""
    global agent_logger
    if agent_logger is None:
        agent_logger = setup_logger(
            name="agent",
            level=logging.DEBUG,
            log_file="logs/blog_writer.log",
            console_output=True
        )
    return agent_logger


# Convenience function to set global log level
def set_log_level(level: int) -> None:
    """
    Set the logging level for all loggers.

    Args:
        level: Logging level (e.g., logging.DEBUG, logging.INFO)

    Example:
        >>> set_log_level(logging.DEBUG)  # Enable debug output
        >>> set_log_level(logging.WARNING)  # Only show warnings and errors
    """
    if main_logger:
        main_logger.setLevel(level)
        for handler in main_logger.handlers:
            handler.setLevel(level)
    if agent_logger:
        agent_logger.setLevel(level)
        for handler in agent_logger.handlers:
            handler.setLevel(level)
