"""
╔════════════════════════════════════════════════════════════════════════════╗
║                      Logger - AutoScaleOps                                 ║
║                      Centralized Logging System                            ║
╚════════════════════════════════════════════════════════════════════════════╝

Purpose: Centralized logging with file rotation, cloud logging support,
         and structured log management.

Usage:
    from core.logger import get_logger
    
    logger = get_logger(__name__)
    logger.info("Application started")
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
from datetime import datetime

from .config_manager import get_config_manager


class ColoredFormatter(logging.Formatter):
    """Colored console output formatter"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # Add color to levelname
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        
        return super().format(record)


class AutoScaleOpsLogger:
    """Centralized logging manager for AutoScaleOps"""
    
    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize logger
        
        Args:
            log_dir: Directory for log files (defaults to ~/.autoscaleops/logs/)
        """
        if log_dir is None:
            log_dir = Path.home() / ".autoscaleops" / "logs"
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.config = get_config_manager()
        self._configured = False
    
    def configure(self):
        """Configure logging system"""
        if self._configured:
            return
        
        # Get log level from config
        log_level_str = self.config.get('logging.level', 'INFO')
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Console handler (colored)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        
        console_format = ColoredFormatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        root_logger.addHandler(console_handler)
        
        # File handler (rotating)
        log_file = self.log_dir / "autoscaleops.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        
        file_format = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        root_logger.addHandler(file_handler)
        
        # Error file handler (only errors and critical)
        error_file = self.log_dir / "errors.log"
        error_handler = RotatingFileHandler(
            error_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_format)
        root_logger.addHandler(error_handler)
        
        # Cloud logging (if enabled)
        cloud_enabled = self.config.get('logging.cloud_enabled', False)
        if cloud_enabled:
            self._setup_cloud_logging()
        
        self._configured = True
        root_logger.info("Logging system configured")
    
    def _setup_cloud_logging(self):
        """Setup cloud logging (BetterStack, etc.)"""
        try:
            cloud_provider = self.config.get('logging.cloud_provider')
            
            if cloud_provider == 'betterstack':
                self._setup_betterstack_logging()
            else:
                logging.warning(f"Unknown cloud logging provider: {cloud_provider}")
        
        except Exception as e:
            logging.error(f"Cloud logging setup failed: {e}")
    
    def _setup_betterstack_logging(self):
        """Setup BetterStack logging"""
        try:
            from .security import get_secret
            
            # Get BetterStack token from secrets
            token = get_secret('betterstack_token')
            
            if not token:
                logging.warning("BetterStack token not found in secrets")
                return
            
            # Note: BetterStack integration would go here
            # For now, we just log that it would be enabled
            logging.info("BetterStack logging would be enabled (integration pending)")
        
        except Exception as e:
            logging.error(f"BetterStack setup failed: {e}")
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger instance
        
        Args:
            name: Logger name (usually __name__)
        
        Returns:
            Logger instance
        """
        if not self._configured:
            self.configure()
        
        return logging.getLogger(name)
    
    def set_level(self, level: str):
        """
        Change log level dynamically
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        try:
            log_level = getattr(logging, level.upper())
            
            root_logger = logging.getLogger()
            root_logger.setLevel(log_level)
            
            for handler in root_logger.handlers:
                handler.setLevel(log_level)
            
            # Save to config
            self.config.set('logging.level', level.upper())
            
            logging.info(f"Log level changed to {level.upper()}")
        
        except AttributeError:
            logging.error(f"Invalid log level: {level}")
    
    def get_log_files(self) -> list:
        """
        Get list of log files
        
        Returns:
            List of log file paths
        """
        try:
            return sorted(self.log_dir.glob("*.log*"))
        except Exception as e:
            logging.error(f"Error listing log files: {e}")
            return []
    
    def get_recent_logs(self, lines: int = 100, level: Optional[str] = None) -> list:
        """
        Get recent log entries
        
        Args:
            lines: Number of lines to return
            level: Filter by log level (optional)
        
        Returns:
            List of log lines
        """
        try:
            log_file = self.log_dir / "autoscaleops.log"
            
            if not log_file.exists():
                return []
            
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
            
            # Filter by level if specified
            if level:
                level_upper = level.upper()
                filtered_lines = [
                    line for line in all_lines
                    if level_upper in line
                ]
            else:
                filtered_lines = all_lines
            
            # Return last N lines
            return filtered_lines[-lines:]
        
        except Exception as e:
            logging.error(f"Error reading logs: {e}")
            return []
    
    def clear_logs(self):
        """Clear all log files"""
        try:
            for log_file in self.get_log_files():
                log_file.unlink()
            
            logging.info("All log files cleared")
        
        except Exception as e:
            logging.error(f"Error clearing logs: {e}")
    
    def export_logs(self, output_path: Path, start_date: Optional[datetime] = None):
        """
        Export logs to file
        
        Args:
            output_path: Output file path
            start_date: Only export logs after this date (optional)
        """
        try:
            log_file = self.log_dir / "autoscaleops.log"
            
            if not log_file.exists():
                logging.warning("No logs to export")
                return
            
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Filter by date if specified
            if start_date:
                filtered_lines = []
                for line in lines:
                    try:
                        # Parse date from log line
                        date_str = line.split(' - ')[0]
                        log_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        
                        if log_date >= start_date:
                            filtered_lines.append(line)
                    except:
                        # If parsing fails, include the line
                        filtered_lines.append(line)
            else:
                filtered_lines = lines
            
            # Write to output file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.writelines(filtered_lines)
            
            logging.info(f"Logs exported to {output_path}")
        
        except Exception as e:
            logging.error(f"Export failed: {e}")


# Singleton instance
_logger_manager = None

def get_logger_manager() -> AutoScaleOpsLogger:
    """
    Get the singleton logger manager
    
    Returns:
        AutoScaleOpsLogger instance
    """
    global _logger_manager
    if _logger_manager is None:
        _logger_manager = AutoScaleOpsLogger()
        _logger_manager.configure()
    return _logger_manager


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Logger instance
    
    Example:
        logger = get_logger(__name__)
        logger.info("Application started")
    """
    return get_logger_manager().get_logger(name)


def set_log_level(level: str):
    """
    Change log level dynamically
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    get_logger_manager().set_level(level)


if __name__ == "__main__":
    # Test the logger
    logger = get_logger(__name__)
    
    print("="*60)
    print("AutoScaleOps Logger Test")
    print("="*60)
    
    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")
    logger.critical("This is a CRITICAL message")
    
    print("\nLog files:")
    manager = get_logger_manager()
    for log_file in manager.get_log_files():
        print(f"  - {log_file}")
    
    print("\nRecent logs (last 5 lines):")
    for line in manager.get_recent_logs(lines=5):
        print(f"  {line.strip()}")
    
    print("="*60)