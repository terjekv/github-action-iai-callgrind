#!/usr/bin/env python3
import argparse
import json
import os
import pathlib
import re
import shlex
import subprocess
import time
from typing import Any


def normalize_backend(raw: str) -> str:
    value = raw.strip().lower()
    if value in {"iai", "iai-callgrind", "callgrind"}:
        return "iai-callgrind"
    if value in {"criterion"}:
        return "criterion"
    raise ValueError(f"unsupported backend '{raw}' (expected 'iai-callgrind' or 'criterion')")


def parse_callgrind_summary(path: pathlib.Path) -> int | None:
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


def normalize_callgrind_metric_name(path: pathlib.Path) -> str:
    # callgrind filenames can include run-specific numeric suffixes (for example PID).
    # Strip trailing ".<digits>" to make base/head metric keys comparable.
    normalized = re.sub(r"\.\d+$", "", path.as_posix())
    return normalized


def scan_criterion_estimate_files(target_dir: pathlib.Path) -> list[pathlib.Path]:
    criterion_dir = target_dir / "criterion"
    if not criterion_dir.exists():
        return []

    candidates: list[pathlib.Path] = []
    for path in criterion_dir.rglob("estimates.json"):
        if path.is_file():
            candidates.append(path)
    return candidates


def criterion_metric_name(path: pathlib.Path, target_dir: pathlib.Path) -> str:
    rel = path.relative_to(target_dir / "criterion")
    parts = list(rel.parts)
    if parts and parts[-1] == "estimates.json":
        parts = parts[:-1]
    if parts and parts[-1] in {"new", "base"}:
        parts = parts[:-1]
    return "/".join(parts) if parts else rel.as_posix()


def parse_criterion_estimate(path: pathlib.Path, statistic: str) -> dict[str, float] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    metric = data.get(statistic)
    if not isinstance(metric, dict):
        return None

    point = metric.get("point_estimate")
    if point is None:
        return None

    try:
        value = float(point)
    except (TypeError, ValueError):
        return None

    conf = metric.get("confidence_interval")
    lower: float | None = None
    upper: float | None = None
    if isinstance(conf, dict):
        low = conf.get("lower_bound")
        high = conf.get("upper_bound")
        try:
            lower = float(low) if low is not None else None
        except (TypeError, ValueError):
            lower = None
        try:
            upper = float(high) if high is not None else None
        except (TypeError, ValueError):
            upper = None

    payload: dict[str, float] = {"value": value}
    if lower is not None:
        payload["lower"] = lower
    if upper is not None:
        payload["upper"] = upper
    return payload


def select_recent_files(
    files: list[pathlib.Path], start_ns: int, before_paths: set[str], fallback_limit: int
) -> list[pathlib.Path]:
    selected: list[pathlib.Path] = []
    for path in files:
        stat = path.stat()
        if str(path) not in before_paths or stat.st_mtime_ns >= start_ns:
            selected.append(path)
    if not selected:
        selected = sorted(files, key=lambda p: p.stat().st_mtime_ns, reverse=True)[:fallback_limit]
    return selected


def collect_callgrind_metrics(
    target_dir: pathlib.Path, start_ns: int, before_paths: set[str]
) -> dict[str, Any]:
    files = scan_callgrind_files(target_dir)
    selected = select_recent_files(files, start_ns, before_paths, fallback_limit=20)

    metrics: list[dict[str, Any]] = []
    for path in sorted(selected):
        summary = parse_callgrind_summary(path)
        if summary is None:
            continue
        metrics.append(
            {
                "metric": normalize_callgrind_metric_name(path.relative_to(target_dir)),
                "value": summary,
            }
        )

    if not metrics:
        return {"total": 0, "metrics": [], "missing": True, "missing_reason": "no callgrind metrics found"}

    total = sum(item["value"] for item in metrics)
    return {"total": total, "metrics": metrics, "metric_unit": "events"}


