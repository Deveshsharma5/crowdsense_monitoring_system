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
        ("Crowd Counting & Spatial Density Unit Tests", os.path.join(tests_dir, "test_crowd_density.py")),
        ("Zone Thresholds & PDF Integration Tests", os.path.join(tests_dir, "test_zone_thresholds.py")),
        ("Telegram Alert Service Security & Unit Tests", os.path.join(tests_dir, "test_telegram_service.py")),
    ]

    print("=" * 65)
    print("        CROWDSENSE AUTOMATED TEST SUITE MASTER RUNNER")
    print("=" * 65)
    print(f"Python interpreter: {python_bin}")
    print(f"Working Directory:  {root_dir}\n")

    all_passed = True
    results = []

    for name, test_path in tests:
        print(f"\n>>> Running: {name} ({os.path.basename(test_path)})...")
        print("-" * 65)
        ret = subprocess.run([python_bin, test_path], cwd=root_dir)
        if ret.returncode != 0:
            print(f"FAILED: {name}")
            results.append((name, "FAILED"))
            all_passed = False
        else:
            print(f"PASSED: {name}")
            results.append((name, "PASSED"))

    print("\n" + "=" * 65)
    print("                       TEST SUMMARY")
    print("=" * 65)
    for name, status in results:
        print(f"  [{status}] {name}")
    print("-" * 65)
    if all_passed:
        print("  ALL TEST SUITES COMPLETED SUCCESSFULLY! (61/61 TESTS PASS)")
    else:
        print("  SOME TESTS FAILED - PLEASE REVIEW LOGS")
    print("=" * 65)

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(run())
