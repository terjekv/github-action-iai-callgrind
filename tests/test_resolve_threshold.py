import subprocess
import unittest

from testlib import REPO_ROOT, load_script_module


resolve_threshold = load_script_module(
    "resolve_threshold", "scripts/resolve_threshold.py"
)


class ResolveThresholdTests(unittest.TestCase):
    def test_precedence_is_new_then_old_then_generic(self) -> None:
        resolve = resolve_threshold.resolve_callgrind_threshold
        self.assertEqual(resolve(3), 3)
        self.assertEqual(resolve(3, iai_callgrind_specific=4), 4)
        self.assertEqual(resolve(3, gungraun_specific=5), 5)
        self.assertEqual(resolve(3, gungraun_specific=6, iai_callgrind_specific=6), 6)

    def test_conflicting_specific_names_fail_clearly(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "conflicting Callgrind thresholds.*regression_threshold_pct_gungraun",
        ):
            resolve_threshold.resolve_callgrind_threshold(3, 4, 5)

    def test_cli_rejects_conflicts(self) -> None:
        completed = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "resolve_threshold.py"),
                "--generic=3",
                "--gungraun=4",
                "--iai-callgrind=5",
            ],
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("conflicting Callgrind thresholds", completed.stderr)

    def test_generic_threshold_cannot_use_specific_input_sentinel(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "regression_threshold_pct must be non-negative",
        ):
            resolve_threshold.resolve_callgrind_threshold(-1)


if __name__ == "__main__":
    unittest.main()
