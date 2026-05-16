"""Directory Secret Scanner.

A highly configurable command-line utility designed to audit repositories
and local directories for leaked credentials, API keys, and hardcoded passwords
using the 'detect_secrets' core analysis plugins.

Usage:
    python secret_scanner.py [TARGET_DIR] [--verbose] [--exclude EXCLUDE [EXCLUDE ...]]

Example:
    python secret_scanner.py ./my_project --verbose --exclude .git node_modules
"""

import argparse
import logging
import os
import sys
from typing import List, Optional, Set

from detect_secrets import SecretsCollection
from detect_secrets.settings import default_settings

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# --- Default Exclude Sets ---
DEFAULT_IGNORED_DIRS: Set[str] = {
    ".git",
    ".github",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".idea",
    ".vscode",
}


def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments.

    Returns:
        argparse.Namespace: Object containing validated command-line options.
    """
    parser = argparse.ArgumentParser(
        description="Scan a target directory recursively for hardcoded secrets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python secret_scanner.py .\n"
            "  python secret_scanner.py /path/to/code --verbose\n"
            "  python secret_scanner.py . --exclude custom_dir build\n"
        ),
    )

    parser.add_argument(
        "target_dir",
        nargs="?",
        default=".",
        help="The directory path to scan. Defaults to the current directory ('.').",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging output for detailed file processing.",
    )

    parser.add_argument(
        "-e",
        "--exclude",
        nargs="+",
        default=[],
        help="Additional directory names to ignore during the scan.",
    )

    return parser.parse_args()


def scan_directory(directory_path: str, exclude_dirs: Set[str]) -> int:
    """Recursively walks a directory and scans human-readable files for secrets.

    Args:
        directory_path: The filesystem path to audit.
        exclude_dirs: A set of folder names to dynamically skip during traversal.

    Returns:
        int: Total number of secret findings discovered (0 means clean scan).
    """
    if not os.path.isdir(directory_path):
        logger.error("Target path '%s' is not a valid directory.", directory_path)
        return 1

    absolute_target = os.path.abspath(directory_path)
    logger.info("Initializing audit scan on: %s", absolute_target)
    logger.info("Ignoring directories: %s", ", ".join(sorted(exclude_dirs)))

    secrets = SecretsCollection()
    total_findings = 0

    with default_settings():
        for root, dirs, files in os.walk(directory_path, topdown=True):
            # Modifying dirs in-place with topdown=True prevents os.walk
            # from traversing into ignored directories entirely.
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                file_path = os.path.join(root, file)
                logger.debug("Auditing file: %s", file_path)

                try:
                    secrets.scan_file(file_path)
                except (PermissionError, UnicodeDecodeError):
                    logger.debug("Skipped unreadable file: %s", file_path)
                    continue
                except Exception as err:
                    logger.warning("Error processing %s: %s", file_path, err)
                    continue

    findings = secrets.json()

    if not findings:
        print("\n" + "=" * 60)
        print(" SUCCESS: No credentials or hardcoded secrets were found.")
        print("=" * 60)
        return 0

    print("SECURITY ALERT: Potential Secret Exposures Detected")

    for file_path, secret_list in findings.items():
        print(f"\n File: {file_path}")
        print(f"   {'Line':<8} | {'Detector/Plugin Engine':<30}")
        print("   " + "-" * 45)
        
        for secret in secret_list:
            total_findings += 1
            line_num = secret.get("line_number", "Unknown")
            plugin_type = secret.get("type", "Unknown Detector")
            print(f"   {f'L{line_num}':<8} | {plugin_type:<30}")
            
    print("\n" + "=" * 60)
    print(f"Audit concluded with {total_findings} vulnerabilities identified.")
    print("=" * 60)

    return total_findings


def main() -> None:
    """Application entry point handling setup, parameters, and teardown."""
    args = parse_arguments()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Combine default excluded directories with user additions
    exclude_set = DEFAULT_IGNORED_DIRS.union(set(args.exclude))

    try:
        secret_count = scan_directory(args.target_dir, exclude_set)
        # Exit with status code 1 if secrets are found (ideal for CI/CD pipelines)
        sys.exit(1 if secret_count > 0 else 0)

    except KeyboardInterrupt:
        print("\n\n[!] Execution interrupted by user. Aborting scan safely.")
        sys.exit(130)


if __name__ == "__main__":
    main()
