import json
import pathlib
import shutil
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

    def test_discover_benchmarks_finds_workspace_members(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            (repo / "Cargo.toml").write_text(
                '[workspace]\nmembers = ["crates/*"]\n',
                encoding="utf-8",
            )
            for crate_name in ("alpha", "beta"):
                crate = repo / "crates" / crate_name
                (crate / "benches").mkdir(parents=True)
                (crate / "Cargo.toml").write_text(
                    f'[package]\nname = "{crate_name}"\nversion = "0.1.0"\nedition = "2021"\n',
                    encoding="utf-8",
                )
                (crate / "benches" / "shared_callgrind.rs").write_text("// bench\n", encoding="utf-8")

            discovered = expand_matrix.discover_benchmarks(repo, ".", "iai-callgrind")

            self.assertEqual(
                {(item["name"], item["manifest_path"]) for item in discovered},
                {
                    ("crates/alpha/shared_callgrind", "crates/alpha/Cargo.toml"),
                    ("crates/beta/shared_callgrind", "crates/beta/Cargo.toml"),
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

    def test_cargo_args_are_before_criterion_separator(self) -> None:
        spec = {"name": "bench_a", "bench": "bench_a"}
        feature_set = {"name": "default", "features": "", "no_default_features": False}

        command = expand_matrix.build_command(
            spec, feature_set, "--release", "criterion", "--noplot --sample-size 10"
        )

        self.assertEqual(
            command,
            "cargo bench --bench bench_a --release -- --noplot --sample-size 10",
        )

    def test_pair_moved_benchmarks_adds_base_spec_for_unique_move(self) -> None:
        head = [
            {
                "name": "crates/new/parser_callgrind",
                "bench": "parser_callgrind",
                "backend": "iai-callgrind",
                "repo_crate": "crates/new",
                "package_name": "parser",
            }
        ]
        base = [
            {
                "name": "crates/old/parser_callgrind",
                "bench": "parser_callgrind",
                "backend": "iai-callgrind",
                "repo_crate": "crates/old",
                "package_name": "parser",
                "manifest_path": "crates/old/Cargo.toml",
            }
        ]

        paired = expand_matrix.pair_moved_benchmarks(head, base)

        self.assertTrue(paired[0]["moved"])
        self.assertEqual(paired[0]["base"]["manifest_path"], "crates/old/Cargo.toml")
        self.assertEqual(paired[0]["move_source"], "crates/old")
        self.assertEqual(paired[0]["move_target"], "crates/new")

    def test_make_matrix_emits_distinct_base_command_for_move(self) -> None:
        feature_sets = [{"name": "default", "features": "", "no_default_features": False}]
        benchmarks = [
            {
                "name": "crates/new/parser_callgrind",
                "bench": "parser_callgrind",
                "backend": "iai-callgrind",
                "manifest_path": "crates/new/Cargo.toml",
                "base": {
                    "bench": "parser_callgrind",
                    "manifest_path": "crates/old/Cargo.toml",
                },
                "moved": True,
                "move_source": "crates/old",
                "move_target": "crates/new",
            }
        ]

        matrix = expand_matrix.make_matrix(benchmarks, feature_sets, "", "--noplot")
        item = matrix["include"][0]

        self.assertEqual(
            item["head_command"],
            "cargo bench --bench parser_callgrind --manifest-path crates/new/Cargo.toml",
        )
        self.assertEqual(
            item["base_command"],
            "cargo bench --bench parser_callgrind --manifest-path crates/old/Cargo.toml",
        )
        self.assertTrue(item["moved"])

    def test_cli_auto_detects_moved_workspace_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            (repo / "Cargo.toml").write_text(
                '[workspace]\nmembers = ["crates/*"]\n',
                encoding="utf-8",
            )
            old_crate = repo / "crates" / "old"
            (old_crate / "benches").mkdir(parents=True)
            (old_crate / "Cargo.toml").write_text(
                '[package]\nname = "parser"\nversion = "0.1.0"\nedition = "2021"\n',
                encoding="utf-8",
            )
            (old_crate / "benches" / "parser_callgrind.rs").write_text("// old\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "-c", "commit.gpgsign=false", "commit", "-m", "base"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            base_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()

            new_crate = repo / "crates" / "new"
            (new_crate / "benches").mkdir(parents=True)
            (new_crate / "Cargo.toml").write_text(
                '[package]\nname = "parser"\nversion = "0.1.0"\nedition = "2021"\n',
                encoding="utf-8",
            )
            (new_crate / "benches" / "parser_callgrind.rs").write_text("// new\n", encoding="utf-8")
            shutil.rmtree(old_crate)
            subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "-c", "commit.gpgsign=false", "commit", "-m", "head"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            output = repo / "matrix.json"

            subprocess.run(
                [
                    "python3",
                    str(REPO_ROOT / "scripts" / "expand_matrix.py"),
                    "--repo-path",
                    str(repo),
                    "--working-directory",
                    ".",
                    "--benchmarks-json",
                    "[]",
                    "--feature-sets-json",
                    '[{"name":"default","features":""}]',
                    "--backend",
                    "iai-callgrind",
                    "--auto-discover",
                    "--auto-detect-moved-benchmarks",
                    "--head-sha",
                    head_sha,
                    "--base-sha",
                    base_sha,
                    "--output",
                    str(output),
                ],
                check=True,
                cwd=REPO_ROOT,
            )

            item = json.loads(output.read_text(encoding="utf-8"))["include"][0]
            self.assertTrue(item["moved"])
            self.assertIn("--manifest-path crates/new/Cargo.toml", item["head_command"])
            self.assertIn("--manifest-path crates/old/Cargo.toml", item["base_command"])

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
                "cargo bench --bench sample_callgrind_bench --release -- --noplot --sample-size 30",
            )


if __name__ == "__main__":
    unittest.main()
