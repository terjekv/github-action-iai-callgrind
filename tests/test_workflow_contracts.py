import pathlib
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

    def test_release_workflow_publishes_on_version_tags(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("name: Release", workflow)
        self.assertIn("  push:", workflow)
        self.assertIn('      - "v*"', workflow)
        self.assertIn("  contents: write", workflow)
        self.assertIn("uses: softprops/action-gh-release@v2", workflow)
        self.assertIn('version = os.environ["TAG_NAME"].removeprefix("v")', workflow)


if __name__ == "__main__":
    unittest.main()
