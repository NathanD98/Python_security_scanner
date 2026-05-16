"""Unit Test Suite for the SAST Syntax Security Gate.

This module establishes a deterministic, automated test matrix for validating the
behavior of the static application security testing (SAST) control logic. It provides
isolated regression testing to verify that the security gate responds accurately to
varying structural code profiles, dependency configurations, and environment states.

Test Suite Architecture & Dynamic Dependency Resolution:
    Because security scanners frequently utilize custom filenames or reside inside deep
    nested project subdirectories, standard static python import hooks (e.g., 'import
    bandit_scan') will routinely fail with 'ModuleNotFoundError' when executed from a
    project's root directory.

    To ensure platform-agnostic portability, this test harness implements a two-stage
    dynamic bootstrap routine:
        1. Explicit Location Discovery: Computes absolute paths at runtime relative to
           the executing test file using '__file__'.
        2. Programmatic Module Ingestion: Leverages low-level 'importlib.util' engines
           to dynamically map, compile, and inject the source logic straight into the
           active global module dictionary ('sys.modules'). This effectively neutralizes
           directory path conflicts and bypasses Python naming constraints on filenames.

Mocking Paradigms & Process Isolation:
    To preserve execution speed and guarantee repeatability, the suite enforces a
    strict zero-external-dependency requirement. By using the '@patch' decorator,
    low-level system infrastructure calls like 'subprocess.run' are intercepted and
    swapped out for a 'MagicMock' instance. This allows the test suite to simulate raw
    system return codes, standard output streams (stdout), and error outputs (stderr)
    instantaneously without spawning physical subprocesses or modifying real code.

Assertion Matrix & Signal Interception:
    Since the target scanner utility terminates execution flow using 'sys.exit()',
    invoking it inside a generic test runner would immediately kill the entire test
    thread. To circumvent this, assertions are encapsulated within a
    'self.assertRaises(SystemExit)' context manager. This traps the execution
    termination signal, extracts the underlying integer exit status code, and validates
    it against the expected DevSecOps pipeline outcomes:
        * Exit Code 0: Verified clean pass when the source code contains zero code smells.
        * Exit Code 1: Verified hard-fail gate behavior when vulnerabilities or syntax
          errors are intercepted.
"""

import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_FILE_PATH = os.path.join(SCRIPT_DIR, "banditscan.py")

spec = importlib.util.spec_from_file_location("bandit_scan", SRC_FILE_PATH)
bandit_scan = importlib.util.module_from_spec(spec)
sys.modules["bandit_scan"] = bandit_scan
spec.loader.exec_module(bandit_scan)


class TestBanditScan(unittest.TestCase):
    """Test cases for verifying the behavior of run_sast_scan."""

    @patch("subprocess.run")
    def test_sast_scan_success(self, mock_run: MagicMock) -> None:
        """Test that exit code 0 is sent when code architecture is secure."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "No issues identified."
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        with self.assertRaises(SystemExit) as context:
            bandit_scan.run_sast_scan()
        self.assertEqual(context.exception.code, 0)

    @patch("subprocess.run")
    def test_sast_scan_flaws_found(self, mock_run: MagicMock) -> None:
        """Test that exit code 1 is triggered when code smells are caught."""
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = "Issue: [B102:exec_used] Use of exec detected."
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        with self.assertRaises(SystemExit) as context:
            bandit_scan.run_sast_scan()
        self.assertEqual(context.exception.code, 1)

    @patch("subprocess.run")
    def test_sast_scan_missing_module(self, mock_run: MagicMock) -> None:
        """Test that exit code 1 is triggered if bandit isn't installed."""
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = ""
        mock_process.stderr = "No module named bandit"
        mock_run.return_value = mock_process

        with self.assertRaises(SystemExit) as context:
            bandit_scan.run_sast_scan()
        self.assertEqual(context.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
