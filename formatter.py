"""Automated Source Code Formatting Engine.

This module provides a standalone, production-ready utility to automatically format
Python source code according to strict PEP 8 standards. It serves as a static
hygiene gate within local development environments or pre-commit pipeline workflows,
wrapping the industry-standard 'Black' opinionated code formatter.

Operational Theory & Code Hygiene:
    Code formatting engines normalize structural design choices (such as trailing
    commas, quote styles, and line wraps) without changing the logical behavior of
    the application. This ensures uniform code readability across large engineering
    teams and prevents superficial formatting diffs from polluting Git history.

Cross-Platform Execution & Subprocess Path Resolution:
    When automating command-line interface tools across variable OS landscapes
    (particularly Microsoft Store installations of Python on Windows), executing a
    global binary entry point (like 'black .') frequently misfires with standard
    'FileNotFoundError' or path isolation blocks.

    This runner relies exclusively on system interpreter query mechanics
    ('sys.executable') to invoke Black as a native internal module via the execution
    array `[sys.executable, "-m", "black", "."]`. This forces path resolution inside
    the active execution runtime environment safely without exposing the system to
    arbitrary shell injections ('shell=True').

Pipeline Integrity & Exit Signatures:
    The script tracks formatting outcomes and yields standard operating system exit
    signals upon termination:
        * Exit Code 0: All targeted files are formatted successfully or already
          adhere strictly to formatting baselines.
        * Exit Code 1: The underlying formatting engine encountered a syntax block
          or was missing entirely from the host environment.
"""

import subprocess
import sys


def run_code_formatter() -> None:
    """Invokes the Black formatting engine recursively on the current directory."""
    print("Formatting codebase architecture using Black...")

    # Execute black natively as an internal module via the running interpreter
    # '.' targets the current working directory recursively
    result = subprocess.run(
        [sys.executable, "-m", "black", "."],
        capture_output=True,
        text=True,
    )

    # Catch cases where the black library is entirely absent from the environment
    if result.stderr and "No module named" in result.stderr:
        print("\nERROR: 'black' is not installed in this Python environment.")
        print("Please resolve this by running the following command in your terminal:")
        print(f"  {sys.executable} -m pip install black\n")
        sys.exit(1)

    # Report results out to the terminal interface
    if result.returncode != 0:
        print("\nFormatting Exception: Black encountered errors processing files.")
        if result.stderr:
            print("\n--- Engine Output ---")
            print(result.stderr.strip())
        sys.exit(1)

    # Print success telemetry (Black outputs its summary message to stderr by design)
    if result.stderr:
        print(f"\n{result.stderr.strip()}")

    print("\nSuccess: Codebase formatting operations completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    run_code_formatter()
