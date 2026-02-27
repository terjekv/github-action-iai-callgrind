#!/usr/bin/env python3
import argparse
import hashlib
import json
import pathlib
import shlex
import sys
from typing import Any

BACKENDS = ("iai-callgrind", "criterion")


def normalize_backend(raw: str) -> str:
    value = raw.strip().lower()
    if value in {"iai", "iai-callgrind", "callgrind"}:
        return "iai-callgrind"
    if value in {"criterion"}:
        return "criterion"
    raise ValueError(f"unsupported backend '{raw}' (expected 'iai-callgrind' or 'criterion')")


def normalize_backend_selection(raw: str) -> str:
    value = raw.strip().lower()
    if value in {"all", "any"}:
        return "all"
    return normalize_backend(raw)


def expand_backends(selection: str) -> list[str]:
    if selection == "all":
        return list(BACKENDS)
    return [selection]


def infer_name_backend(name: str) -> str | None:
    lowered = name.lower()
    has_callgrind = "callgrind" in lowered
    has_criterion = "criterion" in lowered
    if has_callgrind and not has_criterion:
        return "iai-callgrind"
    if has_criterion and not has_callgrind:
        return "criterion"
    return None


def discover_benchmarks(
    repo_path: pathlib.Path, working_directory: str, backend_selection: str
) -> list[dict[str, Any]]:
    benches_dir = repo_path / working_directory / "benches"
    if not benches_dir.exists():
        return []

    selected_backends = set(expand_backends(backend_selection))
    benchmarks: list[dict[str, Any]] = []
    for path in sorted(benches_dir.glob("*.rs")):
        if path.name == "mod.rs":
            continue

        inferred_backend = infer_name_backend(path.stem)
        if inferred_backend and inferred_backend not in selected_backends:
            continue

        candidate_backends = [inferred_backend] if inferred_backend else list(BACKENDS)
        for backend in candidate_backends:
            if backend not in selected_backends:
                continue
            benchmarks.append({"name": path.stem, "bench": path.stem, "backend": backend})
    return benchmarks


