#!/usr/bin/env python3
import argparse
import hashlib
import json
import pathlib
import shlex
import sys
from typing import Any


def discover_benchmarks(repo_path: pathlib.Path, working_directory: str) -> list[dict[str, Any]]:
    benches_dir = repo_path / working_directory / "benches"
    if not benches_dir.exists():
        return []

    benchmarks: list[dict[str, Any]] = []
    for path in sorted(benches_dir.glob("*.rs")):
        if path.name == "mod.rs":
            continue
        benchmarks.append({"name": path.stem, "bench": path.stem})
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


def build_command(spec: dict[str, Any], feature_set: dict[str, Any], cargo_args: str) -> str:
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
        command = " ".join(parts)

    if cargo_args.strip():
        command = f"{command} {cargo_args.strip()}"

    return " ".join(command.split())


def make_matrix(
    benchmarks: list[dict[str, Any]], feature_sets: list[dict[str, Any]], cargo_args: str
) -> dict[str, list[dict[str, Any]]]:
    include: list[dict[str, Any]] = []
    for bench in benchmarks:
        bench_name = str(bench.get("name") or bench.get("bench") or "benchmark")
        for feature_set in feature_sets:
            case_seed = f"{bench_name}|{feature_set['name']}|{feature_set['features']}"
            case_id = hashlib.sha1(case_seed.encode("utf-8")).hexdigest()[:10]
            include.append(
                {
                    "id": case_id,
                    "benchmark_name": bench_name,
                    "feature_name": feature_set["name"],
                    "command": build_command(bench, feature_set, cargo_args),
                }
            )
    return {"include": include}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--working-directory", default=".")
    parser.add_argument("--benchmarks-json", required=True)
    parser.add_argument("--feature-sets-json", required=True)
    parser.add_argument("--auto-discover", action="store_true")
    parser.add_argument("--cargo-args", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    repo_path = pathlib.Path(args.repo_path).resolve()

    benchmarks_raw = json.loads(args.benchmarks_json)
    if benchmarks_raw and not isinstance(benchmarks_raw, list):
        raise ValueError("benchmarks_json must be a JSON array")

    benchmarks: list[dict[str, Any]] = []
    for entry in benchmarks_raw:
        if isinstance(entry, str):
            benchmarks.append({"name": entry, "bench": entry})
        elif isinstance(entry, dict):
            benchmarks.append(entry)
        else:
            raise ValueError("benchmark entries must be objects or strings")

    if args.auto_discover and not benchmarks:
        benchmarks = discover_benchmarks(repo_path, args.working_directory)

    if not benchmarks:
        print(
            "No benchmarks configured. Provide benchmarks_json or enable auto_discover with benches/*.rs",
            file=sys.stderr,
        )
        return 1

    feature_sets = normalize_feature_sets(json.loads(args.feature_sets_json))

    matrix = make_matrix(benchmarks, feature_sets, args.cargo_args)
    pathlib.Path(args.output).write_text(json.dumps(matrix), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
