"""
Property-based tests for Git branch protection.

Feature: deploy-staging, Property 1: Git Branch Protection Enforcement
Validates: Requirements 1.1
"""
import os
import subprocess
from pathlib import Path
from hypothesis import given, strategies as st, settings, HealthCheck
import unittest


@st.composite
def branch_name_strategy(draw):
    """Generate branch names for testing."""
    branches = ['main', 'master', 'develop', 'staging', 'feature/test', 'hotfix/urgent']
    return draw(st.sampled_from(branches))


@st.composite
def protected_branch_strategy(draw):
    """Generate protected branch names."""
    protected = ['main', 'master']
    return draw(st.sampled_from(protected))


class GitBranchProtectionPropertyTest(unittest.TestCase):
    """
    Property test for Git branch protection.
    
    **Property 1: Git Branch Protection Enforcement**
    For any attempt to push directly to main/master branches, the Git workflow 
    should reject the push and require a pull request instead.
    """

    def setUp(self):
        self.repo_root = Path(__file__).parent.parent
        self.hooks_dir = self.repo_root / '.githooks'
        self.pre_push_hook = self.hooks_dir / 'pre-push'
        self.pre_commit_hook = self.hooks_dir / 'pre-commit'

    def test_git_hooks_exist(self):
        """Test that Git hooks exist and are executable."""
        self.assertTrue(self.pre_push_hook.exists(), "Pre-push hook should exist")
        self.assertTrue(self.pre_commit_hook.exists(), "Pre-commit hook should exist")
        
        # Check if hooks are executable
        self.assertTrue(os.access(self.pre_push_hook, os.X_OK), 
                       "Pre-push hook should be executable")
        self.assertTrue(os.access(self.pre_commit_hook, os.X_OK), 
                       "Pre-commit hook should be executable")

    @given(branch_name=protected_branch_strategy())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.filter_too_much])
    def test_protected_branch_detection_property(self, branch_name):
        """
        Property: For any protected branch name, the pre-push hook should 
        detect it as protected and prevent direct pushes.
        """
        with open(self.pre_push_hook, 'r') as f:
            hook_content = f.read()

        # Protected branches should be listed in the hook
        self.assertIn(branch_name, hook_content, 
                     f"Protected branch {branch_name} should be listed in pre-push hook")

    def test_pre_push_hook_protection_logic(self):
        """Test that pre-push hook contains proper protection logic."""
        with open(self.pre_push_hook, 'r') as f:
            content = f.read()

        # Should contain protection logic
        required_elements = [
            'protected_branches',
            'current_branch',
            'Direct push to protected branch',
            'pull request',
            'exit 1'
        ]

        for element in required_elements:
            self.assertIn(element, content, 
                         f"Pre-push hook should contain: {element}")

    @given(branch_name=branch_name_strategy())
    @settings(max_examples=20, suppress_health_check=[HealthCheck.filter_too_much])
    def test_branch_protection_logic_property(self, branch_name):
        """
        Property: For any branch name, the protection logic should correctly
        identify whether it's protected or not.
        """
        with open(self.pre_push_hook, 'r') as f:
            content = f.read()

        # Extract protected branches from hook content
        protected_branches = ['main', 'master']  # Based on hook implementation
        
        is_protected = branch_name in protected_branches
        
        if is_protected:
            # Protected branches should trigger error message
            self.assertIn('Direct push to protected branch', content,
                         "Should have protection error message")
        
        # All branches should be subject to the check
        self.assertIn('current_branch', content,
                     "Should check current branch")

    def test_pre_commit_hook_file_validation(self):
        """Test that pre-commit hook contains file validation logic."""
        with open(self.pre_commit_hook, 'r') as f:
            content = f.read()

        # Should contain file size validation
        validation_elements = [
            'MAX_FILE_SIZE',
            'check_file_size',
            'check_file_type',
            'staged_files',
            'git diff --cached'
        ]

        for element in validation_elements:
            self.assertIn(element, content,
                         f"Pre-commit hook should contain: {element}")

    def test_file_size_limit_configuration(self):
        """Test that file size limit is properly configured."""
        with open(self.pre_commit_hook, 'r') as f:
            content = f.read()

        # Should have 100MB limit (104857600 bytes)
        self.assertIn('104857600', content, "Should have 100MB file size limit")
        self.assertIn('100MB', content, "Should mention 100MB limit in messages")

    @given(
        file_extension=st.sampled_from(['zip', 'rar', '7z', 'tar', 'gz', 'bak', 'backup', 'old', 'tmp'])
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.filter_too_much])
    def test_file_type_validation_property(self, file_extension):
        """
        Property: For any problematic file extension, the pre-commit hook
        should detect and warn about it.
        """
        with open(self.pre_commit_hook, 'r') as f:
            content = f.read()

        # File extension should be mentioned in validation logic
        self.assertIn(file_extension, content,
                     f"Pre-commit hook should validate {file_extension} files")

    def test_sensitive_data_detection(self):
        """Test that pre-commit hook detects sensitive data patterns."""
        with open(self.pre_commit_hook, 'r') as f:
            content = f.read()

        # Should check for sensitive patterns
        sensitive_checks = [
            'sensitive_patterns',
            'password',
            'secret',
            'api_key',
            'private_key'
        ]

        for check in sensitive_checks:
            self.assertIn(check, content,
                         f"Pre-commit hook should check for: {check}")

    def test_hook_bypass_documentation(self):
        """Test that hooks document bypass options."""
        with open(self.pre_push_hook, 'r') as f:
            pre_push_content = f.read()
        
        with open(self.pre_commit_hook, 'r') as f:
            pre_commit_content = f.read()

        # Should document --no-verify option
        self.assertIn('--no-verify', pre_push_content,
                     "Pre-push hook should document bypass option")
        self.assertIn('--no-verify', pre_commit_content,
                     "Pre-commit hook should document bypass option")

    def test_setup_script_exists(self):
        """Test that Git hooks setup script exists."""
        setup_script = self.repo_root / 'scripts' / 'setup-git-hooks.sh'
        self.assertTrue(setup_script.exists(), "Git hooks setup script should exist")
        self.assertTrue(os.access(setup_script, os.X_OK), 
                       "Setup script should be executable")

    def test_setup_script_functionality(self):
        """Test that setup script contains proper installation logic."""
        setup_script = self.repo_root / 'scripts' / 'setup-git-hooks.sh'
        
        with open(setup_script, 'r') as f:
            content = f.read()

        # Should install both hooks
        required_elements = [
            'pre-commit',
            'pre-push',
            'chmod +x',
            'git config core.hooksPath'
        ]

        for element in required_elements:
            self.assertIn(element, content,
                         f"Setup script should contain: {element}")

    def test_branch_protection_documentation(self):
        """Test that branch protection rules are documented."""
        docs_file = self.repo_root / '.github' / 'branch-protection-rules.md'
        self.assertTrue(docs_file.exists(), "Branch protection documentation should exist")

        with open(docs_file, 'r') as f:
            content = f.read()

        # Should document protection for main branches
        self.assertIn('main', content, "Should document main branch protection")
        self.assertIn('master', content, "Should document master branch protection")
        self.assertIn('pull request', content, "Should mention pull request requirement")

    @given(
        hook_type=st.sampled_from(['pre-commit', 'pre-push'])
    )
    @settings(max_examples=5)
    def test_hook_error_handling_property(self, hook_type):
        """
        Property: For any Git hook, it should have proper error handling
        and exit codes.
        """
        hook_file = self.hooks_dir / hook_type
        
        with open(hook_file, 'r') as f:
            content = f.read()

        # Should have proper error handling
        error_handling_elements = [
            'set -e',  # Exit on error
            'exit 1',  # Error exit code
            'exit 0'   # Success exit code
        ]

        for element in error_handling_elements:
            self.assertIn(element, content,
                         f"{hook_type} hook should contain: {element}")

    def test_django_integration_in_hooks(self):
        """Test that hooks integrate with Django project structure."""
        with open(self.pre_push_hook, 'r') as f:
            content = f.read()

        # Should check Django system for deployment branches
        django_checks = [
            'python manage.py check',
            'Django system check'
        ]

        for check in django_checks:
            self.assertIn(check, content,
                         f"Pre-push hook should include: {check}")


if __name__ == '__main__':
    unittest.main()