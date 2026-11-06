#!/usr/bin/env python3
"""
PolarSnap Master E2E Test Runner
Authoritative, independent test runner executing Tiers 1-4 across all 32 features.
"""
import argparse
import inspect
import json
import os
from pathlib import Path
import sys
import time
import unittest
from typing import Dict, List, Any, Optional, Set, Tuple

# Add parent directory to sys.path to allow module imports
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

Tuple_Meta = Tuple[Set[int], int]


def feature(feature_id: int):
    """Decorator to mark a test case with a feature ID (1..32)."""
    def decorator(fn):
        if not hasattr(fn, "_covered_features"):
            fn._covered_features = set()
        fn._covered_features.add(feature_id)
        return fn
    return decorator


def tier(tier_num: int):
    """Decorator to mark a test case with a tier number (1..4)."""
    def decorator(fn):
        fn._test_tier = tier_num
        return fn
    return decorator


class PolarTestResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.successes = []
        self.feature_coverage: Dict[int, int] = {i: 0 for i in range(1, 33)}
        self.tier_coverage: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
        self.test_details: List[Dict[str, Any]] = []

    def _extract_metadata(self, test) -> Tuple_Meta:
        test_method = getattr(test, test._testMethodName, None)
        features: Set[int] = set()
        tier_num: int = 1

        # Check method attributes
        if test_method:
            if hasattr(test_method, "_covered_features"):
                features.update(test_method._covered_features)
            if hasattr(test_method, "_test_tier"):
                tier_num = test_method._test_tier

        # Fallback to test class attributes or docstrings
        if not features and hasattr(test, "FEATURE_IDS"):
            features.update(test.FEATURE_IDS)
        if hasattr(test, "TIER"):
            tier_num = test.TIER

        # Path-based tier fallback
        test_file = inspect.getfile(test.__class__)
        if "tier1_features" in test_file:
            tier_num = 1
        elif "tier2_boundaries" in test_file:
            tier_num = 2
        elif "tier3_combinations" in test_file:
            tier_num = 3
        elif "tier4_workloads" in test_file:
            tier_num = 4

        return features, tier_num

    def addSuccess(self, test):
        super().addSuccess(test)
        self.successes.append(test)
        features, tier_num = self._extract_metadata(test)
        self.tier_coverage[tier_num] = self.tier_coverage.get(tier_num, 0) + 1
        for f in features:
            if f in self.feature_coverage:
                self.feature_coverage[f] += 1

        self.test_details.append({
            "name": test.id(),
            "status": "PASSED",
            "tier": tier_num,
            "features": sorted(list(features)),
            "error": None
        })

    def addFailure(self, test, err):
        super().addFailure(test, err)
        features, tier_num = self._extract_metadata(test)
        self.test_details.append({
            "name": test.id(),
            "status": "FAILED",
            "tier": tier_num,
            "features": sorted(list(features)),
            "error": self._exc_info_to_string(err, test)
        })

    def addError(self, test, err):
        super().addError(test, err)
        features, tier_num = self._extract_metadata(test)
        self.test_details.append({
            "name": test.id(),
            "status": "ERROR",
            "tier": tier_num,
            "features": sorted(list(features)),
            "error": self._exc_info_to_string(err, test)
        })

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        features, tier_num = self._extract_metadata(test)
        self.test_details.append({
            "name": test.id(),
            "status": "SKIPPED",
            "tier": tier_num,
            "features": sorted(list(features)),
            "error": reason
        })


def discover_and_filter_suite(
    tier_filter: Optional[int] = None,
    feature_filter: Optional[int] = None,
    milestone_filter: Optional[str] = None
) -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    tier_subdirs = {
        1: CURRENT_DIR / "tier1_features",
        2: CURRENT_DIR / "tier2_boundaries",
        3: CURRENT_DIR / "tier3_combinations",
        4: CURRENT_DIR / "tier4_workloads",
    }

    dirs_to_search = []
    if tier_filter is not None and tier_filter in tier_subdirs:
        dirs_to_search.append((tier_filter, tier_subdirs[tier_filter]))
    else:
        for t_num, t_path in tier_subdirs.items():
            dirs_to_search.append((t_num, t_path))

    milestone_features = {
        "M1": set(range(1, 9)),
        "M2": set(range(9, 15)),
        "M3": set(range(15, 20)),
        "M4": set(range(20, 26)),
        "M5": set(range(26, 31)),
        "M6": set(range(31, 33)),
    }

    for t_num, t_path in dirs_to_search:
        if not t_path.exists():
            continue
        discovered = loader.discover(start_dir=str(t_path), pattern="test_*.py", top_level_dir=str(PROJECT_ROOT))
        for test in _flatten_tests(discovered):
            test_method = getattr(test, test._testMethodName, None)
            features: Set[int] = set()
            if test_method and hasattr(test_method, "_covered_features"):
                features.update(test_method._covered_features)
            if hasattr(test, "FEATURE_IDS"):
                features.update(test.FEATURE_IDS)

            # Apply Feature Filter
            if feature_filter is not None and feature_filter not in features:
                continue

            # Apply Milestone Filter
            if milestone_filter is not None:
                allowed_features = milestone_features.get(milestone_filter.upper(), set())
                if not features.intersection(allowed_features):
                    continue

            suite.addTest(test)

    return suite


