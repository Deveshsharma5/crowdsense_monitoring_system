"""
CrowdSense Comprehensive Test Suite Runner
Runs all unit and integration tests across subsystems.
"""
import sys
import os
import subprocess

def run():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(tests_dir, ".."))
    python_bin = sys.executable

    tests = [
        ("Zone Thresholds Integration Tests", os.path.join(tests_dir, "test_zone_thresholds.py")),
        ("Telegram Alert Service Unit Tests", os.path.join(tests_dir, "test_telegram_service.py")),
    ]

    print("=" * 60)
    print("        CROWDSENSE AUTOMATED TEST SUITE RUNNER")
    print("=" * 60)
    print(f"Python interpreter: {python_bin}")
    print(f"Working Directory:  {root_dir}\n")

    all_passed = True

    for name, test_path in tests:
        print(f"\n>>> Running: {name} ({os.path.basename(test_path)})...")
        print("-" * 60)
        ret = subprocess.run([python_bin, test_path], cwd=root_dir)
        if ret.returncode != 0:
            print(f"FAILED: {name}")
            all_passed = False
        else:
            print(f"PASSED: {name}")

    print("\n" + "=" * 60)
    if all_passed:
        print("  ALL TEST SUITES COMPLETED SUCCESSFULLY!")
    else:
        print("  SOME TESTS FAILED - PLEASE REVIEW LOGS")
    print("=" * 60)

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(run())

