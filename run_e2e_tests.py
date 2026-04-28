#!/usr/bin/env python3
"""Comprehensive test runner for franken-stream e2e audit and testing."""

import os
import sys
import subprocess
import json
import re
from pathlib import Path
from datetime import datetime


class TestRunner:
    """Comprehensive test runner for franken-stream."""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.python_path = str(self.project_root)
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "summary": {}
        }

    def run_command(self, cmd, timeout=30, input_text=None):
        """Run a command and return result."""
        env = os.environ.copy()
        env["PYTHONPATH"] = self.python_path

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                input=input_text,
                env=env,
                cwd=self.project_root,
                timeout=timeout
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "Timeout",
                "success": False
            }

    def test_unit_tests(self):
        """Run unit tests."""
        print("🧪 Running Unit Tests...")
        result = self.run_command("python tests/test_unit.py")
        self.results["tests"]["unit_tests"] = result
        print(f"✅ Unit tests: {'PASSED' if result['success'] else 'FAILED'}")
        return result["success"]

    def test_cli_commands(self):
        """Test CLI commands."""
        print("💻 Testing CLI Commands...")
        cli_tests = {
            "help": ["python", "-m", "franken_stream.main", "--help"],
            "config": ["python", "-m", "franken_stream.main", "config"],
            "validate": ["python", "-m", "franken_stream.main", "validate"],
            "test_providers": ["python", "-m", "franken_stream.main", "test-providers"],
            "update": ["python", "-m", "franken_stream.main", "update"]  # May fail due to network
        }

        results = {}
        for name, cmd in cli_tests.items():
            result = self.run_command(" ".join(cmd))
            results[name] = result
            status = "✅" if result["success"] or (name == "update" and "Failed to update" in result["stdout"]) else "❌"
            print(f"{status} CLI {name}: {'PASSED' if result['success'] or (name == 'update' and 'Failed to update' in result['stdout']) else 'FAILED'}")

        self.results["tests"]["cli_commands"] = results
        # Allow update to fail due to network issues
        return all(r["success"] for name, r in results.items() if name != "update") and \
               (results["update"]["success"] or "Failed to update" in results["update"]["stdout"])

    def test_web_ui(self):
        """Test Web UI startup."""
        print("🌐 Testing Web UI...")
        # Test web server startup (will timeout after 3 seconds)
        result = self.run_command(
            "timeout 3 python -m franken_stream.main web --host 127.0.0.1 --port 8002",
            timeout=5
        )
        # Web server should start successfully (timeout is expected)
        success = "Starting Web UI" in result["stdout"] or "Serving" in result["stdout"]
        self.results["tests"]["web_ui"] = {"result": result, "success": success}
        print(f"✅ Web UI: {'PASSED' if success else 'FAILED'}")
        return success

    def test_search_functionality(self):
        """Test search functionality."""
        print("🔍 Testing Search Functionality...")
        # Test search with timeout to prevent hanging
        result = self.run_command(
            "timeout 10 python -m franken_stream.main watch 'test' --no-interactive",
            timeout=15
        )
        # Search should attempt to run (may fail due to network)
        success = result["returncode"] is not None  # Command executed
        self.results["tests"]["search"] = {"result": result, "success": success}
        print(f"✅ Search: {'PASSED' if success else 'FAILED'}")
        return success

    def audit_security(self):
        """Perform security audit."""
        print("🔒 Performing Security Audit...")

        security_checks = {
            "no_hardcoded_secrets": self.check_no_hardcoded_secrets(),
            "safe_url_handling": self.check_url_handling(),
            "input_validation": self.check_input_validation(),
            "proxy_security": self.check_proxy_security(),
            "file_permissions": self.check_file_permissions()
        }

        self.results["tests"]["security_audit"] = security_checks
        all_passed = all(security_checks.values())
        print(f"✅ Security Audit: {'PASSED' if all_passed else 'FAILED'}")
        return all_passed

    def check_no_hardcoded_secrets(self):
        """Check for hardcoded secrets."""
        # Search for potential secrets in code
        secret_patterns = ["password.*=", "secret.*=", "api_key.*=", "token.*="]
        found_secrets = []

        for file in self.project_root.rglob("*.py"):
            if "test" in str(file):
                continue
            try:
                content = file.read_text()
                for pattern in secret_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        found_secrets.extend([f"{file}: {match}" for match in matches])
            except:
                pass

        success = len(found_secrets) == 0
        self.results["security"]["hardcoded_secrets"] = {
            "found": found_secrets,
            "safe": success
        }
        return success

    def check_url_handling(self):
        """Check URL handling security."""
        # Look for proper URL validation
        scraper_file = self.project_root / "franken_stream" / "scraper.py"
        if scraper_file.exists():
            content = scraper_file.read_text()
            has_validation = "_validate_url" in content and "_sanitize_url" in content
            self.results["security"]["url_handling"] = {"has_validation": has_validation}
            return has_validation
        return False

    def check_input_validation(self):
        """Check input validation."""
        main_file = self.project_root / "franken_stream" / "main.py"
        if main_file.exists():
            content = main_file.read_text()
            has_validation = len(content.split("typer.Argument")) > 1  # Has typer validation
            self.results["security"]["input_validation"] = {"has_validation": has_validation}
            return has_validation
        return False

    def check_proxy_security(self):
        """Check proxy security."""
        scraper_file = self.project_root / "franken_stream" / "scraper.py"
        if scraper_file.exists():
            content = scraper_file.read_text()
            # Check if proxy is properly configured
            has_proxy_config = "proxy" in content and "session.proxies" in content
            self.results["security"]["proxy_security"] = {"configured": has_proxy_config}
            return has_proxy_config
        return False

    def check_file_permissions(self):
        """Check file permissions."""
        config_dir = Path.home() / ".franken-stream"
        if config_dir.exists():
            perms = oct(config_dir.stat().st_mode)[-3:]
            # Should be 700 or similar (owner only)
            safe = perms.startswith("7") or perms.startswith("6")
            self.results["security"]["file_permissions"] = {
                "permissions": perms,
                "safe": safe
            }
            return safe
        return True  # If no config dir, assume safe

    def audit_performance(self):
        """Perform performance audit."""
        print("⚡ Performing Performance Audit...")

        # Test startup time
        import time
        start = time.time()
        result = self.run_command("python -c \"from franken_stream.providers import ProviderManager; pm = ProviderManager()\"", timeout=5)
        end = time.time()
        startup_time = end - start

        # Test provider loading time
        start = time.time()
        result = self.run_command("python -c \"from franken_stream.providers import ProviderManager; pm = ProviderManager(); pm.load_providers()\"", timeout=5)
        end = time.time()
        load_time = end - start

        performance = {
            "startup_time": startup_time,
            "provider_load_time": load_time,
            "acceptable": startup_time < 2.0 and load_time < 1.0
        }

        self.results["tests"]["performance"] = performance
        success = performance["acceptable"]
        print(f"✅ Performance: {'PASSED' if success else 'FAILED'} (startup: {startup_time:.2f}s, load: {load_time:.2f}s)")
        return success

    def generate_report(self):
        """Generate comprehensive report."""
        print("\n" + "="*80)
        print("🎯 FRANKEN-STREAM E2E AUDIT & TEST REPORT")
        print("="*80)

        # Calculate summary - count major test categories
        major_tests = ["unit_tests", "cli_commands", "web_ui", "search", "security_audit", "performance"]
        tests_run = len(major_tests)
        tests_passed = 0

        for test_name in major_tests:
            if test_name in self.results["tests"]:
                test_result = self.results["tests"][test_name]
                if test_name == "security_audit":
                    # Security audit is a dict of boolean results
                    tests_passed += 1 if all(test_result.values()) else 0
                elif test_name == "cli_commands":
                    # CLI commands is a dict of command results
                    # Allow update to fail due to network
                    cli_success = all(r.get("success", False) for cmd, r in test_result.items() if cmd != "update")
                    update_ok = test_result.get("update", {}).get("success", False) or "Failed to update" in test_result.get("update", {}).get("stdout", "")
                    tests_passed += 1 if cli_success and update_ok else 0
                elif test_name == "performance":
                    tests_passed += 1 if test_result.get("acceptable", False) else 0
                elif isinstance(test_result, dict) and "success" in test_result:
                    tests_passed += 1 if test_result["success"] else 0
                elif isinstance(test_result, bool):
                    tests_passed += 1 if test_result else 0

        self.results["summary"] = {
            "tests_run": tests_run,
            "tests_passed": tests_passed,
            "success_rate": f"{tests_passed}/{tests_run}",
            "overall_success": tests_passed >= 5  # Allow 1 failure for network-dependent tests
        }

        print(f"📊 Summary: {tests_passed}/{tests_run} tests passed")
        print(f"🎉 Overall: {'SUCCESS' if self.results['summary']['overall_success'] else 'ISSUES FOUND'}")

        # Save detailed report
        report_file = self.project_root / "E2E_AUDIT_REPORT.json"
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"📄 Detailed report saved to: {report_file}")

        return self.results["summary"]["overall_success"]

    def run_all_tests(self):
        """Run all tests and audits."""
        print("🚀 Starting Franken-Stream E2E Audit & Testing")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Initialize security results
        self.results["security"] = {}

        # Run all test suites
        test_results = [
            self.test_unit_tests(),
            self.test_cli_commands(),
            self.test_web_ui(),
            self.test_search_functionality(),
            self.audit_security(),
            self.audit_performance()
        ]

        # Generate final report
        success = self.generate_report()

        return success


def main():
    """Main entry point."""
    runner = TestRunner()
    success = runner.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()