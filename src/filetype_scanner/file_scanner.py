"""Directory Data File Scanner.

A highly configurable command-line utility designed to audit directories
and repositories for structured data files (.csv, .xlsx, etc.) and report
them in a clean, professional summary.

Usage:
    python data_scanner.py [TARGET_DIR] [--verbose] [--exclude EXCLUDE [EXCLUDE ...]]

Example:
    python data_scanner.py ./my_project --verbose --exclude .git node_modules
"""

import argparse
import logging
import os
import sys
from typing import List, Set

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# --- Default Scanning Constants ---
TARGET_EXTENSIONS: Set[str] = {
    ".csv",
    ".xlsx",
    ".xls",
    ".json",
    ".tsv",
}

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
        description="Scan a target directory recursively for data files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python data_scanner.py .\n"
            "  python data_scanner.py /path/to/data --verbose\n"
            "  python data_scanner.py . --exclude custom_dir build\n"
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


def scan_directory(directory_path: str, exclude_dirs: Set[str]) -> List[str]:
    """Recursively walks a directory and finds files matching target data extensions.

    Args:
        directory_path: The filesystem path to audit.
        exclude_dirs: A set of folder names to dynamically skip during traversal.

    Returns:
        List[str]: A list of relative or absolute file paths matching the target extensions.
    """
    if not os.path.isdir(directory_path):
        logger.error("Target path '%s' is not a valid directory.", directory_path)
        return []

    absolute_target = os.path.abspath(directory_path)
    logger.info("Initializing inventory scan on: %s", absolute_target)
    logger.info("Ignoring directories: %s", ", ".join(sorted(exclude_dirs)))
    logger.debug("Target extensions: %s", ", ".join(sorted(TARGET_EXTENSIONS)))

    found_files: List[str] = []

    for root, dirs, files in os.walk(directory_path, topdown=True):
        # Modifying dirs in-place with topdown=True prevents os.walk
        # from traversing into ignored directories entirely.
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            file_path = os.path.join(root, file)
            logger.debug("Checking file: %s", file_path)

            # Unpack the extension tuple properly before applying .lower()
            _, ext = os.path.splitext(file)
            if ext.lower() in TARGET_EXTENSIONS:
                logger.info("[MATCH] Found data file: %s", file_path)
                found_files.append(file_path)

    return found_files


def print_report(matched_files: List[str]) -> None:
    """Generates a clean, formatted stdout report of the discovery results.

    Args:
        matched_files: List of file paths found during the scan.
    """
    print("\n" + "=" * 60)
    print(f" {'DATA DISCOVERY REPORT':^58}")
    print("=" * 60)
    print(f" Total data files identified: {len(matched_files)}")
    print("-" * 60)

    if not matched_files:
        print(" No matching data files (.csv, .xlsx, etc.) were found.")
    else:
        for index, file_path in enumerate(matched_files, start=1):
            # Formatted list output for alignment and legibility
            print(f"  {index:>3}. {file_path}")

    print("=" * 60 + "\n")


def main() -> None:
    """Application entry point handling setup, parameters, and teardown."""
    args = parse_arguments()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Combine default excluded directories with user additions
    exclude_set = DEFAULT_IGNORED_DIRS.union(set(args.exclude))

    try:
        matched_files = scan_directory(args.target_dir, exclude_set)
        print_report(matched_files)
        sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n[!] Execution interrupted by user. Aborting scan safely.")
        sys.exit(130)


if __name__ == "__main__":
    main()