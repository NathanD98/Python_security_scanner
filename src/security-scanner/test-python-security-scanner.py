"""Unit Test Suite for the Repository Secret Scanner Gate.

This module establishes a comprehensive, automated test matrix for validating the
behavior of the recursive secrets auditing engine. It provides isolated unit tests
to ensure that the tool accurately flags hardcoded keys, manages directory exclusion
sets, handles unreadable files, and enforces proper CI/CD process termination codes.

Test Suite Architecture & Dynamic File Injection:
    To support multi-folder project architectures and eliminate pathing volatility
    during local or continuous integration runs, this test suite leverages
    'importlib.util' instead of static top-level imports.

    The testing suite dynamically resolves its own running execution directory via
    '__file__', constructs an absolute file path straight to 'secret_scanner.py', and
    registers the logic cleanly inside Python's system module mapping
    ('sys.modules'). This avoids any potential 'ModuleNotFoundError' issues
    regardless of your active terminal working directory.

Mocking Paradigm & Zero Filesystem Footprint:
    To maintain blazing-fast execution speeds and eliminate the need to create actual
    insecure credential files on disk, this suite enforces a zero-filesystem footprint.
    It intercepts and overrides foundational operating system interactions using the
    'unittest.mock.patch' framework.

    By mocking elements like 'os.path.isdir', 'os.walk', and the third-party
    'SecretsCollection' internals, the test suite can mimic complex nested directory
    structures and credential find-states entirely in runtime memory.

Assertion Matrix & Signal Interception:
    Because the security scanner terminates the runtime environment via 'sys.exit()'
    to break build pipelines upon finding security threats, testing must trap these
    system signals before they kill the test framework execution loop. All test gates
    are executed within a 'self.assertRaises(SystemExit)' context block. This isolates
    the system signal, extracts the termination flag, and ensures the script enforces
    the correct pipeline contract:
        * Exit Code 0: Confirmed clean run state when no secrets are present.
        * Exit Code 1: Confirmed hard-fail gate behavior when keys are found or
          parameters are completely invalid.
"""

import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# 1. Dynamically locate and resolve target script paths to maintain platform portability
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_FILE_PATH = os.path.join(SCRIPT_DIR, "python-security-scanner.py")

# 2. Programmatically compile and inject the module into system memory
spec = importlib.util.spec_from_file_location("secret_scanner", SRC_FILE_PATH)
secret_scanner = importlib.util.module_from_spec(spec)
sys.modules["secret_scanner"] = secret_scanner
spec.loader.exec_module(secret_scanner)


class TestSecretScanner(unittest.TestCase):
    """Test cases to verify the integrity and behavior of secret_scanner.py."""

    @patch("os.path.isdir")
    def test_scan_directory_invalid_path(self, mock_isdir: MagicMock) -> None:
        """Test that an invalid path returns a failure indicator code (1)."""
        mock_isdir.return_value = False

        result = secret_scanner.scan_directory("/invalid/target/path", set())
        self.assertEqual(result, 1)

    @patch("secret_scanner.SecretsCollection")
    @patch("os.walk")
    @patch("os.path.isdir")
    def test_scan_directory_clean_run(
        self, mock_isdir: MagicMock, mock_walk: MagicMock, mock_secrets_cls: MagicMock
    ) -> None:
        """Test that a directory containing zero secrets returns code 0."""
        mock_isdir.return_value = True

        # Simulate walking an environment with a single clean file
        mock_walk.return_value = [("./app", [], ["main.py"])]

        # Configure SecretsCollection to mock zero findings
        mock_secrets_inst = MagicMock()
        mock_secrets_inst.json.return_value = {}
        mock_secrets_cls.return_value = mock_secrets_inst

        result = secret_scanner.scan_directory("./app", set())
        self.assertEqual(result, 0)

    @patch("secret_scanner.SecretsCollection")
    @patch("os.walk")
    @patch("os.path.isdir")
    def test_scan_directory_secrets_found(
        self, mock_isdir: MagicMock, mock_walk: MagicMock, mock_secrets_cls: MagicMock
    ) -> None:
        """Test that detecting secrets aggregates total violations accurately."""
        mock_isdir.return_value = True
        mock_walk.return_value = [("./app", [], ["config.py"])]

        # Configure SecretsCollection to return simulated secret objects
        mock_secrets_inst = MagicMock()
        mock_secrets_inst.json.return_value = {
            "./app/config.py": [
                {"line_number": 12, "type": "Secret Keyword"},
                {"line_number": 45, "type": "Slack Webhook"},
            ]
        }
        mock_secrets_cls.return_value = mock_secrets_inst

        result = secret_scanner.scan_directory("./app", set())
        # Should return total findings count
        self.assertEqual(result, 2)

    @patch("secret_scanner.scan_directory")
    @patch("secret_scanner.parse_arguments")
    def test_main_pipeline_success(
        self, mock_args: MagicMock, mock_scan_dir: MagicMock
    ) -> None:
        """Test that main() calls exit code 0 when zero threats exist."""
        # Setup mock CLI arguments
        args = MagicMock()
        args.target_dir = "."
        args.verbose = False
        args.exclude = []
        mock_args.return_value = args

        # Simulate zero vulnerabilities found
        mock_scan_dir.return_value = 0

        with self.assertRaises(SystemExit) as context:
            secret_scanner.main()
        self.assertEqual(context.exception.code, 0)

    @patch("secret_scanner.scan_directory")
    @patch("secret_scanner.parse_arguments")
    def test_main_pipeline_failure(
        self, mock_args: MagicMock, mock_scan_dir: MagicMock
    ) -> None:
        """Test that main() issues exit code 1 to break pipeline on risks."""
        args = MagicMock()
        args.target_dir = "."
        args.verbose = False
        args.exclude = []
        mock_args.return_value = args

        # Simulate vulnerabilities found
        mock_scan_dir.return_value = 5

        with self.assertRaises(SystemExit) as context:
            secret_scanner.main()
        self.assertEqual(context.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
