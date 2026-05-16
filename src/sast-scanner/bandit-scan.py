"""Automated Static Application Security Testing (SAST) Pipeline Gate.

This module provides a production-ready, automated utility to perform static 
analysis on custom source code. It scans internal application packages for 
security code smells, structural flaws, and high-risk anti-patterns before 
the code is integrated into a production environment.

Theoretical Background & SAST Mechanics:
    Unlike dynamic scanners that analyze runtime behavior, a SAST utility inspects 
    the raw source code without executing it. It parses Python files into an 
    Abstract Syntax Tree (AST), which maps out the exact structural hierarchy of 
    the logic. The underlying 'Bandit' engine passes specialized plugins over 
    this tree to identify dangerous nodes, such as:
        1. Insecure Functions: References to 'eval()', 'exec()', or 'input()'.
        2. Weak Cryptography: Usage of insecure hashing variants (MD5, SHA1).
        3. Dynamic Shell Spawning: Insecure 'subprocess' execution loops with 
           'shell=True' or obsolete 'os.system()' implementations.
        4. Insecure Network Binds: Hardcoded binds to '0.0.0.0' allowing 
           unrestricted ingress access.

Cross-Platform Infrastructure Compliance:
    To maintain deterministic reliability across diverse OS runtimes (especially 
    segmented environments like the Windows Microsoft Store Python installation), 
    the engine is invoked as a native internal module through the running 
    interpreter path ('sys.executable'). This bypasses standard system path 
    resolution vulnerabilities and negates the need for 'shell=True' logic inside 
    the control script.

Pipeline Gate Matrix:
    The utility returns a binary success or failure status to the hosting automated 
    CI/CD framework (e.g., GitHub Actions, GitLab Runner):
        * Exit Code 0: Syntax passes baseline code-hygiene and severity parameters.
        * Exit Code 1: Medium-to-High risk structural flaws were found. The 
          build or deployment step is terminated immediately.
"""

import subprocess
import sys


def run_sast_scan() -> None:
    """Recursively parses source files for security flaws using the Bandit engine."""
    print("Analyzing code syntax for security smells...\n")

    # Execute bandit natively as an internal module via the active interpreter
    # Parameters explained:
    #   '-r': Recursive scanning through the targeted folder path.
    #   './app': The target directory containing the application source code.
    #   '-ll': Log level filtration; reports only Medium or High severity issues.
    result = subprocess.run(
        [sys.executable, "-m", "bandit", "-r", "./app", "-ll"],
        capture_output=True,
        text=True,
    )

    # Trap cases where the bandit library is not installed in the current runtime
    if result.stderr and "No module named" in result.stderr:
        print("ERROR: 'bandit' is not installed in this Python environment.")
        print("Please resolve this by running the following command in your terminal:")
        print(f"  {sys.executable} -m pip install bandit\n")
        sys.exit(1)

    # Evaluate execution status codes. Non-zero means vulnerabilities were discovered
    if result.returncode != 0:
        print("SECURITY ALERT: Flaws detected in code architecture!")
        print("(Examples: Hardcoded binds, eval functions, weak crypto, unsafe subprocesses)")
        
        # Print standard output findings (where Bandit writes details)
        if result.stdout:
            print("\n--- Scan Results ---")
            print(result.stdout.strip())
            
        # Print any underlying processing errors or syntax issues
        if result.stderr:
            print("\n--- Scanner Errors/Warnings ---")
            print(result.stderr.strip())
            
        sys.exit(1)

    print("Success: Code syntax clears baseline security checks.")
    sys.exit(0)


if __name__ == "__main__":
    run_sast_scan()