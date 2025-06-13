"""
Configuration du logger pour TrackImmo.
Single daily log file with 30-day retention.
"""

import os
import sys
import logging
import glob
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta

# Créer le dossier de logs s'il n'existe pas
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Global logger instance to ensure single configuration
_logger_configured = False
_main_logger = None

def cleanup_old_logs():
    """Remove log files older than 30 days."""
    try:
        cutoff_date = datetime.now() - timedelta(days=30)
        log_pattern = LOG_DIR / "trackimmo-*.log*"
        
        for log_file in glob.glob(str(log_pattern)):
            log_path = Path(log_file)
            if log_path.exists():
                # Get file modification time
                file_time = datetime.fromtimestamp(log_path.stat().st_mtime)
                if file_time < cutoff_date:
                    try:
                        log_path.unlink()
                        print(f"Removed old log file: {log_file}")
                    except OSError as e:
                        print(f"Could not remove old log file {log_file}: {e}")
    except Exception as e:
        print(f"Error during log cleanup: {e}")

def get_logger(name=None):
    """
    Get the configured logger instance.
    All modules will use the same logger with a single daily log file.
    
    Args:
        name: Module name (kept for compatibility, but all use same logger)
        
    Returns:
        logging.Logger: Configured logger
    """
    global _logger_configured, _main_logger
    
    if _logger_configured and _main_logger:
        return _main_logger
    
    # Import settings here to avoid circular imports
    try:
        from trackimmo.config import settings
        log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    except ImportError:
        # Fallback if settings not available
        log_level = logging.INFO
    
    # Create main logger - set to DEBUG so all messages reach handlers
    _main_logger = logging.getLogger("trackimmo")
    _main_logger.setLevel(logging.DEBUG)  # Logger accepts all levels, handlers filter
    
    # Clear any existing handlers to avoid duplicates
    _main_logger.handlers.clear()
    
    # Formatage with full timestamp
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler - respects configured log level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    _main_logger.addHandler(console_handler)
    
    # Daily rotating file handler - gets all levels including DEBUG
    log_filename = LOG_DIR / "trackimmo.log"
    file_handler = TimedRotatingFileHandler(
        filename=str(log_filename),
        when='midnight',
        interval=1,
        backupCount=30,  # Keep 30 days of logs
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # File gets all levels
    file_handler.setFormatter(formatter)
    
    # Set the suffix for rotated files to include date
    file_handler.suffix = "%Y-%m-%d"
    
    _main_logger.addHandler(file_handler)
    
    # Cleanup old logs on first initialization
    cleanup_old_logs()
    
    # Prevent propagation to root logger
    _main_logger.propagate = False
    
    _logger_configured = True
    return _main_logger

def get_module_logger(module_name):
    """
    Get a logger for a specific module.
    This creates a child logger that inherits from the main logger.
    
    Args:
        module_name: Name of the module
        
    Returns:
        logging.Logger: Module-specific logger
    """
    main_logger = get_logger()
    return main_logger.getChild(module_name.split('.')[-1])