def _flatten_tests(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten_tests(item)
        else:
            yield item


def run_tests(
    tier_filter: Optional[int] = None,
    feature_filter: Optional[int] = None,
    milestone_filter: Optional[str] = None,
    dry_run: bool = False,
    json_output: Optional[str] = None,
    verbose: bool = False
) -> int:
    suite = discover_and_filter_suite(tier_filter, feature_filter, milestone_filter)
    total_discovered = suite.countTestCases()

    print("=" * 80)
    print(" PolarSnap -- by Trandif | Master E2E Test Runner")
    print("=" * 80)
    print(f"Discovered Tests: {total_discovered}")
    if tier_filter:
        print(f"Tier Filter: Tier {tier_filter}")
    if feature_filter:
        print(f"Feature Filter: Feature #{feature_filter}")
    if milestone_filter:
        print(f"Milestone Filter: {milestone_filter}")
    print("-" * 80)

    if dry_run:
        print("[DRY-RUN] Test discovery complete. Displaying discovered tests:")
        for t in _flatten_tests(suite):
            print(f"  - {t.id()}")
        print("-" * 80)
        print("Dry run completed successfully.")
        return 0

    start_time = time.perf_counter()
    result = PolarTestResult()
    runner = unittest.TextTestRunner(verbosity=2 if verbose else 1, resultclass=lambda *args, **kwargs: result)
    suite.run(result)
    duration = time.perf_counter() - start_time

    # Print Report
    print("\n" + "=" * 80)
    print(" TEST EXECUTION SUMMARY")
    print("=" * 80)
    print(f"Total Tests Executed: {result.testsRun}")
    print(f"Passed:              {len(result.successes)}")
    print(f"Failures:            {len(result.failures)}")
    print(f"Errors:              {len(result.errors)}")
    print(f"Skipped:             {len(result.skipped)}")
    print(f"Execution Duration:  {duration:.3f} seconds")
    if result.failures:
        print("\n" + "!" * 80)
        print(" FAILURES:")
        for test, err in result.failures:
            print(f"--- {test.id()} ---")
            print(err)
        print("!" * 80)
    if result.errors:
        print("\n" + "!" * 80)
        print(" ERRORS:")
        for test, err in result.errors:
            print(f"--- {test.id()} ---")
            print(err)
        print("!" * 80)
    print("-" * 80)
    print(" Tier Breakdown:")
    for t_id in sorted(result.tier_coverage.keys()):
        count = result.tier_coverage[t_id]
        print(f"   Tier {t_id}: {count} tests executed")
    print("-" * 80)
    print(" Feature Coverage (Features 1..32):")
    covered_features_count = 0
    for f_id in range(1, 33):
        cnt = result.feature_coverage.get(f_id, 0)
        mark = "PASS" if cnt > 0 else "FAIL"
        if cnt > 0:
            covered_features_count += 1
        print(f"   Feature {f_id:2d}: [{mark:4s}] ({cnt:2d} assertions)", end="\n" if f_id % 4 == 0 else "  |  ")

    print(f"\nTotal Covered Features: {covered_features_count}/32 ({covered_features_count / 32 * 100:.1f}%)")
    print("=" * 80)

    # Export JSON if requested
    if json_output:
        report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_tests": result.testsRun,
            "passed": len(result.successes),
            "failed": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped),
            "duration_seconds": duration,
            "tier_counts": result.tier_coverage,
            "feature_coverage": result.feature_coverage,
            "covered_features_count": covered_features_count,
            "is_success": result.wasSuccessful(),
            "details": result.test_details
        }
        out_path = Path(json_output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Standardized test results exported to: {out_path.resolve()}")

    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description="PolarSnap Master E2E Test Runner")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4], help="Execute specific test tier")
    parser.add_argument("--feature", type=int, choices=range(1, 33), help="Execute tests covering specific feature ID (1-32)")
    parser.add_argument("--milestone", type=str, choices=["M1", "M2", "M3", "M4", "M5", "M6"], help="Execute tests for milestone")
    parser.add_argument("--dry-run", action="store_true", help="Discover tests without executing")
    parser.add_argument("--json-output", type=str, help="Export results to JSON file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose test execution output")

    args = parser.parse_args()
    exit_code = run_tests(
        tier_filter=args.tier,
        feature_filter=args.feature,
        milestone_filter=args.milestone,
        dry_run=args.dry_run,
        json_output=args.json_output,
        verbose=args.verbose
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
