"""
Tests for smoke test script existence and structure.

Validates: Smoke test script is valid bash and has correct permissions.
"""
import os
import subprocess
import pytest


SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "scripts", "smoke_test.sh"
)


class TestSmokeScriptStructure:
    """Verify the smoke test script is well-formed."""

    def test_script_exists(self):
        """Smoke test script exists."""
        assert os.path.isfile(SCRIPT_PATH)

    def test_script_is_executable(self):
        """Script has execute permission."""
        assert os.access(SCRIPT_PATH, os.X_OK)

    def test_script_has_shebang(self):
        """Script starts with proper shebang."""
        with open(SCRIPT_PATH) as f:
            first_line = f.readline().strip()
        assert first_line.startswith("#!/")
        assert "bash" in first_line

    def test_script_syntax_valid(self):
        """Script passes bash -n syntax check."""
        result = subprocess.run(
            ["bash", "-n", SCRIPT_PATH],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_script_checks_healthz(self):
        """Script includes healthz endpoint check."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "/healthz" in content

    def test_script_checks_admin_pages(self):
        """Script includes admin page checks."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "/admin/" in content

    def test_script_accepts_base_url_arg(self):
        """Script accepts custom base URL as first argument."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "BASE_URL" in content
        assert "${1:-" in content  # Default value syntax

    def test_script_returns_nonzero_on_failure(self):
        """Script exits non-zero when failures detected."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "exit 1" in content

    def test_script_has_summary_output(self):
        """Script outputs a summary of results."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "passed" in content.lower()
        assert "failed" in content.lower()
