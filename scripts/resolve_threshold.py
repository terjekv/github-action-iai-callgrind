#!/usr/bin/env python3
import argparse
import math


UNSET = -1.0


def resolve_callgrind_threshold(
    generic: float,
    gungraun_specific: float = UNSET,
    iai_callgrind_specific: float = UNSET,
) -> float:
    values = {
        "regression_threshold_pct": float(generic),
        "regression_threshold_pct_gungraun": float(gungraun_specific),
        "regression_threshold_pct_iai_callgrind": float(iai_callgrind_specific),
    }
    for name, value in values.items():
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
        if name == "regression_threshold_pct" and value < 0:
            raise ValueError(f"{name} must be non-negative")
        if name != "regression_threshold_pct" and value < 0 and value != UNSET:
            raise ValueError(f"{name} must be non-negative or -1")

    new_value = values["regression_threshold_pct_gungraun"]
    old_value = values["regression_threshold_pct_iai_callgrind"]
    if new_value != UNSET and old_value != UNSET and new_value != old_value:
        raise ValueError(
            "conflicting Callgrind thresholds: "
            "regression_threshold_pct_gungraun "
            f"is {new_value:g}, but regression_threshold_pct_iai_callgrind "
            f"is {old_value:g}; set only one name or give both the same value"
        )
    if new_value != UNSET:
        return new_value
    if old_value != UNSET:
        return old_value
    return values["regression_threshold_pct"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generic", required=True, type=float)
    parser.add_argument("--gungraun", default=UNSET, type=float)
    parser.add_argument("--iai-callgrind", default=UNSET, type=float)
    args = parser.parse_args()

    try:
        threshold = resolve_callgrind_threshold(
            args.generic,
            args.gungraun,
            args.iai_callgrind,
        )
    except ValueError as error:
        parser.error(str(error))
    print(f"{threshold:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
