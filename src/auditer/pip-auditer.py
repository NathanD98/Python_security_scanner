"""Automated Software Supply Chain Dependency Security Gate.

This module provides a standalone, automated utility to audit Python project
dependencies for known Common Vulnerabilities and Exposures (CVEs). It uses the
PyPA-recommended 'pip-audit' engine to parse a local 'requirements.txt' file
and cross-reference packages against the Python Packaging Advisory Database.

Design Architecture & Cross-Platform Reliability:
    To bypass strict permission boundaries, path shielding, and file execution
    isolation common to Windows Store Python installations, the script executes
    the underlying security engine natively as an internal module via:
    `sys.executable -m pip_audit`

    This ensures that if the executing Python environment contains the package,
    the system shell boundaries are bypassed without needing 'shell=True'.

CI/CD Pipeline Integration:
    The script abstracts standard output into structured JSON streams. If any
    vulnerabilities are identified, it explicitly prints the data block and
    terminates with an exit code of 1, providing a definitive hard-stop
    gate mechanism for DevSecOps continuous integration pipelines.
"""

import subprocess
import sys


def check_dependencies() -> None:
    """Audits third-party dependencies for known CVEs using pip-audit."""
    print("Auditing third-party dependencies for known CVEs...")

    # Execute pip_audit cleanly as a module using the current interpreter path
    result = subprocess.run(
        [sys.executable, "-m", "pip_audit", "-r", "requirements.txt", "-f", "json"],
        capture_output=True,
        text=True,
    )

    # Catch cases where pip-audit is entirely missing from the environment
    if "is not recognized as an internal or external command" in result.stderr:
        print("\nERROR: 'pip-audit' is not installed in this Python environment.")
        print("Please resolve this by running the following command in your terminal:")
        print(f"  {sys.executable} -m pip install pip-audit\n")
        sys.exit(1)

    # Evaluate execution status codes. Non-zero means vulnerabilities were discovered
    if result.returncode != 0:
        print("\nSECURITY CRITICAL: Vulnerable packages found in requirements.txt!")
        if result.stdout:
            print("\nScan Results (JSON):")
            print(result.stdout)
        sys.exit(1)

    print("Success: All dependencies are clean.")
    sys.exit(0)


if __name__ == "__main__":
    check_dependencies()
