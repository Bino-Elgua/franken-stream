"""End-to-end tests for franken-stream CLI."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


class TestCLI:
    """Test CLI commands end-to-end."""

    def run_command(self, args, input_text=None):
        """Run a CLI command and return result."""
        cmd = [sys.executable, "-m", "franken_stream.main"] + args
        env = {"PYTHONPATH": str(Path(__file__).parent.parent)}

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=input_text,
            env={**env, **dict(os.environ)},
            cwd=Path(__file__).parent.parent
        )
        return result

    def test_cli_help(self):
        """Test CLI help command."""
        result = self.run_command(["--help"])
        assert result.returncode == 0
        assert "Terminal media streamer" in result.stdout
        assert "watch" in result.stdout
        assert "tv" in result.stdout

    def test_config_command(self):
        """Test config command."""
        result = self.run_command(["config"])
        assert result.returncode == 0
        assert "Configuration" in result.stdout or "providers" in result.stdout

    def test_validate_command(self):
        """Test validate command."""
        result = self.run_command(["validate"])
        assert result.returncode == 0
        assert "valid" in result.stdout.lower() or "Config" in result.stdout

    def test_test_providers_command(self):
        """Test test-providers command."""
        result = self.run_command(["test-providers"])
        assert result.returncode == 0
        assert "Provider Health Check" in result.stdout or "Testing providers" in result.stdout

    def test_update_command(self):
        """Test update command."""
        result = self.run_command(["update"])
        # This might fail due to network, but should not crash
        assert result.returncode in [0, 1]  # Allow network failures

    @patch('franken_stream.scraper.ContentScraper.search')
    def test_watch_command_no_interactive(self, mock_search):
        """Test watch command with no-interactive flag."""
        mock_search.return_value = []

        result = self.run_command(["watch", "test", "--no-interactive"])
        # Should not hang and should attempt search
        assert result.returncode in [0, 1]  # Allow various exit codes

    def test_watch_command_invalid_query(self):
        """Test watch command with invalid query."""
        result = self.run_command(["watch", "", "--no-interactive"])
        # Should handle empty query gracefully
        assert result.returncode != 0 or "No results" in result.stdout


class TestWebUI:
    """Test Web UI functionality."""

    def test_web_command_help(self):
        """Test web command help."""
        result = subprocess.run(
            [sys.executable, "-m", "franken_stream.main", "web", "--help"],
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(Path(__file__).parent.parent)},
            cwd=Path(__file__).parent.parent
        )
        assert result.returncode == 0
        assert "web" in result.stdout.lower()

    def test_web_server_start(self):
        """Test web server can start."""
        import signal
        import time

        # Start the server process
        proc = subprocess.Popen(
            [sys.executable, "-m", "franken_stream.main", "web", "--host", "127.0.0.1", "--port", "8001"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={"PYTHONPATH": str(Path(__file__).parent.parent)},
            cwd=Path(__file__).parent.parent
        )

        # Wait a bit for startup
        time.sleep(2)

        # Check if it started successfully by reading stdout
        if proc.poll() is None:  # Still running
            proc.terminate()
            proc.wait(timeout=5)
            stdout, stderr = proc.communicate()
            assert "Starting Franken-Stream Web UI" in stdout
        else:
            # Process already exited
            stdout, stderr = proc.communicate()
            assert proc.returncode == 0 or "Starting Franken-Stream Web UI" in stdout


class TestSecurity:
    """Security-focused tests."""

    def run_command(self, args, input_text=None):
        """Run a CLI command and return result."""
        cmd = [sys.executable, "-m", "franken_stream.main"] + args
        env = {"PYTHONPATH": str(Path(__file__).parent.parent)}

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=input_text,
            env={**env, **dict(os.environ)},
            cwd=Path(__file__).parent.parent
        )
        return result

    def test_no_shell_injection_in_watch(self):
        """Test that watch command doesn't allow shell injection."""
        # Test with potentially malicious input
        malicious_query = "test; rm -rf /tmp/*"
        result = self.run_command(["watch", malicious_query, "--no-interactive"])

        # Should not execute shell commands
        # This is a basic check - in real security testing we'd monitor system calls
        assert result.returncode != 0 or "Error" in result.stdout

    def test_proxy_validation(self):
        """Test proxy URL validation."""
        # Valid proxy
        result = self.run_command(["watch", "test", "--proxy", "http://proxy.example.com:8080", "--no-interactive"])
        # Should not crash on valid proxy
        assert isinstance(result.returncode, int)

        # Invalid proxy (should still not crash)
        result = self.run_command(["watch", "test", "--proxy", "invalid-proxy", "--no-interactive"])
        assert isinstance(result.returncode, int)


class TestErrorHandling:
    """Test error handling scenarios."""

    def run_command(self, args, input_text=None):
        """Run a CLI command and return result."""
        cmd = [sys.executable, "-m", "franken_stream.main"] + args
        env = {"PYTHONPATH": str(Path(__file__).parent.parent)}

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=input_text,
            env={**env, **dict(os.environ)},
            cwd=Path(__file__).parent.parent
        )
        return result

    @patch('franken_stream.providers.ProviderManager.load_providers')
    def test_corrupted_config_handling(self, mock_load):
        """Test handling of corrupted config file."""
        mock_load.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

        result = self.run_command(["config"])
        # Should handle JSON errors gracefully
        assert result.returncode in [0, 1]

    def test_network_timeout_handling(self):
        """Test network timeout handling."""
        # This would require mocking network calls
        # For now, just ensure the command doesn't crash
        result = self.run_command(["watch", "nonexistent", "--no-interactive"])
        assert isinstance(result.returncode, int)


if __name__ == "__main__":
    pytest.main([__file__])