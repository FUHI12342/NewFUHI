# Logging utilities for Pico 2 W WiFi Hardening
# Provides comprehensive event logging with timestamps and context

import time

# Log level constants (replacing Enum)
LOG_LEVEL_DEBUG = "DEBUG"
LOG_LEVEL_INFO = "INFO"
LOG_LEVEL_WARNING = "WARNING"
LOG_LEVEL_ERROR = "ERROR"
LOG_LEVEL_CRITICAL = "CRITICAL"

# Log category constants (replacing Enum)
LOG_CATEGORY_CONFIG = "CONFIG"
LOG_CATEGORY_WIFI = "WIFI"
LOG_CATEGORY_SETUP = "SETUP"
LOG_CATEGORY_FILE = "FILE"
LOG_CATEGORY_NETWORK = "NETWORK"
LOG_CATEGORY_SYSTEM = "SYSTEM"
LOG_CATEGORY_SECURITY = "SECURITY"

class LogEntry:
    """Represents a single log entry with timestamp and context"""
    
    def __init__(self, level, category, message, 
                 context=None, timestamp=None):
        self.level = level
        self.category = category
        self.message = message
        self.context = context or {}
        self.timestamp = timestamp or time.time()
    
    def to_dict(self):
        """Convert log entry to dictionary format"""
        return {
            'timestamp': self.timestamp,
            'level': self.level,
            'category': self.category,
            'message': self.message,
            'context': self.context
        }
    
    def format_message(self):
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
        
        return f"[{time_str}] [{self.level}] [{self.category}] {self.message}{context_str}"

class Logger:
    """Comprehensive logging system for Pico 2 W WiFi Hardening"""
    
    def __init__(self, max_entries = 100, enable_console = True):
        self.max_entries = max_entries
        self.enable_console = enable_console
        self.log_entries = []
        self.log_counts = {}
        
        # Initialize counters
        for level in [LOG_LEVEL_DEBUG, LOG_LEVEL_INFO, LOG_LEVEL_WARNING, LOG_LEVEL_ERROR, LOG_LEVEL_CRITICAL]:
            self.log_counts[level] = 0
        for category in [LOG_CATEGORY_CONFIG, LOG_CATEGORY_WIFI, LOG_CATEGORY_SETUP, LOG_CATEGORY_FILE, LOG_CATEGORY_NETWORK, LOG_CATEGORY_SYSTEM, LOG_CATEGORY_SECURITY]:
            self.log_counts[f"cat_{category}"] = 0
    
    def log(self, level, category, message,
            context=None):
        """Log a message with specified level and category"""
        entry = LogEntry(level, category, message, context)
        
        # Add to log entries
        self.log_entries.append(entry)
        
        # Maintain max entries limit
        if len(self.log_entries) > self.max_entries:
            self.log_entries.pop(0)
        
        # Update counters
        self.log_counts[level] += 1
        self.log_counts[f"cat_{category}"] += 1
        
        # Console output
        if self.enable_console:
            print(entry.format_message())
    
    def debug(self, category, message, context=None):
        """Log debug message"""
        self.log(LOG_LEVEL_DEBUG, category, message, context)
    
    def info(self, category, message, context=None):
        """Log info message"""
        self.log(LOG_LEVEL_INFO, category, message, context)
    
    def warning(self, category, message, context=None):
        """Log warning message"""
        self.log(LOG_LEVEL_WARNING, category, message, context)
    
    def error(self, category, message, context=None):
        """Log error message"""
        self.log(LOG_LEVEL_ERROR, category, message, context)
    
    def critical(self, category, message, context=None):
        """Log critical message"""
        self.log(LOG_LEVEL_CRITICAL, category, message, context)
    
    def get_recent_logs(self, count = 10, level = None, 
                       category = None):
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
    
    def get_log_summary(self):
        """Get summary of log statistics"""
        return {
            'total_entries': len(self.log_entries),
            'counts_by_level': {level: self.log_counts[level] for level in [LOG_LEVEL_DEBUG, LOG_LEVEL_INFO, LOG_LEVEL_WARNING, LOG_LEVEL_ERROR, LOG_LEVEL_CRITICAL]},
            'counts_by_category': {cat: self.log_counts[f"cat_{cat}"] for cat in [LOG_CATEGORY_CONFIG, LOG_CATEGORY_WIFI, LOG_CATEGORY_SETUP, LOG_CATEGORY_FILE, LOG_CATEGORY_NETWORK, LOG_CATEGORY_SYSTEM, LOG_CATEGORY_SECURITY]},
            'oldest_timestamp': self.log_entries[0].timestamp if self.log_entries else None,
            'newest_timestamp': self.log_entries[-1].timestamp if self.log_entries else None
        }
    
    def clear_logs(self):
        """Clear all log entries and reset counters"""
        self.log_entries.clear()
        for key in self.log_counts:
            self.log_counts[key] = 0
    
    def export_logs(self, format_type = "text"):
        """Export logs in specified format"""
        if format_type == "text":
            return "\n".join(entry.format_message() for entry in self.log_entries)
        elif format_type == "json":
            import json
            return json.dumps([entry.to_dict() for entry in self.log_entries], indent=2)
        else:
            raise ValueError(f"Unsupported format type: {format_type}")

