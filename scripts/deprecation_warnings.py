#!/usr/bin/env python3
import argparse
import json
from typing import Any

from backend_names import is_legacy_backend
from resolve_threshold import UNSET


def legacy_backend_values(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "backend" and isinstance(nested, str) and is_legacy_backend(nested):
                found.add(nested.strip().lower())
            else:
                found.update(legacy_backend_values(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(legacy_backend_values(nested))
    return found


def collect_deprecations(
    backend: str,
    benchmarks_json: str,
    iai_callgrind_threshold: float,
) -> list[str]:
    deprecations: list[str] = []
    aliases: set[str] = set()
    if is_legacy_backend(backend):
        aliases.add(backend.strip().lower())

    try:
        benchmark_specs = json.loads(benchmarks_json)
    except json.JSONDecodeError as error:
        raise ValueError(f"benchmarks_json is not valid JSON: {error}") from error
    aliases.update(legacy_backend_values(benchmark_specs))
    if aliases:
        names = ", ".join(sorted(aliases))
        deprecations.append(
            f"legacy backend name(s) {names}; use 'gungraun' instead"
        )
    if float(iai_callgrind_threshold) != UNSET:
        deprecations.append(
            "regression_threshold_pct_iai_callgrind; "
            "use regression_threshold_pct_gungraun instead"
        )
    return deprecations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True)
    parser.add_argument("--benchmarks-json", required=True)
    parser.add_argument("--iai-callgrind-threshold", required=True, type=float)
    args = parser.parse_args()

    try:
        deprecations = collect_deprecations(
            args.backend,
            args.benchmarks_json,
            args.iai_callgrind_threshold,
        )
    except ValueError as error:
        parser.error(str(error))
    if deprecations:
        message = (
            "Deprecated Rust PR Bench v3 input detected: "
            + "; ".join(deprecations)
            + ". Legacy aliases remain supported through v3 and will not be removed "
            "before v4."
        )
        print(f"::warning title=Rust PR Bench v3 deprecation::{message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
