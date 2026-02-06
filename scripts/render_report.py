#!/usr/bin/env python3
import argparse
import json
import math
import pathlib
from collections import defaultdict
from typing import Any, Iterable


def load_results(artifacts_dir: pathlib.Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path in sorted(artifacts_dir.rglob("result.json")):
        with path.open("r", encoding="utf-8") as handle:
            results.append(json.load(handle))
    return results


def classify(delta_pct: float, threshold: float) -> tuple[str, bool]:
    if math.isnan(delta_pct) or math.isinf(delta_pct):
        return ("⚪ unknown", False)
    if delta_pct > threshold:
        return ("🔴 regression", True)
    if delta_pct < -0.5:
        return ("🟢 improved", False)
    if delta_pct > 0.5:
        return ("🟡 slight regression", False)
    return ("⚪ neutral", False)


def fmt_int(value: int) -> str:
    return f"{value:,}"


def fmt_pct(value: float) -> str:
    return f"{value:+.2f}%"


def fmt_pct_or_na(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return fmt_pct(value)


def metric_delta(base_value: int, head_value: int) -> float:
    if base_value == 0:
        return 0.0 if head_value == 0 else float("inf")
    return ((head_value - base_value) / base_value) * 100.0


def avg(values: Iterable[float]) -> float | None:
    items = [value for value in values if math.isfinite(value)]
    if not items:
        return None
    return sum(items) / len(items)


def collect_metric_deltas(entry: dict[str, Any]) -> list[float]:
    base_metrics = {item["metric"]: int(item["value"]) for item in entry.get("base_metrics", [])}
    head_metrics = {item["metric"]: int(item["value"]) for item in entry.get("head_metrics", [])}
    metric_names = set(base_metrics.keys()) | set(head_metrics.keys())
    deltas: list[float] = []
    for metric_name in metric_names:
        base_value = base_metrics.get(metric_name, 0)
        head_value = head_metrics.get(metric_name, 0)
        deltas.append(metric_delta(base_value, head_value))
    return deltas


def compute_feature_summary(
    entries: list[dict[str, Any]], threshold: float
) -> tuple[int, int, int, float | None, float | None, bool]:
    improved = 0
    regressions = 0
    neutral = 0
    has_regressions = False
    bench_deltas: list[float] = []
    metric_deltas: list[float] = []

    for entry in entries:
        if entry.get("head_missing") or entry.get("base_missing"):
            continue
        status, is_regression = classify(entry["delta_pct"], threshold)
        if is_regression:
            regressions += 1
            has_regressions = True
        elif status.startswith("🟢"):
            improved += 1
        else:
            neutral += 1
        bench_deltas.append(float(entry["delta_pct"]))
        metric_deltas.extend(collect_metric_deltas(entry))

    return (
        improved,
        regressions,
        neutral,
        avg(bench_deltas),
        avg(metric_deltas),
        has_regressions,
    )


def render_metric_breakdown(entry: dict[str, Any], threshold: float) -> list[str]:
    lines: list[str] = []
    if entry.get("head_missing") or entry.get("base_missing"):
        reasons = []
        if entry.get("head_missing"):
            reasons.append("head missing")
        if entry.get("base_missing"):
            reasons.append("base missing")
        reason_text = " and ".join(reasons) if reasons else "missing"
        lines.append(
            f"<details><summary>{entry['benchmark_name']} metric breakdown (missing)</summary>"
        )
        lines.append("")
        lines.append(f"Skipped metric breakdown ({reason_text}).")
        lines.append("")
        lines.append("</details>")
        return lines

    base_metrics = {item["metric"]: int(item["value"]) for item in entry.get("base_metrics", [])}
    head_metrics = {item["metric"]: int(item["value"]) for item in entry.get("head_metrics", [])}
    metric_names = sorted(set(base_metrics.keys()) | set(head_metrics.keys()))

    lines.append(
        f"<details><summary>{entry['benchmark_name']} metric breakdown ({len(metric_names)} metrics)</summary>"
    )
    lines.append("")
    lines.append("| Metric | Base | Head | Delta | Status |")
    lines.append("| --- | ---: | ---: | ---: | --- |")
    for metric_name in metric_names:
        base_value = base_metrics.get(metric_name, 0)
        head_value = head_metrics.get(metric_name, 0)
        delta_pct = metric_delta(base_value, head_value)
        status, _ = classify(delta_pct, threshold)
        lines.append(
            "| {metric} | {base} | {head} | {delta} | {status} |".format(
                metric=metric_name,
                base=fmt_int(base_value),
                head=fmt_int(head_value),
                delta=fmt_pct(delta_pct) if math.isfinite(delta_pct) else "n/a",
                status=status if math.isfinite(delta_pct) else "⚪ unknown",
            )
        )
    lines.append("")
    lines.append("</details>")
    return lines


def render_markdown(
    results: list[dict[str, Any]],
    threshold: float,
    pr_number: int | None,
    head_sha: str | None,
    run_at: str | None,
    history: list[dict[str, Any]],
    max_history: int,
) -> tuple[str, dict[str, Any]]:
    if not results:
        return (
            "## IAI-Callgrind Benchmark Report\n\nNo benchmark results were found.",
            {"has_regressions": False, "count": 0, "latest": {}, "history": history},
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        grouped[item["feature_name"]].append(item)

    has_regressions = False
    lines: list[str] = []
    lines.append("## IAI-Callgrind Benchmark Report")
    lines.append("")
    lines.append(f"Regression threshold: **{threshold:.2f}%**")
    if pr_number is not None or run_at or head_sha:
        pr_part = f"PR: #{pr_number}" if pr_number is not None else "PR: n/a"
        run_part = f"Latest: {run_at}" if run_at else "Latest: n/a"
        head_part = f"Head: {head_sha[:7]}" if head_sha else "Head: n/a"
        lines.append(f"{pr_part} • {run_part} • {head_part}")
    lines.append("")
    summary_suffix = f" • {head_sha[:7]}" if head_sha else ""
    lines.append(f"## Summary (Latest Run{summary_suffix})")
    lines.append("")
    lines.append("| Feature Set | Improved | Regressions | Neutral | Avg Δ (bench) | Avg Δ (metrics) |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")

    feature_sections: list[str] = []
    total_improved = 0
    total_regressions = 0
    total_neutral = 0
    all_bench_deltas: list[float] = []
    all_metric_deltas: list[float] = []

    for feature_name in sorted(grouped.keys()):
        (
            improved,
            regressions,
            neutral,
            avg_bench_delta,
            avg_metric_delta,
            feature_has_regressions,
        ) = compute_feature_summary(grouped[feature_name], threshold)
        if feature_has_regressions:
            has_regressions = True
        total_improved += improved
        total_regressions += regressions
        total_neutral += neutral
        for entry in grouped[feature_name]:
            if entry.get("head_missing") or entry.get("base_missing"):
                continue
            all_bench_deltas.append(float(entry["delta_pct"]))
            all_metric_deltas.extend(collect_metric_deltas(entry))
        section_lines: list[str] = []

        section_lines.append(f"<details><summary><strong>{feature_name}</strong></summary>")
        section_lines.append("")
        section_lines.append("| Benchmark | Base | Head | Delta | Status |")
        section_lines.append("| --- | ---: | ---: | ---: | --- |")

        sorted_entries = sorted(grouped[feature_name], key=lambda e: e["benchmark_name"])
        for entry in sorted_entries:
            if entry.get("head_missing") or entry.get("base_missing"):
                status = "⚪ missing"
            else:
                status, _ = classify(entry["delta_pct"], threshold)
            section_lines.append(
                "| {bench} | {base} | {head} | {delta} | {status} |".format(
                    bench=entry["benchmark_name"],
                    base=fmt_int(int(entry["base_total"])),
                    head=fmt_int(int(entry["head_total"])),
                    delta=fmt_pct_or_na(float(entry["delta_pct"])),
                    status=status,
                )
            )

        section_lines.append("")
        section_lines.append("Metric-level breakdowns:")
        section_lines.append("")
        for entry in sorted_entries:
            section_lines.extend(render_metric_breakdown(entry, threshold))
            section_lines.append("")

        section_lines.append("")
        section_lines.append("</details>")

        lines.append(
            "| {feature} | {improved} | {regressions} | {neutral} | {bench_avg} | {metric_avg} |".format(
                feature=feature_name,
                improved=improved,
                regressions=regressions,
                neutral=neutral,
                bench_avg=fmt_pct_or_na(avg_bench_delta),
                metric_avg=fmt_pct_or_na(avg_metric_delta),
            )
        )
        feature_sections.extend(section_lines)

    lines.append("")
    lines.extend(feature_sections)

    if has_regressions:
        lines.append("")
        lines.append("### Regressions Above Threshold")
        lines.append("")
        for entry in sorted(results, key=lambda e: e["delta_pct"], reverse=True):
            _, is_regression = classify(entry["delta_pct"], threshold)
            if not is_regression:
                continue
            lines.append(
                "- `{feature}` / `{bench}`: {delta}".format(
                    feature=entry["feature_name"],
                    bench=entry["benchmark_name"],
                    delta=fmt_pct(float(entry["delta_pct"])),
                )
            )

    missing_entries = [
        entry
        for entry in results
        if entry.get("head_missing") or entry.get("base_missing")
    ]
    if missing_entries:
        lines.append("")
        lines.append("### Skipped Benchmarks (Missing in Base/Head)")
        lines.append("")
        for entry in sorted(missing_entries, key=lambda e: e["benchmark_name"]):
            reasons = []
            if entry.get("head_missing"):
                reasons.append("head")
            if entry.get("base_missing"):
                reasons.append("base")
            reason_text = " & ".join(reasons) if reasons else "missing"
            lines.append(
                "- `{feature}` / `{bench}`: missing in {reason}".format(
                    feature=entry["feature_name"],
                    bench=entry["benchmark_name"],
                    reason=reason_text,
                )
            )

    avg_bench_delta_all = avg(all_bench_deltas)
    avg_metric_delta_all = avg(all_metric_deltas)
    latest_entry = {
        "commit": head_sha or "",
        "run_at": run_at or "",
        "summary": {
            "improved": total_improved,
            "regressions": total_regressions,
            "neutral": total_neutral,
        },
        "avg_bench_delta_pct": avg_bench_delta_all,
        "avg_metric_delta_pct": avg_metric_delta_all,
        "has_regressions": has_regressions,
    }

    def history_key(item: dict[str, Any]) -> str:
        commit = str(item.get("commit") or "")
        return commit

    new_history: list[dict[str, Any]] = [latest_entry]
    seen = {history_key(latest_entry)}
    for item in history:
        key = history_key(item)
        if not key or key in seen:
            continue
        new_history.append(item)
        seen.add(key)
        if len(new_history) >= max_history:
            break

    lines.append("")
    lines.append(f"## PR History (last {len(new_history)} runs)")
    lines.append("")
    lines.append("| Commit | Date (UTC) | Summary | Avg Δ (bench) | Avg Δ (metrics) | Regressions? |")
    lines.append("| --- | --- | --- | ---: | ---: | --- |")
    for item in new_history:
        summary = item.get("summary", {})
        summary_text = "{improved} improved / {regressions} reg / {neutral} neutral".format(
            improved=summary.get("improved", 0),
            regressions=summary.get("regressions", 0),
            neutral=summary.get("neutral", 0),
        )
        lines.append(
            "| {commit} | {run_at} | {summary} | {bench_avg} | {metric_avg} | {has_regressions} |".format(
                commit=(item.get("commit") or "")[:7],
                run_at=item.get("run_at") or "n/a",
                summary=summary_text,
                bench_avg=fmt_pct_or_na(item.get("avg_bench_delta_pct")),
                metric_avg=fmt_pct_or_na(item.get("avg_metric_delta_pct")),
                has_regressions="yes" if item.get("has_regressions") else "no",
            )
        )

    history_payload = json.dumps({"history": new_history}, separators=(",", ":"))
    lines.append("")
    lines.append(f"<!-- iai-callgrind-history: {history_payload} -->")

    summary_payload = {
        "has_regressions": has_regressions,
        "count": len(results),
        "latest": latest_entry,
        "history": new_history,
    }
    return ("\n".join(lines), summary_payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-dir", required=True)
    parser.add_argument("--threshold", required=True, type=float)
    parser.add_argument("--markdown-output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--history-input")
    parser.add_argument("--head-sha")
    parser.add_argument("--run-at")
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--max-history", type=int, default=10)
    args = parser.parse_args()

    results = load_results(pathlib.Path(args.artifacts_dir))
    history: list[dict[str, Any]] = []
    if args.history_input:
        history_path = pathlib.Path(args.history_input)
        if history_path.exists():
            history_data = json.loads(history_path.read_text(encoding="utf-8"))
            if isinstance(history_data, dict):
                history = history_data.get("history", [])
            elif isinstance(history_data, list):
                history = history_data

    markdown, summary_payload = render_markdown(
        results,
        args.threshold,
        args.pr_number,
        args.head_sha,
        args.run_at,
        history,
        args.max_history,
    )

    pathlib.Path(args.markdown_output).write_text(markdown, encoding="utf-8")
    pathlib.Path(args.summary_output).write_text(json.dumps(summary_payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