def collect_criterion_metrics(
    target_dir: pathlib.Path, start_ns: int, before_paths: set[str], statistic: str
) -> dict[str, Any]:
    files = scan_criterion_estimate_files(target_dir)
    selected = select_recent_files(files, start_ns, before_paths, fallback_limit=200)

    metrics: list[dict[str, Any]] = []
    for path in sorted(selected):
        estimate = parse_criterion_estimate(path, statistic)
        if not estimate:
            continue
        metric_entry: dict[str, Any] = {
            "metric": criterion_metric_name(path, target_dir),
            "value": estimate["value"],
            "statistic": statistic,
            "unit": "ns",
        }
        if "lower" in estimate:
            metric_entry["lower"] = estimate["lower"]
        if "upper" in estimate:
            metric_entry["upper"] = estimate["upper"]
        metrics.append(metric_entry)

    if not metrics:
        return {
            "total": 0,
            "metrics": [],
            "missing": True,
            "missing_reason": "no criterion estimates found",
        }

    total = sum(float(item["value"]) for item in metrics)
    return {
        "total": total,
        "metrics": metrics,
        "metric_unit": "ns",
        "comparison_statistic": statistic,
    }


def detect_missing_bench(command: str, cwd: pathlib.Path) -> str | None:
    try:
        parts = shlex.split(command)
    except ValueError:
        return None

    if not parts or parts[0] != "cargo":
        return None
    if "bench" not in parts:
        return None
    if "--bench" not in parts:
        return None
    if "--manifest-path" in parts or "--package" in parts or "-p" in parts:
        return None

    bench_index = parts.index("--bench") + 1
    if bench_index >= len(parts):
        return None
    bench_name = parts[bench_index]
    bench_path = cwd / "benches" / f"{bench_name}.rs"
    if not bench_path.exists():
        return f"missing bench file {bench_path.as_posix()}"
    return None


def is_missing_bench_error(output: str) -> bool:
    lowered = output.lower()
    return (
        "no bench target named" in lowered
        or "could not find bench" in lowered
        or "no benchmark target named" in lowered
    )

def is_missing_feature_error(output: str) -> bool:
    lowered = output.lower()
    return (
        "does not have the feature" in lowered
        or "does not have these features" in lowered
        or "does not contain this feature" in lowered
        or "does not contain these features" in lowered
        or "unknown feature" in lowered
        or "feature `" in lowered and " is not defined" in lowered
        or "no such feature" in lowered
    )


def is_iai_version_mismatch_error(output: str) -> bool:
    lowered = output.lower()
    return "iai-callgrind-runner" in lowered and "is newer than iai-callgrind" in lowered


def run_command(
    command: str,
    cwd: pathlib.Path,
    target_dir: pathlib.Path,
    backend: str,
    criterion_statistic: str,
) -> dict[str, Any]:
    missing_reason = detect_missing_bench(command, cwd)
    if missing_reason:
        return {"total": 0, "metrics": [], "missing": True, "missing_reason": missing_reason}

    if backend == "criterion":
        before = {str(path) for path in scan_criterion_estimate_files(target_dir)}
    else:
        before = {str(path) for path in scan_callgrind_files(target_dir)}
    start_ns = time.time_ns()
    env = os.environ.copy()
    env["CARGO_TARGET_DIR"] = str(target_dir)

    try:
        subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            check=True,
            env=env,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        output = (exc.stdout or "") + "\n" + (exc.stderr or "")
        if is_missing_bench_error(output):
            return {"total": 0, "metrics": [], "missing": True, "missing_reason": "bench target not found"}
        if is_missing_feature_error(output):
            return {"total": 0, "metrics": [], "missing": True, "missing_reason": "feature not available"}
        error_reason = None
        if is_iai_version_mismatch_error(output):
            error_reason = "iai-callgrind version mismatch"
        return {
            "total": 0,
            "metrics": [],
            "error": True,
            "error_code": exc.returncode,
            "error_output": output.strip(),
            "error_reason": error_reason,
        }
    if backend == "criterion":
        return collect_criterion_metrics(target_dir, start_ns, before, criterion_statistic)
    return collect_callgrind_metrics(target_dir, start_ns, before)


