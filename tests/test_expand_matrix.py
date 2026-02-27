import json
import pathlib
import subprocess
import tempfile
import unittest

from testlib import REPO_ROOT, load_script_module


expand_matrix = load_script_module("expand_matrix", "scripts/expand_matrix.py")


class ExpandMatrixTests(unittest.TestCase):
    def test_normalize_backend_selection_accepts_any(self) -> None:
        self.assertEqual(expand_matrix.normalize_backend_selection("any"), "all")
        self.assertEqual(expand_matrix.normalize_backend_selection("all"), "all")

    def test_discover_benchmarks_routes_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            benches = repo / "crate" / "benches"
            benches.mkdir(parents=True)
            (benches / "alpha_callgrind.rs").write_text("// callgrind\n", encoding="utf-8")
            (benches / "beta_criterion.rs").write_text("// criterion\n", encoding="utf-8")
            (benches / "shared.rs").write_text("// both\n", encoding="utf-8")

            discovered = expand_matrix.discover_benchmarks(repo, "crate", "all")
            pairs = {(item["name"], item["backend"]) for item in discovered}

            self.assertEqual(
                pairs,
                {
                    ("alpha_callgrind", "iai-callgrind"),
                    ("beta_criterion", "criterion"),
                    ("shared", "iai-callgrind"),
                    ("shared", "criterion"),
                },
            )

    def test_build_command_appends_criterion_args_only_for_criterion(self) -> None:
        spec = {"name": "bench_a", "bench": "bench_a"}
        feature_set = {"name": "default", "features": "", "no_default_features": False}

        callgrind_command = expand_matrix.build_command(
            spec, feature_set, "", "iai-callgrind", "--noplot --sample-size 10"
        )
        criterion_command = expand_matrix.build_command(
            spec, feature_set, "", "criterion", "--noplot --sample-size 10"
        )

        self.assertEqual(callgrind_command, "cargo bench --bench bench_a")
        self.assertEqual(
            criterion_command,
            "cargo bench --bench bench_a -- --noplot --sample-size 10",
        )

    def test_command_placeholders_expand_feature_flags(self) -> None:
        spec = {"command": "cargo bench {features} {no_default_features_flag}"}
        feature_set = {"name": "feat", "features": "simd", "no_default_features": True}

        command = expand_matrix.build_command(spec, feature_set, "", "iai-callgrind", "--noplot")

        self.assertEqual(command, "cargo bench simd --no-default-features")

    def test_cli_accepts_dash_prefixed_argument_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "matrix.json"
            subprocess.run(
                [
                    "python3",
                    str(REPO_ROOT / "scripts" / "expand_matrix.py"),
                    "--repo-path",
                    str(REPO_ROOT),
                    "--working-directory",
                    "examples/sample-rust-app",
                    "--benchmarks-json",
                    '["sample_callgrind_bench"]',
                    "--feature-sets-json",
                    '[{"name":"default","features":""}]',
                    "--backend",
                    "criterion",
                    "--criterion-cli-args",
                    "--noplot --sample-size 30",
                    "--cargo-args",
                    "--release",
                    "--output",
                    str(output),
                ],
                check=True,
                cwd=REPO_ROOT,
            )

            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["include"]), 1)
            self.assertEqual(
                payload["include"][0]["command"],
                "cargo bench --bench sample_callgrind_bench -- --noplot --sample-size 30 --release",
            )


if __name__ == "__main__":
    unittest.main()
