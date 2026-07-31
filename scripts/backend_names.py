#!/usr/bin/env python3
import argparse
import os


V2_CALLGRIND_BACKEND = "iai-callgrind"
V3_GUNGRAUN_BACKEND = "gungraun"
CRITERION_BACKEND = "criterion"
LEGACY_GUNGRAUN_ALIASES = {"iai", "iai-callgrind", "callgrind"}
GUNGRAUN_ALIASES = {V3_GUNGRAUN_BACKEND, *LEGACY_GUNGRAUN_ALIASES}


def canonical_gungraun_backend() -> str:
    override = os.environ.get("RUST_PR_BENCH_CANONICAL_BACKEND", "").strip().lower()
    if override:
        if override not in {V2_CALLGRIND_BACKEND, V3_GUNGRAUN_BACKEND}:
            raise ValueError(
                "RUST_PR_BENCH_CANONICAL_BACKEND must be 'gungraun' or "
                "'iai-callgrind'"
            )
        return override

    # Older immutable reusable-workflow tags historically checked helper scripts
    # out from the default branch. Preserve their v2 wire contract when those
    # workflows execute the current helpers. The v3 workflow sets the override
    # above explicitly, while local script use defaults to current v3 behavior.
    if os.environ.get("GITHUB_ACTIONS", "").strip().lower() == "true":
        return V2_CALLGRIND_BACKEND
    return V3_GUNGRAUN_BACKEND


GUNGRAUN_BACKEND = canonical_gungraun_backend()
BACKENDS = (GUNGRAUN_BACKEND, CRITERION_BACKEND)


def normalize_backend(raw: str) -> str:
    value = str(raw).strip().lower()
    if value in GUNGRAUN_ALIASES:
        return GUNGRAUN_BACKEND
    if value == CRITERION_BACKEND:
        return CRITERION_BACKEND
    raise ValueError(
        f"unsupported backend '{raw}' "
        "(expected 'gungraun', 'criterion', or 'all'; legacy aliases "
        "'iai-callgrind', 'iai', and 'callgrind' are also accepted)"
    )


def is_legacy_backend(raw: str) -> bool:
    return str(raw).strip().lower() in LEGACY_GUNGRAUN_ALIASES


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
