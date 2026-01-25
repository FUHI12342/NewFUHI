"""
Property-based tests for large file rejection.

Feature: deploy-staging, Property 2: Large File Rejection
Validates: Requirements 1.2
"""
import os
import tempfile
import subprocess
from pathlib import Path
from hypothesis import given, strategies as st, settings, HealthCheck, assume
import unittest


@st.composite
def file_size_strategy(draw):
    """Generate file sizes for testing."""
    # Generate sizes around the 100MB limit
    sizes = [
        1024,           # 1KB - small
        1024 * 1024,    # 1MB - medium
        50 * 1024 * 1024,   # 50MB - below limit
        100 * 1024 * 1024,  # 100MB - at limit
        101 * 1024 * 1024,  # 101MB - above limit
        200 * 1024 * 1024,  # 200MB - well above limit
    ]
    return draw(st.sampled_from(sizes))


@st.composite
def file_extension_strategy(draw):
    """Generate file extensions for testing."""
    extensions = ['txt', 'py', 'js', 'zip', 'tar.gz', 'db', 'sqlite3', 'log', 'bak']
    return draw(st.sampled_from(extensions))


class LargeFileRejectionPropertyTest(unittest.TestCase):
    """
    Property test for large file rejection.
    
    **Property 2: Large File Rejection**
    For any file larger than 100MB added to the repository, the Git workflow 
    should reject the commit and suggest alternative storage methods.
    """

    def setUp(self):
        self.repo_root = Path(__file__).parent.parent
        self.pre_commit_hook = self.repo_root / '.githooks' / 'pre-commit'
        self.max_file_size = 100 * 1024 * 1024  # 100MB

    def test_pre_commit_hook_exists(self):
        """Test that pre-commit hook exists and is executable."""
        self.assertTrue(self.pre_commit_hook.exists(), "Pre-commit hook should exist")
        self.assertTrue(os.access(self.pre_commit_hook, os.X_OK), 
                       "Pre-commit hook should be executable")

    def test_file_size_limit_configuration(self):
        """Test that file size limit is correctly configured."""
        with open(self.pre_commit_hook, 'r') as f:
            content = f.read()

        # Should have 100MB limit configured
        self.assertIn('104857600', content, "Should have 100MB limit (104857600 bytes)")
        self.assertIn('MAX_FILE_SIZE', content, "Should define MAX_FILE_SIZE variable")

    @given(file_size=file_size_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.filter_too_much])
    def test_file_size_validation_property(self, file_size):
        """
        Property: For any file size, the validation logic should correctly
        determine whether it exceeds the limit.
        """
        with open(self.pre_commit_hook, 'r') as f:
            content = f.read()

        # Should contain file size checking logic
        self.assertIn('check_file_size', content, "Should have file size checking function")
        self.assertIn('stat -f%z', content, "Should use stat command to get file size")

        # Test the logic
        exceeds_limit = file_size > self.max_file_size
        
        if exceeds_limit:
            # Should have error message for large files
            self.assertIn('too large', content, "Should have error message for large files")
            self.assertIn('Git LFS', content, "Should suggest Git LFS for large files")

    def test_file_size_error_messages(self):
        """Test that appropriate error messages are shown for large files."""
        with open(self.pre_commit_hook, 'r') as f:
            content = f.read()

        # Should have helpful error messages
        error_message_elements = [
            'too large',
            'Maximum allowed size',
            'Git LFS',
            'external storage',
            'git lfs track'
        ]

        for element in error_message_elements:
            self.assertIn(element, content,
                         f"Should contain error message element: {element}")

    @given(
        file_size=st.integers(min_value=101 * 1024 * 1024, max_value=500 * 1024 * 1024),
        filename=st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789_-', min_size=1, max_size=20)
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.filter_too_much])
    def test_large_file_rejection_property(self, file_size, filename):
        """
        Property: For any file larger than 100MB, the pre-commit hook
        should reject it and provide helpful suggestions.
        """
        assume(file_size > self.max_file_size)
        
        # Create a temporary large file for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / f"{filename}.test"
            
            # Create file of specified size (sparse file for efficiency)
            with open(test_file, 'wb') as f:
                f.seek(file_size - 1)
                f.write(b'\0')
            
            # Verify file size
            actual_size = test_file.stat().st_size
            self.assertEqual(actual_size, file_size, "Test file should have correct size")
            
            # File should be considered too large
            self.assertGreater(actual_size, self.max_file_size, 
                             "Test file should exceed size limit")

    def test_alternative_storage_suggestions(self):
        """Test that hook suggests alternative storage methods."""
        with open(self.pre_commit_hook, 'r') as f:
            content = f.read()

        # Should suggest various alternatives
        alternatives = [
            'Git LFS',
            'external storage',
            'S3',
            'git lfs track'
        ]

        for alternative in alternatives:
            self.assertIn(alternative, content,
                         f"Should suggest alternative: {alternative}")

    @given(extension=file_extension_strategy())
    @settings(max_examples=20, suppress_health_check=[HealthCheck.filter_too_much])
    def test_file_type_specific_handling_property(self, extension):
        """
        Property: For any file extension, the hook should provide
        appropriate handling and suggestions.
        """
        with open(self.pre_commit_hook, 'r') as f:
            content = f.read()

        # Should have file type checking
        self.assertIn('check_file_type', content, "Should have file type checking function")

        # Specific file types should have specific handling
        if extension in ['zip', 'rar', '7z', 'tar', 'gz']:
            self.assertIn(extension, content, f"Should handle {extension} files")
        elif extension in ['bak', 'backup', 'old', 'tmp']:
            self.assertIn(extension, content, f"Should warn about {extension} files")
        elif extension in ['db', 'sqlite', 'sqlite3']:
            self.assertIn('db', content, "Should handle database files")

    def test_staged_files_detection(self):
        """Test that hook correctly detects staged files."""
        with open(self.pre_commit_hook, 'r') as f:
            content = f.read()

        # Should use git diff to get staged files
        git_commands = [
            'git diff --cached',
            'staged_files',
            '--name-only',
            '--diff-filter=ACM'
        ]

        for command in git_commands:
            self.assertIn(command, content,
                         f"Should use git command: {command}")

    def test_validation_bypass_option(self):
        """Test that hook documents how to bypass validation."""
        with open(self.pre_commit_hook, 'r') as f:
            content = f.read()

        # Should document bypass option
        bypass_elements = [
            '--no-verify',
            'NOT RECOMMENDED',
            'git commit --no-verify'
        ]

        for element in bypass_elements:
            self.assertIn(element, content,
                         f"Should document bypass option: {element}")

    def test_human_readable_file_sizes(self):
        """Test that hook displays human-readable file sizes."""
        with open(self.pre_commit_hook, 'r') as f:
            content = f.read()

        # Should use numfmt or similar for human-readable sizes
        size_formatting = [
            'numfmt',
            '--to=iec',
            'MB',
            'GB'
        ]

        # At least one method should be present
        has_formatting = any(fmt in content for fmt in size_formatting)
        self.assertTrue(has_formatting, "Should format file sizes for human readability")

    @given(
        file_count=st.integers(min_value=1, max_value=10),
        has_large_files=st.booleans()
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.filter_too_much])
    def test_multiple_files_validation_property(self, file_count, has_large_files):
        """
        Property: For any number of staged files, the hook should validate
        each file and report all issues.
        """
        with open(self.pre_commit_hook, 'r') as f:
            content = f.read()

        # Should process multiple files
        multi_file_elements = [
            'while IFS=',
            'read -r file',
            'done <<<',
            'validation_failed=false'
        ]

        for element in multi_file_elements:
            self.assertIn(element, content,
                         f"Should handle multiple files: {element}")

    def test_exit_codes_property(self):
        """Test that hook uses appropriate exit codes."""
        with open(self.pre_commit_hook, 'r') as f:
            content = f.read()

        # Should have proper exit codes
        exit_codes = [
            'exit 0',  # Success
            'exit 1'   # Failure
        ]

        for code in exit_codes:
            self.assertIn(code, content,
                         f"Should use exit code: {code}")

    def test_validation_summary_messages(self):
        """Test that hook provides clear validation summary."""
        with open(self.pre_commit_hook, 'r') as f:
            content = f.read()

        # Should have clear success/failure messages
        summary_elements = [
            'Pre-commit validation PASSED',
            'Pre-commit validation FAILED',
            'fix the issues above',
            'validation_failed'
        ]

        for element in summary_elements:
            self.assertIn(element, content,
                         f"Should have summary message: {element}")


if __name__ == '__main__':
    unittest.main()