#!/usr/bin/env python3
import argparse
import json
import math
import pathlib
from collections import defaultdict
from typing import Any


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


def metric_delta(base_value: int, head_value: int) -> float:
    if base_value == 0:
        return 0.0 if head_value == 0 else float("inf")
    return ((head_value - base_value) / base_value) * 100.0


def render_metric_breakdown(entry: dict[str, Any], threshold: float) -> list[str]:
    lines: list[str] = []
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


def render_markdown(results: list[dict[str, Any]], threshold: float) -> tuple[str, bool]:
    if not results:
        return ("## IAI-Callgrind Benchmark Report\n\nNo benchmark results were found.", False)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        grouped[item["feature_name"]].append(item)

    has_regressions = False
    lines: list[str] = []
    lines.append("## IAI-Callgrind Benchmark Report")
    lines.append("")
    lines.append(f"Regression threshold: **{threshold:.2f}%**")
    lines.append("")
    lines.append("| Feature Set | Improved | Regressions | Neutral |")
    lines.append("| --- | ---: | ---: | ---: |")

    feature_sections: list[str] = []

    for feature_name in sorted(grouped.keys()):
        improved = 0
        regressions = 0
        neutral = 0
        section_lines: list[str] = []

        section_lines.append(f"<details><summary><strong>{feature_name}</strong></summary>")
        section_lines.append("")
        section_lines.append("| Benchmark | Base | Head | Delta | Status |")
        section_lines.append("| --- | ---: | ---: | ---: | --- |")

        sorted_entries = sorted(grouped[feature_name], key=lambda e: e["benchmark_name"])
        for entry in sorted_entries:
            status, is_regression = classify(entry["delta_pct"], threshold)
            if is_regression:
                regressions += 1
                has_regressions = True
            elif status.startswith("🟢"):
                improved += 1
            else:
                neutral += 1

            section_lines.append(
                "| {bench} | {base} | {head} | {delta} | {status} |".format(
                    bench=entry["benchmark_name"],
                    base=fmt_int(int(entry["base_total"])),
                    head=fmt_int(int(entry["head_total"])),
                    delta=fmt_pct(float(entry["delta_pct"])),
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

        lines.append(f"| {feature_name} | {improved} | {regressions} | {neutral} |")
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

    return ("\n".join(lines), has_regressions)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-dir", required=True)
    parser.add_argument("--threshold", required=True, type=float)
    parser.add_argument("--markdown-output", required=True)
    parser.add_argument("--summary-output", required=True)
    args = parser.parse_args()

    results = load_results(pathlib.Path(args.artifacts_dir))
    markdown, has_regressions = render_markdown(results, args.threshold)

    pathlib.Path(args.markdown_output).write_text(markdown, encoding="utf-8")
    pathlib.Path(args.summary_output).write_text(
        json.dumps({"has_regressions": has_regressions, "count": len(results)}),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
