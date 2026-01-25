from loguru import logger as _logger
import sys
import os
from pathlib import Path

logger = _logger

# Set up log file path based on whether the script is frozen (compiled with PyInstaller)
# Using user home directory for logs to avoid read-only file system issues in AppImage/packaged apps
log_dir = Path.home() / "Documents" / "AgentNetRecordings" / "logs"
os.makedirs(log_dir, exist_ok=True)
logger_path = log_dir / "runtime.log"

# Clear any existing handlers to avoid duplicate logs
logger.remove()

# Ensure stdout uses utf-8 encoding
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

# Add a handler for stdout (console output)
logger.add(sys.stdout, level="INFO", colorize=True)

# Add a handler for file logging
logger.add(logger_path, level="INFO", colorize=False, mode="w")

# Print the absolute path of the logger file
abs_logger_path = os.path.abspath(logger_path)
