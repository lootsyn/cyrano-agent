"""Execute a unittest pattern; zero matching tests is an error."""

import argparse
import unittest

from bootstrap import activate

ROOT = activate()


def main() -> int:
    """Run only the requested source tests without a live provider."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern", required=True)
    args = parser.parse_args()
    if "/" in args.pattern or "\\" in args.pattern:
        parser.error("use a basename pattern inside tests/")
    suite = unittest.defaultTestLoader.discover(
        str(ROOT.parent / "tests/unit_tests/cyrano"), pattern=args.pattern
    )
    if suite.countTestCases() == 0:
        print(
            "NO_TESTS: no matching foundation test; native product "
            "tests use the documented pytest command"
        )
        return 2
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() and not result.skipped else 1


if __name__ == "__main__":
    raise SystemExit(main())
