# Property-Based Test: Comprehensive Event Logging
# Feature: pico-wifi-hardening, Property 8: Comprehensive Event Logging

import pytest
import time
from hypothesis import given, strategies as st, settings
from pico_device.logging_utils import (
    Logger, LogLevel, LogCategory, LogEntry, ContextLogger,
    get_logger, init_logger, log_config_decision, log_wifi_event,
    log_setup_activation, log_file_operation, log_network_event,
    log_system_event, log_security_event
)

class TestComprehensiveEventLoggingProperty:
    """
    Property 8: Comprehensive Event Logging
    For any configuration decision, Setup AP activation, or WiFi connection event,
    the system should log the event with timestamp, reason, and relevant context information.
    
    **Validates: Requirements 5.1, 5.2, 5.5**
    """
    
    def setup_method(self):
        """Setup fresh logger for each test"""
        init_logger(max_entries=50, enable_console=False)
    
    @given(
        level=st.sampled_from(list(LogLevel)),
        category=st.sampled_from(list(LogCategory)),
        message=st.text(min_size=1, max_size=100),
        context_keys=st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=5),
        context_values=st.lists(st.one_of(st.text(max_size=50), st.integers(), st.booleans()), min_size=0, max_size=5)
    )
    @settings(max_examples=50, deadline=3000)
    def test_log_entry_creation_and_formatting(self, level, category, message, context_keys, context_values):
        """
        Property: Log entry creation and formatting consistency
        
        For any log level, category, message, and context:
        1. Log entry should be created with correct attributes
        2. Timestamp should be automatically assigned
        3. Formatting should be consistent and readable
        4. Context should be preserved accurately
        """
        # Create context dictionary
        context = {}
        for i, key in enumerate(context_keys):
            if i < len(context_values):
                context[key] = context_values[i]
        
        # Create log entry
        entry = LogEntry(level, category, message, context)
        
        # Verify basic attributes
        assert entry.level == level, "Log level should be preserved"
        assert entry.category == category, "Log category should be preserved"
        assert entry.message == message, "Log message should be preserved"
        assert entry.context == context, "Log context should be preserved"
        assert isinstance(entry.timestamp, (int, float)), "Timestamp should be numeric"
        assert entry.timestamp > 0, "Timestamp should be positive"
        
        # Test dictionary conversion
        entry_dict = entry.to_dict()
        assert entry_dict['level'] == level.value, "Dictionary should contain level value"
        assert entry_dict['category'] == category.value, "Dictionary should contain category value"
        assert entry_dict['message'] == message, "Dictionary should contain message"
        assert entry_dict['context'] == context, "Dictionary should contain context"
        assert entry_dict['timestamp'] == entry.timestamp, "Dictionary should contain timestamp"
        
        # Test message formatting
        formatted = entry.format_message()
        assert level.value in formatted, "Formatted message should contain level"
        assert category.value in formatted, "Formatted message should contain category"
        assert message in formatted, "Formatted message should contain original message"
        
        # Verify context appears in formatted message if present
        if context:
            for key in context.keys():
                assert key in formatted, f"Context key {key} should appear in formatted message"
    
    @given(
        log_count=st.integers(min_value=1, max_value=20),
        max_entries=st.integers(min_value=5, max_value=15)
    )
    @settings(max_examples=30, deadline=4000)
    def test_logger_entry_management_and_limits(self, log_count, max_entries):
        """
        Property: Logger entry management and size limits
        
        For any number of log entries and maximum entry limit:
        1. Logger should maintain entries up to the limit
        2. Oldest entries should be removed when limit is exceeded
        3. Counters should be accurate
        4. Recent entries should be retrievable
        """
        logger = Logger(max_entries=max_entries, enable_console=False)
        
        # Generate log entries
        entries_data = []
        for i in range(log_count):
            level = LogLevel.INFO
            category = LogCategory.SYSTEM
            message = f"Test message {i}"
            context = {'index': i, 'batch': 'test'}
            
            logger.log(level, category, message, context)
            entries_data.append((level, category, message, context))
        
        # Verify entry count respects limit
        actual_count = len(logger.log_entries)
        expected_count = min(log_count, max_entries)
        assert actual_count == expected_count, f"Logger should contain {expected_count} entries, got {actual_count}"
        
        # Verify counters are accurate
        summary = logger.get_log_summary()
        assert summary['total_entries'] == expected_count, "Summary should reflect actual entry count"
        assert summary['counts_by_level']['INFO'] == log_count, "Level counter should track all logged entries"
        assert summary['counts_by_category']['SYSTEM'] == log_count, "Category counter should track all logged entries"
        
        # Verify most recent entries are preserved
        if log_count > max_entries:
            # Should have the last max_entries entries
            expected_start_index = log_count - max_entries
            for i, entry in enumerate(logger.log_entries):
                expected_index = expected_start_index + i
                assert entry.context['index'] == expected_index, f"Entry {i} should have index {expected_index}"
        
        # Test recent log retrieval
        recent_logs = logger.get_recent_logs(count=5)
        assert len(recent_logs) <= 5, "Should return at most 5 recent logs"
        assert len(recent_logs) <= actual_count, "Should not return more logs than available"
        
        # Verify recent logs are actually the most recent
        if recent_logs:
            for i in range(1, len(recent_logs)):
                assert recent_logs[i].timestamp >= recent_logs[i-1].timestamp, "Recent logs should be in chronological order"
    
    @given(
        source=st.text(min_size=1, max_size=30),
        reason=st.text(min_size=1, max_size=100),
        success=st.booleans()
    )
    @settings(max_examples=30, deadline=3000)
    def test_config_decision_logging(self, source, reason, success):
        """
        Property: Configuration decision logging consistency
        
        For any configuration source and decision reason:
        1. Decision should be logged with appropriate level
        2. Context should include source and success status
        3. Log should be retrievable and properly formatted
        """
        logger = get_logger()
        initial_count = len(logger.log_entries)
        
        # Log configuration decision
        log_config_decision(source, reason, success)
        
        # Verify log was created
        assert len(logger.log_entries) == initial_count + 1, "Configuration decision should create log entry"
        
        # Get the logged entry
        entry = logger.log_entries[-1]
        
        # Verify entry properties
        assert entry.category == LogCategory.CONFIG, "Should use CONFIG category"
        assert entry.message == reason, "Should log the reason as message"
        assert entry.context['source'] == source, "Should include source in context"
        assert entry.context['success'] == success, "Should include success status in context"
        
        # Verify log level based on success
        if success:
            assert entry.level == LogLevel.INFO, "Successful decisions should use INFO level"
        else:
            assert entry.level == LogLevel.WARNING, "Failed decisions should use WARNING level"
    
    @given(
        event_type=st.text(min_size=1, max_size=20),
        details=st.text(min_size=1, max_size=100),
        success=st.booleans(),
        failure_count=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=30, deadline=3000)
    def test_wifi_event_logging(self, event_type, details, success, failure_count):
        """
        Property: WiFi event logging consistency
        
        For any WiFi event type, details, and success status:
        1. Event should be logged with appropriate level
        2. Context should include event type and failure count
        3. Success/failure should determine log level
        """
        logger = get_logger()
        initial_count = len(logger.log_entries)
        
        # Log WiFi event
        log_wifi_event(event_type, details, success, {'failure_count': failure_count})
        
        # Verify log was created
        assert len(logger.log_entries) == initial_count + 1, "WiFi event should create log entry"
        
        # Get the logged entry
        entry = logger.log_entries[-1]
        
        # Verify entry properties
        assert entry.category == LogCategory.WIFI, "Should use WIFI category"
        assert entry.message == details, "Should log details as message"
        assert entry.context['event_type'] == event_type, "Should include event type in context"
        assert entry.context['success'] == success, "Should include success status in context"
        assert entry.context['failure_count'] == failure_count, "Should include failure count in context"
        
        # Verify log level based on success
        if success:
            assert entry.level == LogLevel.INFO, "Successful WiFi events should use INFO level"
        else:
            assert entry.level == LogLevel.ERROR, "Failed WiFi events should use ERROR level"
    
    @given(
        reason=st.text(min_size=1, max_size=50),
        ssid=st.text(min_size=1, max_size=32),
        device_id=st.text(min_size=1, max_size=20)
    )
    @settings(max_examples=20, deadline=3000)
    def test_setup_activation_logging(self, reason, ssid, device_id):
        """
        Property: Setup AP activation logging consistency
        
        For any Setup AP activation reason and SSID:
        1. Activation should be logged as CRITICAL level
        2. Context should include reason and SSID
        3. Message should indicate Setup AP activation
        """
        logger = get_logger()
        initial_count = len(logger.log_entries)
        
        # Log Setup AP activation
        log_setup_activation(reason, ssid, {'device_id': device_id})
        
        # Verify log was created
        assert len(logger.log_entries) == initial_count + 1, "Setup activation should create log entry"
        
        # Get the logged entry
        entry = logger.log_entries[-1]
        
        # Verify entry properties
        assert entry.level == LogLevel.CRITICAL, "Setup activation should use CRITICAL level"
        assert entry.category == LogCategory.SETUP, "Should use SETUP category"
        assert "Setup AP activated" in entry.message, "Message should indicate Setup AP activation"
        assert reason in entry.message, "Message should include activation reason"
        assert entry.context['reason'] == reason, "Should include reason in context"
        assert entry.context['ssid'] == ssid, "Should include SSID in context"
        assert entry.context['device_id'] == device_id, "Should include device ID in context"
    
    @given(
        operation=st.sampled_from(['load', 'save', 'backup', 'restore', 'delete']),
        file_path=st.text(min_size=1, max_size=50),
        success=st.booleans(),
        error_message=st.text(min_size=0, max_size=100)
    )
    @settings(max_examples=30, deadline=3000)
    def test_file_operation_logging(self, operation, file_path, success, error_message):
        """
        Property: File operation logging consistency
        
        For any file operation, path, and success status:
        1. Operation should be logged with appropriate level
        2. Context should include operation details
        3. Error information should be included for failures
        """
        logger = get_logger()
        initial_count = len(logger.log_entries)
        
        # Prepare additional context
        additional_context = {}
        if not success and error_message:
            additional_context['error'] = error_message
        
        # Log file operation
        log_file_operation(operation, file_path, success, additional_context)
        
        # Verify log was created
        assert len(logger.log_entries) == initial_count + 1, "File operation should create log entry"
        
        # Get the logged entry
        entry = logger.log_entries[-1]
        
        # Verify entry properties
        assert entry.category == LogCategory.FILE, "Should use FILE category"
        assert operation in entry.message, "Message should include operation type"
        assert file_path in entry.message, "Message should include file path"
        assert entry.context['operation'] == operation, "Should include operation in context"
        assert entry.context['file_path'] == file_path, "Should include file path in context"
        assert entry.context['success'] == success, "Should include success status in context"
        
        # Verify log level based on success
        if success:
            assert entry.level == LogLevel.INFO, "Successful file operations should use INFO level"
        else:
            assert entry.level == LogLevel.ERROR, "Failed file operations should use ERROR level"
            if error_message:
                assert entry.context['error'] == error_message, "Should include error message in context"
    
    @given(
        operation_name=st.text(min_size=1, max_size=30),
        context_data=st.dictionaries(
            keys=st.text(min_size=1, max_size=10),
            values=st.one_of(st.text(max_size=20), st.integers(), st.booleans()),
            min_size=0,
            max_size=3
        ),
        should_succeed=st.booleans()
    )
    @settings(max_examples=20, deadline=4000)
    def test_context_logger_operation_tracking(self, operation_name, context_data, should_succeed):
        """
        Property: Context logger operation tracking
        
        For any operation with context data:
        1. Start and completion should be logged
        2. Duration should be tracked
        3. Context should be preserved
        4. Failures should be logged appropriately
        """
        logger = get_logger()
        initial_count = len(logger.log_entries)
        
        # Use context logger
        try:
            with ContextLogger(LogCategory.SYSTEM, operation_name, context_data) as ctx:
                # Add some context during operation
                ctx.add_context('test_key', 'test_value')
                
                # Simulate work
                time.sleep(0.01)
                
                # Simulate failure if needed
                if not should_succeed:
                    raise ValueError("Simulated operation failure")
        except ValueError:
            # Expected for failure cases
            pass
        
        # Verify logs were created
        new_entries = logger.log_entries[initial_count:]
        
        if should_succeed:
            # Should have start and completion logs
            assert len(new_entries) >= 2, "Should have start and completion logs for successful operation"
            
            start_entry = new_entries[0]
            completion_entry = new_entries[-1]
            
            # Verify start log
            assert "Starting" in start_entry.message, "Start log should indicate operation start"
            assert operation_name in start_entry.message, "Start log should include operation name"
            
            # Verify completion log
            assert "Completed" in completion_entry.message, "Completion log should indicate operation completion"
            assert operation_name in completion_entry.message, "Completion log should include operation name"
            assert 'duration' in completion_entry.context, "Completion log should include duration"
            assert completion_entry.context['duration'] >= 0, "Duration should be non-negative"
            
        else:
            # Should have start and failure logs
            assert len(new_entries) >= 2, "Should have start and failure logs for failed operation"
            
            start_entry = new_entries[0]
            failure_entry = new_entries[-1]
            
            # Verify failure log
            assert "Failed" in failure_entry.message, "Failure log should indicate operation failure"
            assert operation_name in failure_entry.message, "Failure log should include operation name"
            assert 'error' in failure_entry.context, "Failure log should include error information"
            assert 'duration' in failure_entry.context, "Failure log should include duration"
    
    def test_log_filtering_and_retrieval(self):
        """
        Property: Log filtering and retrieval accuracy
        
        Logs should be filterable by level and category with accurate results.
        """
        logger = get_logger()
        
        # Create logs with different levels and categories
        test_logs = [
            (LogLevel.INFO, LogCategory.CONFIG, "Config info"),
            (LogLevel.ERROR, LogCategory.CONFIG, "Config error"),
            (LogLevel.INFO, LogCategory.WIFI, "WiFi info"),
            (LogLevel.WARNING, LogCategory.WIFI, "WiFi warning"),
            (LogLevel.CRITICAL, LogCategory.SETUP, "Setup critical"),
        ]
        
        for level, category, message in test_logs:
            logger.log(level, category, message)
        
        # Test filtering by level
        info_logs = logger.get_recent_logs(count=10, level=LogLevel.INFO)
        assert len(info_logs) == 2, "Should find 2 INFO level logs"
        assert all(entry.level == LogLevel.INFO for entry in info_logs), "All filtered logs should be INFO level"
        
        # Test filtering by category
        config_logs = logger.get_recent_logs(count=10, category=LogCategory.CONFIG)
        assert len(config_logs) == 2, "Should find 2 CONFIG category logs"
        assert all(entry.category == LogCategory.CONFIG for entry in config_logs), "All filtered logs should be CONFIG category"
        
        # Test combined filtering
        config_info_logs = logger.get_recent_logs(count=10, level=LogLevel.INFO, category=LogCategory.CONFIG)
        assert len(config_info_logs) == 1, "Should find 1 CONFIG INFO log"
        assert config_info_logs[0].level == LogLevel.INFO, "Filtered log should be INFO level"
        assert config_info_logs[0].category == LogCategory.CONFIG, "Filtered log should be CONFIG category"
    
    def test_log_export_functionality(self):
        """
        Property: Log export functionality
        
        Logs should be exportable in different formats with consistent data.
        """
        logger = get_logger()
        
        # Create test logs
        logger.info(LogCategory.SYSTEM, "Test info message", {'key': 'value'})
        logger.error(LogCategory.WIFI, "Test error message", {'error_code': 123})
        
        # Test text export
        text_export = logger.export_logs(format_type="text")
        assert isinstance(text_export, str), "Text export should return string"
        assert "Test info message" in text_export, "Text export should contain log messages"
        assert "Test error message" in text_export, "Text export should contain all log messages"
        assert "INFO" in text_export, "Text export should contain log levels"
        assert "ERROR" in text_export, "Text export should contain log levels"
        
        # Test JSON export
        json_export = logger.export_logs(format_type="json")
        assert isinstance(json_export, str), "JSON export should return string"
        
        # Parse JSON to verify structure
        import json
        parsed_logs = json.loads(json_export)
        assert isinstance(parsed_logs, list), "JSON export should be a list"
        assert len(parsed_logs) == 2, "JSON export should contain all log entries"
        
        # Verify JSON structure
        for log_entry in parsed_logs:
            assert 'timestamp' in log_entry, "JSON log should contain timestamp"
            assert 'level' in log_entry, "JSON log should contain level"
            assert 'category' in log_entry, "JSON log should contain category"
            assert 'message' in log_entry, "JSON log should contain message"
            assert 'context' in log_entry, "JSON log should contain context"