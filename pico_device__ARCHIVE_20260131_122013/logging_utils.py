# Logging utilities for Pico 2 W WiFi Hardening
# Provides comprehensive event logging with timestamps and context

import time
from typing import Dict, Any, List, Optional
from enum import Enum

class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class LogCategory(Enum):
    CONFIG = "CONFIG"
    WIFI = "WIFI"
    SETUP = "SETUP"
    FILE = "FILE"
    NETWORK = "NETWORK"
    SYSTEM = "SYSTEM"
    SECURITY = "SECURITY"

class LogEntry:
    """Represents a single log entry with timestamp and context"""
    
    def __init__(self, level: LogLevel, category: LogCategory, message: str, 
                 context: Optional[Dict[str, Any]] = None, timestamp: Optional[float] = None):
        self.level = level
        self.category = category
        self.message = message
        self.context = context or {}
        self.timestamp = timestamp or time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to dictionary format"""
        return {
            'timestamp': self.timestamp,
            'level': self.level.value,
            'category': self.category.value,
            'message': self.message,
            'context': self.context
        }
    
    def format_message(self) -> str:
        """Format log entry as human-readable string"""
        # Convert timestamp to readable format
        try:
            # For CircuitPython compatibility, use simple time formatting
            time_str = f"{int(self.timestamp)}"
        except:
            time_str = "unknown"
        
        # Build context string
        context_str = ""
        if self.context:
            context_parts = []
            for key, value in self.context.items():
                context_parts.append(f"{key}={value}")
            if context_parts:
                context_str = f" [{', '.join(context_parts)}]"
        
        return f"[{time_str}] [{self.level.value}] [{self.category.value}] {self.message}{context_str}"

class Logger:
    """Comprehensive logging system for Pico 2 W WiFi Hardening"""
    
    def __init__(self, max_entries: int = 100, enable_console: bool = True):
        self.max_entries = max_entries
        self.enable_console = enable_console
        self.log_entries: List[LogEntry] = []
        self.log_counts: Dict[str, int] = {}
        
        # Initialize counters
        for level in LogLevel:
            self.log_counts[level.value] = 0
        for category in LogCategory:
            self.log_counts[f"cat_{category.value}"] = 0
    
    def log(self, level: LogLevel, category: LogCategory, message: str, 
            context: Optional[Dict[str, Any]] = None) -> None:
        """Log a message with specified level and category"""
        entry = LogEntry(level, category, message, context)
        
        # Add to log entries
        self.log_entries.append(entry)
        
        # Maintain max entries limit
        if len(self.log_entries) > self.max_entries:
            self.log_entries.pop(0)
        
        # Update counters
        self.log_counts[level.value] += 1
        self.log_counts[f"cat_{category.value}"] += 1
        
        # Console output
        if self.enable_console:
            print(entry.format_message())
    
    def debug(self, category: LogCategory, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log debug message"""
        self.log(LogLevel.DEBUG, category, message, context)
    
    def info(self, category: LogCategory, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log info message"""
        self.log(LogLevel.INFO, category, message, context)
    
    def warning(self, category: LogCategory, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log warning message"""
        self.log(LogLevel.WARNING, category, message, context)
    
    def error(self, category: LogCategory, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log error message"""
        self.log(LogLevel.ERROR, category, message, context)
    
    def critical(self, category: LogCategory, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log critical message"""
        self.log(LogLevel.CRITICAL, category, message, context)
    
    def get_recent_logs(self, count: int = 10, level: Optional[LogLevel] = None, 
                       category: Optional[LogCategory] = None) -> List[LogEntry]:
        """Get recent log entries with optional filtering"""
        filtered_entries = self.log_entries
        
        # Filter by level
        if level:
            filtered_entries = [entry for entry in filtered_entries if entry.level == level]
        
        # Filter by category
        if category:
            filtered_entries = [entry for entry in filtered_entries if entry.category == category]
        
        # Return most recent entries
        return filtered_entries[-count:] if count > 0 else filtered_entries
    
    def get_log_summary(self) -> Dict[str, Any]:
        """Get summary of log statistics"""
        return {
            'total_entries': len(self.log_entries),
            'counts_by_level': {level.value: self.log_counts[level.value] for level in LogLevel},
            'counts_by_category': {cat.value: self.log_counts[f"cat_{cat.value}"] for cat in LogCategory},
            'oldest_timestamp': self.log_entries[0].timestamp if self.log_entries else None,
            'newest_timestamp': self.log_entries[-1].timestamp if self.log_entries else None
        }
    
    def clear_logs(self) -> None:
        """Clear all log entries and reset counters"""
        self.log_entries.clear()
        for key in self.log_counts:
            self.log_counts[key] = 0
    
    def export_logs(self, format_type: str = "text") -> str:
        """Export logs in specified format"""
        if format_type == "text":
            return "\n".join(entry.format_message() for entry in self.log_entries)
        elif format_type == "json":
            import json
            return json.dumps([entry.to_dict() for entry in self.log_entries], indent=2)
        else:
            raise ValueError(f"Unsupported format type: {format_type}")

# Global logger instance
_global_logger: Optional[Logger] = None

def get_logger() -> Logger:
    """Get global logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = Logger()
    return _global_logger

def init_logger(max_entries: int = 100, enable_console: bool = True) -> Logger:
    """Initialize global logger with custom settings"""
    global _global_logger
    _global_logger = Logger(max_entries, enable_console)
    return _global_logger

# Convenience functions for common logging patterns
def log_config_decision(source: str, reason: str, success: bool = True, 
                       additional_context: Optional[Dict[str, Any]] = None) -> None:
    """Log configuration source selection and rejection decisions"""
    logger = get_logger()
    context = {'source': source, 'success': success}
    if additional_context:
        context.update(additional_context)
    
    level = LogLevel.INFO if success else LogLevel.WARNING
    logger.log(level, LogCategory.CONFIG, reason, context)

def log_wifi_event(event_type: str, details: str, success: bool = True,
                  additional_context: Optional[Dict[str, Any]] = None) -> None:
    """Log WiFi connection events"""
    logger = get_logger()
    context = {'event_type': event_type, 'success': success}
    if additional_context:
        context.update(additional_context)
    
    level = LogLevel.INFO if success else LogLevel.ERROR
    logger.log(level, LogCategory.WIFI, details, context)

def log_setup_activation(reason: str, ssid: str, additional_context: Optional[Dict[str, Any]] = None) -> None:
    """Log Setup AP activation events"""
    logger = get_logger()
    context = {'reason': reason, 'ssid': ssid}
    if additional_context:
        context.update(additional_context)
    
    logger.log(LogLevel.CRITICAL, LogCategory.SETUP, f"Setup AP activated: {reason}", context)

def log_file_operation(operation: str, file_path: str, success: bool = True,
                      additional_context: Optional[Dict[str, Any]] = None) -> None:
    """Log file operations"""
    logger = get_logger()
    context = {'operation': operation, 'file_path': file_path, 'success': success}
    if additional_context:
        context.update(additional_context)
    
    level = LogLevel.INFO if success else LogLevel.ERROR
    logger.log(level, LogCategory.FILE, f"File {operation}: {file_path}", context)

def log_network_event(event_type: str, details: str, success: bool = True,
                     additional_context: Optional[Dict[str, Any]] = None) -> None:
    """Log network-related events"""
    logger = get_logger()
    context = {'event_type': event_type, 'success': success}
    if additional_context:
        context.update(additional_context)
    
    level = LogLevel.INFO if success else LogLevel.WARNING
    logger.log(level, LogCategory.NETWORK, details, context)

def log_system_event(event_type: str, details: str, level: LogLevel = LogLevel.INFO,
                    additional_context: Optional[Dict[str, Any]] = None) -> None:
    """Log system-level events"""
    logger = get_logger()
    context = {'event_type': event_type}
    if additional_context:
        context.update(additional_context)
    
    logger.log(level, LogCategory.SYSTEM, details, context)

def log_security_event(event_type: str, details: str, severity: str = "medium",
                      additional_context: Optional[Dict[str, Any]] = None) -> None:
    """Log security-related events"""
    logger = get_logger()
    context = {'event_type': event_type, 'severity': severity}
    if additional_context:
        context.update(additional_context)
    
    # Map severity to log level
    level_map = {
        'low': LogLevel.INFO,
        'medium': LogLevel.WARNING,
        'high': LogLevel.ERROR,
        'critical': LogLevel.CRITICAL
    }
    level = level_map.get(severity, LogLevel.WARNING)
    
    logger.log(level, LogCategory.SECURITY, details, context)

class ContextLogger:
    """Context manager for logging with automatic success/failure tracking"""
    
    def __init__(self, category: LogCategory, operation: str, context: Optional[Dict[str, Any]] = None):
        self.category = category
        self.operation = operation
        self.context = context or {}
        self.logger = get_logger()
        self.start_time = None
        self.success = False
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.info(self.category, f"Starting {self.operation}", self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time if self.start_time else 0
        context = self.context.copy()
        context['duration'] = duration
        
        if exc_type is None:
            self.success = True
            self.logger.info(self.category, f"Completed {self.operation}", context)
        else:
            context['error'] = str(exc_val) if exc_val else "Unknown error"
            self.logger.error(self.category, f"Failed {self.operation}", context)
        
        return False  # Don't suppress exceptions
    
    def add_context(self, key: str, value: Any) -> None:
        """Add additional context during operation"""
        self.context[key] = value