def git_checkout(repo_path: pathlib.Path, ref: str) -> None:
    subprocess.run(["git", "checkout", "--force", ref], cwd=repo_path, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--working-directory", default=".")
    parser.add_argument("--benchmark-name", required=True)
    parser.add_argument("--feature-name", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--backend", default="iai-callgrind")
    parser.add_argument("--criterion-statistic", default="mean", choices=("mean", "median"))
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    backend = normalize_backend(args.backend)
    repo_path = pathlib.Path(args.repo_path).resolve()
    workdir = (repo_path / args.working_directory).resolve()
    if not workdir.exists():
        raise FileNotFoundError(f"working directory does not exist: {workdir}")

    case_slug = f"{args.benchmark_name}-{args.feature_name}".replace(" ", "-")
    head_target = repo_path / ".bench-target" / backend / case_slug / "head"
    base_target = repo_path / ".bench-target" / backend / case_slug / "base"
    head_target.mkdir(parents=True, exist_ok=True)
    base_target.mkdir(parents=True, exist_ok=True)

    git_checkout(repo_path, args.head_sha)
    head = run_command(args.command, workdir, head_target, backend, args.criterion_statistic)

    git_checkout(repo_path, args.base_sha)
    base = run_command(args.command, workdir, base_target, backend, args.criterion_statistic)

    git_checkout(repo_path, args.head_sha)

    base_total = base.get("total", 0)
    head_total = head.get("total", 0)
    if base.get("missing") or head.get("missing") or base.get("error") or head.get("error"):
        delta = 0
        delta_pct = float("nan")
    else:
        delta = head_total - base_total
        delta_pct = ((delta / base_total) * 100.0) if base_total else 0.0

    result = {
        "backend": backend,
        "benchmark_name": args.benchmark_name,
        "feature_name": args.feature_name,
        "command": args.command,
        "base_total": base_total,
        "head_total": head_total,
        "delta": delta,
        "delta_pct": delta_pct,
        "head_metrics": head["metrics"],
        "base_metrics": base["metrics"],
        "head_missing": bool(head.get("missing")),
        "base_missing": bool(base.get("missing")),
        "head_missing_reason": head.get("missing_reason"),
        "base_missing_reason": base.get("missing_reason"),
        "head_error": bool(head.get("error")),
        "base_error": bool(base.get("error")),
        "head_error_code": head.get("error_code"),
        "base_error_code": base.get("error_code"),
        "head_error_reason": head.get("error_reason"),
        "base_error_reason": base.get("error_reason"),
        "head_error_output": head.get("error_output"),
        "base_error_output": base.get("error_output"),
        "metric_unit": head.get("metric_unit") or base.get("metric_unit"),
        "comparison_statistic": head.get("comparison_statistic")
        or base.get("comparison_statistic")
        or ("mean" if backend == "criterion" else "summary"),
    }

    pathlib.Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    if head.get("error") or base.get("error"):
        output_dir = pathlib.Path(args.output).resolve().parent

        def emit_error(label: str, data: dict[str, Any]) -> None:
            if not data.get("error"):
                return
            output = data.get("error_output") or ""
            if not output:
                return
            reason = data.get("error_reason")
            if reason == "iai-callgrind version mismatch":
                print(
                    f"[{label}] error: iai-callgrind-runner is newer than the crate. "
                    "Update the repo's iai-callgrind dependency to match the runner version."
                )
            log_path = output_dir / f"{label}.error.log"
            log_path.write_text(output, encoding="utf-8")
            print(f"[{label}] command failed; full output:")
            print(output)
            print(f"[{label}] full output written to {log_path.as_posix()}")

        emit_error("head", head)
        emit_error("base", base)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
