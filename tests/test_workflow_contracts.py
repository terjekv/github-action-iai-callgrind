import unittest

from testlib import REPO_ROOT


def extract_job_block(workflow_text: str, job_name: str) -> str:
    lines = workflow_text.splitlines()
    in_jobs = False
    collecting = False
    block: list[str] = []

    for line in lines:
        if not in_jobs:
            if line == "jobs:":
                in_jobs = True
            continue

        if not collecting:
            if line == f"  {job_name}:":
                collecting = True
                block.append(line)
            continue

        if line.startswith("  ") and not line.startswith("    "):
            break
        block.append(line)

    if not block:
        raise AssertionError(f"job '{job_name}' not found")
    return "\n".join(block)


class WorkflowContractTests(unittest.TestCase):
    def test_report_job_directly_depends_on_prepare_matrix(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "rust-pr-bench.yml").read_text(
            encoding="utf-8"
        )
        report_block = extract_job_block(workflow, "report")

        self.assertIn("    needs:", report_block)
        self.assertIn("      - prepare-matrix", report_block)
        self.assertIn("      - benchmark", report_block)
        self.assertIn("    if: always() && needs.prepare-matrix.result == 'success'", report_block)

    def test_workflow_wires_moved_benchmark_detection(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "rust-pr-bench.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("auto_detect_moved_benchmarks:", workflow)
        self.assertIn("--auto-detect-moved-benchmarks", workflow)
        self.assertIn("--head-command", workflow)
        self.assertIn("--base-command", workflow)
        self.assertIn("if: always()", workflow)

    def test_workflow_precompiles_then_fans_out_benchmarks(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "rust-pr-bench.yml").read_text(
            encoding="utf-8"
        )
        precompile_block = extract_job_block(workflow, "precompile")
        benchmark_block = extract_job_block(workflow, "benchmark")

        self.assertIn("scripts/precompile_benchmarks.py", precompile_block)
        self.assertIn("--target-dir", precompile_block)
        self.assertIn("actions/upload-artifact@v7", precompile_block)
        self.assertIn("      - precompile", benchmark_block)
        self.assertIn("actions/download-artifact@v8", benchmark_block)
        self.assertIn("HEAD_BINARY", benchmark_block)
        self.assertIn("${HEAD_RUN_ARGS:+ $HEAD_RUN_ARGS}", benchmark_block)
        self.assertIn("RUST_SYSROOT=", benchmark_block)
        self.assertIn("${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}", benchmark_block)

    def test_binary_artifacts_are_separate_from_report_inputs(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "rust-pr-bench.yml").read_text(
            encoding="utf-8"
        )
        precompile_block = extract_job_block(workflow, "precompile")
        benchmark_block = extract_job_block(workflow, "benchmark")
        report_block = extract_job_block(workflow, "report")

        self.assertIn("binary_artifact_prefix", workflow)
        self.assertIn("binary_artifact_prefix", precompile_block)
        self.assertIn("binary_artifact_prefix", benchmark_block)
        self.assertNotIn("binary_artifact_prefix", report_block)
        self.assertIn(
            "pattern: ${{ needs.prepare-matrix.outputs.artifact_prefix }}-*", report_block
        )

    def test_workflow_wires_label_approved_regression_exceptions(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "rust-pr-bench.yml").read_text(
            encoding="utf-8"
        )
        report_block = extract_job_block(workflow, "report")

        self.assertIn("regression_override_label:", workflow)
        self.assertIn("default: \"\"", workflow)
        self.assertIn("loadPullRequestMetadata", report_block)
        self.assertIn("scripts/regression_overrides.py", report_block)
        self.assertEqual(report_block.count("--regression-overrides-input"), 2)
        self.assertIn("has_unaccepted_regressions:", workflow)
        self.assertIn(
            "inputs.fail_on_regression && steps.render_overall.outputs.has_unaccepted_regressions == 'true'",
            report_block,
        )
        self.assertIn(
            "inputs.comment_mode == 'on-regression' && steps.render_overall.outputs.has_regressions == 'true'",
            report_block,
        )

    def test_compatibility_wrapper_forwards_regression_exception_interface(self) -> None:
        wrapper = (
            REPO_ROOT / ".github" / "workflows" / "iai-callgrind-pr-bench.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("regression_override_label:", wrapper)
        self.assertIn(
            "regression_override_label: ${{ inputs.regression_override_label }}", wrapper
        )
        self.assertIn("has_regressions:", wrapper)
        self.assertIn("has_unaccepted_regressions:", wrapper)

    def test_sample_workflow_exercises_enabled_exception_setting_and_outputs(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "sample-self-test.yml").read_text(
            encoding="utf-8"
        )
        bench_block = extract_job_block(workflow, "bench-sample-autodiscover-callgrind")
        output_block = extract_job_block(workflow, "check-regression-outputs")

        self.assertIn(
            "regression_override_label: rust-pr-bench-self-test-approval", bench_block
        )
        self.assertIn(
            "action_repository: ${{ github.event.pull_request.head.repo.full_name }}", bench_block
        )
        self.assertIn("action_ref: ${{ github.event.pull_request.head.sha }}", bench_block)
        self.assertIn("fail_on_regression: true", bench_block)
        self.assertIn("outputs.has_regressions", output_block)
        self.assertIn("outputs.has_unaccepted_regressions", output_block)

    def test_release_workflow_publishes_on_version_tags(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("name: Release", workflow)
        self.assertIn("  push:", workflow)
        self.assertIn('      - "v*.*.*"', workflow)
        self.assertIn("  contents: write", workflow)
        self.assertIn("uses: softprops/action-gh-release@v3", workflow)
        self.assertIn('version = os.environ["TAG_NAME"].removeprefix("v")', workflow)


if __name__ == "__main__":
    unittest.main()
