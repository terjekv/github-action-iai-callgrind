#!/usr/bin/env python3
import argparse
import json
import os
import pathlib
import re
import subprocess
import time
from typing import Any


def parse_summary(path: pathlib.Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for _ in range(300):
                line = handle.readline()
                if not line:
                    break
                if line.startswith("summary:"):
                    _, value = line.split(":", 1)
                    # Newer callgrind formats can emit multiple values in summary.
                    # We compare the primary event (first value) for compatibility.
                    first_token = value.strip().split()[0]
                    return int(first_token)
    except (OSError, ValueError, IndexError):
        return None
    return None


def scan_callgrind_files(target_dir: pathlib.Path) -> list[pathlib.Path]:
    if not target_dir.exists():
        return []

    candidates: list[pathlib.Path] = []
    for path in target_dir.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        if "callgrind.out" in name or name.startswith("callgrind."):
            candidates.append(path)
    return candidates


def normalize_metric_name(path: pathlib.Path) -> str:
    # callgrind filenames can include run-specific numeric suffixes (for example PID).
    # Strip trailing ".<digits>" to make base/head metric keys comparable.
    normalized = re.sub(r"\.\d+$", "", path.as_posix())
    return normalized


def collect_metrics(target_dir: pathlib.Path, start_ns: int, before_paths: set[str]) -> dict[str, Any]:
    files = scan_callgrind_files(target_dir)
    selected: list[pathlib.Path] = []
    for path in files:
        stat = path.stat()
        if str(path) not in before_paths or stat.st_mtime_ns >= start_ns:
            selected.append(path)

    if not selected:
        selected = sorted(files, key=lambda p: p.stat().st_mtime_ns, reverse=True)[:20]

    metrics: list[dict[str, Any]] = []
    for path in sorted(selected):
        summary = parse_summary(path)
        if summary is None:
            continue
        metrics.append(
            {
                "metric": normalize_metric_name(path.relative_to(target_dir)),
                "value": summary,
            }
        )

    total = sum(item["value"] for item in metrics)
    return {"total": total, "metrics": metrics}


def run_command(command: str, cwd: pathlib.Path, target_dir: pathlib.Path) -> dict[str, Any]:
    before = {str(path) for path in scan_callgrind_files(target_dir)}
    start_ns = time.time_ns()
    env = os.environ.copy()
    env["CARGO_TARGET_DIR"] = str(target_dir)

    subprocess.run(command, shell=True, cwd=cwd, check=True, env=env)
    return collect_metrics(target_dir, start_ns, before)


def git_checkout(repo_path: pathlib.Path, ref: str) -> None:
    subprocess.run(["git", "checkout", "--force", ref], cwd=repo_path, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--working-directory", default=".")
    parser.add_argument("--benchmark-name", required=True)
    parser.add_argument("--feature-name", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    repo_path = pathlib.Path(args.repo_path).resolve()
    workdir = (repo_path / args.working_directory).resolve()
    if not workdir.exists():
        raise FileNotFoundError(f"working directory does not exist: {workdir}")

    case_slug = f"{args.benchmark_name}-{args.feature_name}".replace(" ", "-")
    head_target = repo_path / ".iai-target" / case_slug / "head"
    base_target = repo_path / ".iai-target" / case_slug / "base"
    head_target.mkdir(parents=True, exist_ok=True)
    base_target.mkdir(parents=True, exist_ok=True)

    git_checkout(repo_path, args.head_sha)
    head = run_command(args.command, workdir, head_target)

    git_checkout(repo_path, args.base_sha)
    base = run_command(args.command, workdir, base_target)

    git_checkout(repo_path, args.head_sha)

    base_total = base["total"]
    head_total = head["total"]
    delta = head_total - base_total
    delta_pct = ((delta / base_total) * 100.0) if base_total else 0.0

    result = {
        "benchmark_name": args.benchmark_name,
        "feature_name": args.feature_name,
        "command": args.command,
        "base_total": base_total,
        "head_total": head_total,
        "delta": delta,
        "delta_pct": delta_pct,
        "head_metrics": head["metrics"],
        "base_metrics": base["metrics"],
    }

    pathlib.Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
