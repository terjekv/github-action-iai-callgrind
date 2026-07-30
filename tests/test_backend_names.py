import subprocess
import unittest

from testlib import REPO_ROOT, load_script_module


backend_names = load_script_module("backend_names", "scripts/backend_names.py")


class BackendNamesTests(unittest.TestCase):
    def test_v2_normalizes_new_and_legacy_names_to_stable_wire_value(self) -> None:
        for alias in ("gungraun", "iai-callgrind", "iai", "callgrind"):
            with self.subTest(alias=alias):
                self.assertEqual(
                    backend_names.normalize_backend(alias),
                    "iai-callgrind",
                )

    def test_selection_cli_accepts_gungraun(self) -> None:
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
        self.assertEqual(completed.stdout.strip(), "iai-callgrind")

    def test_unknown_backend_is_actionable(self) -> None:
        with self.assertRaisesRegex(ValueError, "gungraun.*iai-callgrind.*criterion"):
            backend_names.normalize_backend("perf")


if __name__ == "__main__":
    unittest.main()
