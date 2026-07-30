#!/usr/bin/env python3
import argparse


# v2 keeps this value stable in matrices, result artifacts, summaries, and history.
CALLGRIND_BACKEND = "iai-callgrind"
CRITERION_BACKEND = "criterion"
BACKENDS = (CALLGRIND_BACKEND, CRITERION_BACKEND)
CALLGRIND_ALIASES = {"gungraun", "iai", "iai-callgrind", "callgrind"}


def normalize_backend(raw: str) -> str:
    value = str(raw).strip().lower()
    if value in CALLGRIND_ALIASES:
        return CALLGRIND_BACKEND
    if value == CRITERION_BACKEND:
        return CRITERION_BACKEND
    raise ValueError(
        f"unsupported backend '{raw}' "
        "(expected 'gungraun', 'iai-callgrind', or 'criterion')"
    )


def normalize_backend_selection(raw: str) -> str:
    value = str(raw).strip().lower()
    if value in {"all", "any"}:
        return "all"
    return normalize_backend(raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backend")
    parser.add_argument("--selection", action="store_true")
    args = parser.parse_args()

    normalizer = normalize_backend_selection if args.selection else normalize_backend
    try:
        print(normalizer(args.backend))
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