# Global logger instance
_global_logger = None

def get_logger() -> Logger:
    """Get global logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = Logger()
    return _global_logger

def init_logger(max_entries = 100, enable_console = True) -> Logger:
    """Initialize global logger with custom settings"""
    global _global_logger
    _global_logger = Logger(max_entries, enable_console)
    return _global_logger

# Convenience functions for common logging patterns
def log_config_decision(source, reason, success = True, 
                       additional_context=None):
    """Log configuration source selection and rejection decisions"""
    logger = get_logger()
    context = {'source': source, 'success': success}
    if additional_context:
        context.update(additional_context)
    
    level = LOG_LEVEL_INFO if success else LOG_LEVEL_WARNING
    logger.log(level, LOG_CATEGORY_CONFIG, reason, context)

def log_wifi_event(event_type, details, success = True,
                  additional_context=None):
    """Log WiFi connection events"""
    logger = get_logger()
    context = {'event_type': event_type, 'success': success}
    if additional_context:
        context.update(additional_context)
    
    level = LOG_LEVEL_INFO if success else LOG_LEVEL_ERROR
    logger.log(level, LOG_CATEGORY_WIFI, details, context)

def log_setup_activation(reason, ssid, additional_context=None):
    """Log Setup AP activation events"""
    logger = get_logger()
    context = {'reason': reason, 'ssid': ssid}
    if additional_context:
        context.update(additional_context)
    
    logger.log(LOG_LEVEL_CRITICAL, LOG_CATEGORY_SETUP, f"Setup AP activated: {reason}", context)

def log_file_operation(operation, file_path, success = True,
                      additional_context=None):
    """Log file operations"""
    logger = get_logger()
    context = {'operation': operation, 'file_path': file_path, 'success': success}
    if additional_context:
        context.update(additional_context)
    
    level = LOG_LEVEL_INFO if success else LOG_LEVEL_ERROR
    logger.log(level, LOG_CATEGORY_FILE, f"File {operation}: {file_path}", context)

def log_network_event(event_type, details, success = True,
                     additional_context=None):
    """Log network-related events"""
    logger = get_logger()
    context = {'event_type': event_type, 'success': success}
    if additional_context:
        context.update(additional_context)
    
    level = LOG_LEVEL_INFO if success else LOG_LEVEL_WARNING
    logger.log(level, LOG_CATEGORY_NETWORK, details, context)

def log_system_event(event_type, details, level = LOG_LEVEL_INFO,
                    additional_context=None):
    """Log system-level events"""
    logger = get_logger()
    context = {'event_type': event_type}
    if additional_context:
        context.update(additional_context)
    
    logger.log(level, LOG_CATEGORY_SYSTEM, details, context)

def log_security_event(event_type, details, severity = "medium",
                      additional_context=None):
    """Log security-related events"""
    logger = get_logger()
    context = {'event_type': event_type, 'severity': severity}
    if additional_context:
        context.update(additional_context)
    
    # Map severity to log level
    level_map = {
        'low': LOG_LEVEL_INFO,
        'medium': LOG_LEVEL_WARNING,
        'high': LOG_LEVEL_ERROR,
        'critical': LOG_LEVEL_CRITICAL
    }
    level = level_map.get(severity, LOG_LEVEL_WARNING)
    
    logger.log(level, LOG_CATEGORY_SECURITY, details, context)

class ContextLogger:
    """Context manager for logging with automatic success/failure tracking"""
    
    def __init__(self, category, operation, context=None):
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
    
    def add_context(self, key, value):
        """Add additional context during operation"""
        self.context[key] = value