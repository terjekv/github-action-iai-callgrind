import subprocess
import unittest

from testlib import REPO_ROOT, load_script_module


deprecation_warnings = load_script_module(
    "deprecation_warnings", "scripts/deprecation_warnings.py"
)


class DeprecationWarningsTests(unittest.TestCase):
    def test_canonical_inputs_do_not_warn(self) -> None:
        self.assertEqual(
            deprecation_warnings.collect_deprecations(
                "gungraun",
                '[{"backend":"gungraun"}]',
                -1,
            ),
            [],
        )

    def test_legacy_backend_specs_and_threshold_are_aggregated(self) -> None:
        warnings = deprecation_warnings.collect_deprecations(
            "iai-callgrind",
            '[{"backend":"callgrind"},{"base":{"backend":"iai"}}]',
            4,
        )

        self.assertEqual(len(warnings), 2)
        self.assertIn("callgrind, iai, iai-callgrind", warnings[0])
        self.assertIn("regression_threshold_pct_iai_callgrind", warnings[1])

    def test_cli_emits_one_github_warning(self) -> None:
        completed = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "deprecation_warnings.py"),
                "--backend",
                "iai",
                "--benchmarks-json",
                '[{"backend":"iai-callgrind"}]',
                "--iai-callgrind-threshold",
                "3",
            ],
            check=True,
            text=True,
            capture_output=True,
        )

        lines = completed.stdout.strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("::warning title=Rust PR Bench v3 deprecation::"))
        self.assertIn("will not be removed before v4", lines[0])


if __name__ == "__main__":
    unittest.main()
