"""Unit Test Suite for the Dependency Security Gate Utility.

This module establishes a deterministic, automated test matrix for validating the 
behavior of the software supply chain dependency auditing logic. It provides 
isolated unit tests to guarantee that the security gate responds accurately to 
varying package risk profiles, uninstalled system binaries, and environmental flags.

Test Suite Architecture & Dynamic Dependency Ingestion:
    To support diverse repository layout configurations and completely eliminate 
    pathing errors ('ModuleNotFoundError') during execution from the project root 
    or inside automation containers, this suite bypasses static top-level imports. 
    
    It calculates absolute paths dynamically at runtime relative to the test file via 
    '__file__', constructs a precise pointer to 'pip_auditer.py', and programmatically 
    registers the module inside Python's core tracking network ('sys.modules'). This 
    guarantees seamless, platform-agnostic testing capability.

Mocking Paradigm & Zero-Dependency Execution:
    To maintain rapid test execution and remove dependencies on real network interfaces 
    or external package advisory databases, this suite implements strict subprocess 
    isolation. By applying the '@patch' decorator, it intercepts low-level operating 
    system execution hooks ('subprocess.run') and swaps them out for a customizable 
    'MagicMock' instance. 
    
    This allows the developer to fake the standard output (stdout), standard error 
    (stderr), and return code response payloads instantaneously, simulating real-world 
    vulnerability scenarios entirely within local runtime memory.

Assertion Matrix & Signal Interception:
    Because the security tool terminates execution threads using 'sys.exit()' to force 
    failures inside CI/CD environments when security risks are discovered, testing 
    must cleanly isolate these termination requests before they kill the test runner. 
    
    Test executions are wrapped inside a 'self.assertRaises(SystemExit)' context 
    manager. This traps the termination signal, intercepts the underlying integer exit 
    status code, and validates it against expected DevSecOps pipeline outcomes:
        * Exit Code 0: Confirmed clean pass condition when all project packages are safe.
        * Exit Code 1: Confirmed pipeline freeze condition when vulnerabilities or missing 
          dependencies are encountered.
"""

import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# 1. Dynamically locate and resolve target script paths to maintain platform portability
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_FILE_PATH = os.path.join(SCRIPT_DIR, "pip-auditer.py")

# 2. Programmatically compile and inject the module into system memory
spec = importlib.util.spec_from_file_location("pip_auditer", SRC_FILE_PATH)
pip_auditer = importlib.util.module_from_spec(spec)
sys.modules["pip_auditer"] = pip_auditer
spec.loader.exec_module(pip_auditer)


class TestPipAuditer(unittest.TestCase):
    """Test cases to verify the integrity and behavior of pip_auditer.py."""

    @patch("subprocess.run")
    def test_check_dependencies_success(self, mock_run: MagicMock) -> None:
        """Test that exit code 0 is sent when dependencies are secure."""
        # Configure the subprocess mock to mimic a completely clean scan status
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "[]"
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        # Assert that a clean run successfully yields exit status code 0
        with self.assertRaises(SystemExit) as context:
            pip_auditer.check_dependencies()
        self.assertEqual(context.exception.code, 0)

    @patch("subprocess.run")
    def test_check_dependencies_vulnerability_found(self, mock_run: MagicMock) -> None:
        """Test that exit code 1 is triggered when vulnerabilities are caught."""
        # Configure the mock to mimic a dirty audit run (returncode != 0)
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = '{"mock_vulnerability": "CVE-2026-12345"}'
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        # Assert that finding a vulnerability triggers a hard failure (exit 1)
        with self.assertRaises(SystemExit) as context:
            pip_auditer.check_dependencies()
        self.assertEqual(context.exception.code, 1)

    @patch("subprocess.run")
    def test_check_dependencies_missing_package(self, mock_run: MagicMock) -> None:
        """Test that exit code 1 is triggered if pip-audit isn't installed."""
        # Configure the mock to mimic system environment binary lookup failures
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = ""
        mock_process.stderr = "is not recognized as an internal or external command"
        mock_run.return_value = mock_process

        # Assert that a missing environment module safely stops execution with code 1
        with self.assertRaises(SystemExit) as context:
            pip_auditer.check_dependencies()
        self.assertEqual(context.exception.code, 1)


if __name__ == "__main__":
    unittest.main()