#!/usr/bin/env python3
"""Extract pytest subtest coverage and enforce a non-decreasing baseline.

The client gate compares named failures separately.  This helper closes the
other side of that contract: silently deleting a ``with self.subTest(...)``
case must not look clean merely because the remaining tests still pass.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

_SUMMARY = re.compile(r"(?P<count>[0-9]+) subtests? passed\b")


def count_subtests(text: str) -> int:
    """Return the final pytest subtest count, refusing a missing summary."""
    matches = [int(match.group("count")) for match in _SUMMARY.finditer(text)]
    if not matches:
        raise ValueError("pytest summary has no '<N> subtests passed' field")
    return matches[-1]


def verdict(actual: int, baseline: int) -> tuple[bool, int, str]:
    delta = actual - baseline
    if delta < 0:
        return False, delta, "REQUIRES_EXPLANATION"
    return True, delta, "CLEAN"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=pathlib.Path)
    parser.add_argument("--baseline", type=int, required=True)
    args = parser.parse_args(argv)

    try:
        actual = count_subtests(args.log.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as exc:
        print(f"SUBTEST_VERDICT=UNPARSEABLE ({exc})")
        return 2

    ok, delta, label = verdict(actual, args.baseline)
    print(f"SUBTESTS={actual}")
    print(f"SUBTEST_BASELINE={args.baseline}")
    print(f"SUBTEST_DELTA={delta:+d}")
    print(f"SUBTEST_VERDICT={label}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