def normalize_feature_sets(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError("feature_sets_json must be a JSON array")

    normalized: list[dict[str, Any]] = []
    for entry in raw:
        if isinstance(entry, str):
            normalized.append({"name": entry, "features": entry})
            continue
        if not isinstance(entry, dict):
            raise ValueError("feature set entries must be objects or strings")
        name = entry.get("name") or (entry.get("features") or "default")
        normalized.append(
            {
                "name": str(name),
                "features": str(entry.get("features", "")),
                "no_default_features": bool(entry.get("no_default_features", False)),
            }
        )
    if not normalized:
        normalized = [{"name": "default", "features": "", "no_default_features": False}]
    return normalized


def build_command(
    spec: dict[str, Any],
    feature_set: dict[str, Any],
    cargo_args: str,
    backend: str,
    criterion_cli_args: str,
) -> str:
    features = feature_set["features"].strip()
    no_default = feature_set.get("no_default_features", False)

    command = spec.get("command")
    if command:
        command = str(command)
        command = command.replace("{features}", features)
        command = command.replace(
            "{no_default_features_flag}", "--no-default-features" if no_default else ""
        )
        if "{features}" not in str(spec.get("command")) and features:
            command += f" --features {shlex.quote(features)}"
        if "{no_default_features_flag}" not in str(spec.get("command")) and no_default:
            command += " --no-default-features"
    else:
        bench = spec.get("bench")
        if not bench:
            raise ValueError(f"benchmark spec '{spec.get('name', 'unknown')}' is missing 'bench'")

        parts = ["cargo", "bench", "--bench", shlex.quote(str(bench))]
        manifest_path = spec.get("manifest_path")
        if manifest_path:
            parts.extend(["--manifest-path", shlex.quote(str(manifest_path))])
        package = spec.get("package")
        if package:
            parts.extend(["--package", shlex.quote(str(package))])
        if features:
            parts.extend(["--features", shlex.quote(features)])
        if no_default:
            parts.append("--no-default-features")
        extra_args = spec.get("args")
        if extra_args:
            parts.append(str(extra_args))
        if backend == "criterion":
            criterion_args = str(spec.get("criterion_args", criterion_cli_args)).strip()
            if criterion_args:
                parts.extend(["--", criterion_args])
        command = " ".join(parts)

    if cargo_args.strip():
        command = f"{command} {cargo_args.strip()}"

    return " ".join(command.split())


def expand_benchmark_entry(entry: Any, backend_selection: str) -> list[dict[str, Any]]:
    selected_backends = expand_backends(backend_selection)

    def with_backends(base: dict[str, Any], explicit_backend: str | None) -> list[dict[str, Any]]:
        if explicit_backend:
            if explicit_backend not in selected_backends:
                return []
            item = dict(base)
            item["backend"] = explicit_backend
            return [item]

        items: list[dict[str, Any]] = []
        for backend in selected_backends:
            item = dict(base)
            item["backend"] = backend
            items.append(item)
        return items

    if isinstance(entry, str):
        return with_backends({"name": entry, "bench": entry}, explicit_backend=None)
    if isinstance(entry, dict):
        explicit_backend = entry.get("backend")
        normalized: str | None = None
        if explicit_backend:
            normalized = normalize_backend(str(explicit_backend))
        return with_backends(entry, explicit_backend=normalized)

    raise ValueError("benchmark entries must be objects or strings")


def make_matrix(
    benchmarks: list[dict[str, Any]],
    feature_sets: list[dict[str, Any]],
    cargo_args: str,
    criterion_cli_args: str,
) -> dict[str, list[dict[str, Any]]]:
    include: list[dict[str, Any]] = []
    for bench in benchmarks:
        backend = normalize_backend(str(bench.get("backend", "iai-callgrind")))
        bench_name = str(bench.get("name") or bench.get("bench") or "benchmark")
        for feature_set in feature_sets:
            case_seed = f"{backend}|{bench_name}|{feature_set['name']}|{feature_set['features']}"
            case_id = hashlib.sha1(case_seed.encode("utf-8")).hexdigest()[:10]
            include.append(
                {
                    "id": case_id,
                    "backend": backend,
                    "benchmark_name": bench_name,
                    "feature_name": feature_set["name"],
                    "command": build_command(
                        bench, feature_set, cargo_args, backend, criterion_cli_args
                    ),
                }
            )
    return {"include": include}


def normalize_option_values(
    argv: list[str], value_options: set[str], known_options: set[str]
) -> list[str]:
    normalized: list[str] = []
    idx = 0
    while idx < len(argv):
        token = argv[idx]
        if token in value_options and idx + 1 < len(argv):
            next_token = argv[idx + 1]
            if next_token.startswith("-") and next_token not in known_options:
                normalized.append(f"{token}={next_token}")
                idx += 2
                continue
        normalized.append(token)
        idx += 1
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--working-directory", default=".")
    parser.add_argument("--benchmarks-json", required=True)
    parser.add_argument("--feature-sets-json", required=True)
    parser.add_argument("--backend", default="iai-callgrind")
    parser.add_argument("--criterion-cli-args", default="--noplot")
    parser.add_argument("--auto-discover", action="store_true")
    parser.add_argument("--cargo-args", default="")
    parser.add_argument("--output", required=True)
    parsed_argv = normalize_option_values(
        sys.argv[1:],
        value_options={"--criterion-cli-args", "--cargo-args"},
        known_options=set(parser._option_string_actions.keys()),
    )
    args = parser.parse_args(parsed_argv)

    repo_path = pathlib.Path(args.repo_path).resolve()
    backend_selection = normalize_backend_selection(args.backend)

    benchmarks_raw = json.loads(args.benchmarks_json)
    if benchmarks_raw and not isinstance(benchmarks_raw, list):
        raise ValueError("benchmarks_json must be a JSON array")

    benchmarks: list[dict[str, Any]] = []
    for entry in benchmarks_raw:
        benchmarks.extend(expand_benchmark_entry(entry, backend_selection))

    if args.auto_discover and not benchmarks:
        benchmarks = discover_benchmarks(repo_path, args.working_directory, backend_selection)

    if not benchmarks:
        print(
            f"No benchmarks configured for backend '{backend_selection}'. "
            "Provide benchmarks_json or enable auto_discover with benches/*.rs",
            file=sys.stderr,
        )
        return 1

    feature_sets = normalize_feature_sets(json.loads(args.feature_sets_json))

    matrix = make_matrix(
        benchmarks,
        feature_sets,
        args.cargo_args,
        args.criterion_cli_args,
    )
    pathlib.Path(args.output).write_text(json.dumps(matrix), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
