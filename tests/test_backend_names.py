import os
import subprocess
import unittest

from testlib import REPO_ROOT, load_script_module


backend_names = load_script_module("backend_names", "scripts/backend_names.py")


class BackendNamesTests(unittest.TestCase):
    def test_v3_normalizes_new_and_legacy_names_to_gungraun(self) -> None:
        for alias in ("gungraun", "iai-callgrind", "iai", "callgrind"):
            with self.subTest(alias=alias):
                self.assertEqual(
                    backend_names.normalize_backend(alias),
                    "gungraun",
                )

    def test_selection_cli_emits_canonical_gungraun(self) -> None:
        completed = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "backend_names.py"),
                "--selection",
                "gungraun",
            ],
            check=True,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.stdout.strip(), "gungraun")

    def test_only_legacy_names_are_deprecated(self) -> None:
        for alias in ("iai-callgrind", "iai", "callgrind"):
            with self.subTest(alias=alias):
                self.assertTrue(backend_names.is_legacy_backend(alias))
        self.assertFalse(backend_names.is_legacy_backend("gungraun"))
        self.assertFalse(backend_names.is_legacy_backend("criterion"))

    def test_historic_github_workflow_without_v3_override_keeps_v2_wire_value(
        self,
    ) -> None:
        environment = os.environ.copy()
        environment["GITHUB_ACTIONS"] = "true"
        environment.pop("RUST_PR_BENCH_CANONICAL_BACKEND", None)

        completed = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "backend_names.py"),
                "--selection",
                "gungraun",
            ],
            check=True,
            text=True,
            capture_output=True,
            env=environment,
        )

        self.assertEqual(completed.stdout.strip(), "iai-callgrind")

    def test_unknown_backend_is_actionable(self) -> None:
        with self.assertRaisesRegex(ValueError, "gungraun.*criterion.*iai-callgrind"):
            backend_names.normalize_backend("perf")


if __name__ == "__main__":
    unittest.main()
