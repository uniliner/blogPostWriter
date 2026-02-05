# Logging Configuration Guide

This document explains the logging system implementation and how to configure it.

## Overview

The application has been migrated from using `print()` statements to Python's built-in `logging` module. This provides several benefits:

- **Configurable log levels** - Control verbosity without code changes
- **Multiple output destinations** - Log to console, files, or both
- **Structured logging** - Consistent format with timestamps and severity levels
- **Better debugging** - Detailed logs for development, cleaner output for users
- **Production ready** - Easy integration with log aggregation services

## Files Modified/Created

| File | Description |
|------|-------------|
| `logger_config.py` | New centralized logging configuration module |
| `main.py` | Migrated from print to logging |
| `decomposition_agent.py` | Migrated from print to logging |

## Log Levels

The logging system uses standard Python log levels:

| Level | Numeric Value | When Used |
|-------|---------------|-----------|
| `DEBUG` | 10 | Detailed information for diagnosing problems |
| `INFO` | 20 | Confirmation that things are working as expected |
| `WARNING` | 30 | Something unexpected happened (but still working) |
| `ERROR` | 40 | Serious problem occurred |
| `CRITICAL` | 50 | Serious error, program may not continue |

### How Different Levels Are Used

- **DEBUG**: AI model outputs, tool inputs/outputs, detailed plans
- **INFO**: Phase headers, completion messages, summaries, results
- **WARNING**: Obstacles detected, plan revisions, task aborts
- **ERROR**: Input validation errors, API errors

## Configuration

### Basic Usage

The loggers are automatically initialized when imported:

```python
from logger_config import get_main_logger, get_agent_logger

main_logger = get_main_logger()
agent_logger = get_agent_logger()

main_logger.info("Application started")
agent_logger.debug("Executing subtask...")
```

### Setting Log Level

To change the log level globally:

```python
from logger_config import set_log_level
import logging

# Show all messages including debug
set_log_level(logging.DEBUG)

# Show only warnings and errors
set_log_level(logging.WARNING)
```

Or set in `main.py`:

```python
from logger_config import get_main_logger
import logging

logger = get_main_logger()
logger.setLevel(logging.DEBUG)  # Set specific logger level
```

### Custom File Locations

To customize log file locations:

```python
from logger_config import setup_logger
import logging

# Custom logger configuration
my_logger = setup_logger(
    name="custom_logger",
    level=logging.DEBUG,
    log_file="my_custom_log_file.log",
    console_output=True
)
```

## Log File Locations

By default, all logs are written to a single file:

| Log File | Contents |
|----------|-----------|
| `logs/blog_writer.log` | Main application and agent operations |

The `logs/` directory is created automatically if it doesn't exist.

Log entries include the logger name (`main` or `agent`) in the format, making it easy to distinguish the source:
```
2026-02-03 14:30:45 [main] [INFO] Application started
2026-02-03 14:30:46 [agent] [INFO] Plan created with 5 subtasks
```

## Log Formats

### Console Output Format
```
INFO: Application started
INFO: Plan created with 5 subtasks
WARNING: Obstacle detected: tool_failure
```

### File Output Format
```
2026-02-03 14:30:45 [main] [INFO] Application started
2026-02-03 14:30:46 [agent] [INFO] Plan created with 5 subtasks
2026-02-03 14:30:50 [agent] [WARNING] Obstacle detected: tool_failure
```

## Configuration Examples

### Development Mode (Verbose)
```python
import logging
from logger_config import set_log_level

set_log_level(logging.DEBUG)
```

### Production Mode (Minimal)
```python
import logging
from logger_config import set_log_level

set_log_level(logging.WARNING)
```

### Silent Mode (Errors Only)
```python
import logging
from logger_config import set_log_level

set_log_level(logging.ERROR)
```

### Disable Console Output (File Only)
Edit `logger_config.py`:
```python
main_logger = setup_logger(
    name="main",
    level=logging.INFO,
    log_file="logs/blog_writer.log",
    console_output=False  # Disable console output
)

agent_logger = setup_logger(
    name="agent",
    level=logging.INFO,
    log_file="logs/blog_writer.log",
    console_output=False  # Disable console output
)
```

### Disable File Logging (Console Only)
```python
from logger_config import setup_logger
import logging

logger = setup_logger(
    name="my_logger",
    level=logging.INFO,
    log_file=None,  # No file logging
    console_output=True
)
```

## Environment Variable Configuration

You can configure logging via environment variables by modifying `main.py`:

```python
import os
import logging
from logger_config import set_log_level

# Set log level from environment
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)
set_log_level(log_level)
```

Then set the environment variable:
```bash
export LOG_LEVEL=DEBUG
python main.py
```

## Integration with Log Aggregation

### Example: Sending to External Service

```python
import logging
from logger_config import setup_logger

# Setup with custom handler
logger = setup_logger(
    name="blog_writer.main",
    level=logging.INFO,
    log_file=None,
    console_output=False
)

# Add external handler (e.g., Datadog, CloudWatch, etc.)
from datadog_logging import DatadogHandler
dd_handler = DatadogHandler(api_key="your-key")
logger.addHandler(dd_handler)
```

## Troubleshooting

### Logs Not Appearing

Check that:
1. The `logs/` directory has write permissions
2. The log level is set appropriately
3. Console output isn't disabled when expecting console logs

### Too Much Output

Increase the log level:
```python
import logging
set_log_level(logging.WARNING)  # Only warnings and errors
```

### Not Enough Detail

Decrease the log level:
```python
import logging
set_log_level(logging.DEBUG)  # Everything
```

## Migration Summary

| Original (print) | New (logging) |
|------------------|---------------|
| `print(message)` | `logger.info(message)` |
| N/A | `logger.debug(message)` |
| N/A | `logger.warning(message)` |
| `print("Error:", e)` | `logger.error(f"Error: {e}")` |
| `traceback.print_exc()` | `logger.debug(traceback.format_exc())` |

## Best Practices

1. **Use appropriate levels**:
   - DEBUG for verbose diagnostic info
   - INFO for normal operation milestones
   - WARNING for recoverable issues
   - ERROR for failures

2. **Use f-strings for formatting**:
   ```python
   logger.info(f"Processing {filename} ({size} bytes)")
   ```

3. **Don't concatenate for performance**:
   ```python
   # Bad
   logger.info("Processing " + filename + " with " + str(size))

   # Good
   logger.info("Processing %s with %s", filename, size)
   # Or with f-strings (Python 3.6+)
   logger.info(f"Processing {filename} with {size}")
   ```

4. **Log exceptions properly**:
   ```python
   try:
       risky_operation()
   except Exception as e:
       logger.error(f"Operation failed: {e}", exc_info=True)
   ```

5. **Keep user output separate**:
   - Use `logger` for internal operations
   - Use `print()` for direct user interaction (like `input()` prompts)
   - Note: The current implementation keeps console logs clean without timestamps
