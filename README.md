# github-action-iai-callgrind

Reusable GitHub workflow for benchmarking Rust PRs with `iai-callgrind` and posting a base-vs-head report.

## What this provides

- Runs configured benchmark targets for a matrix of feature sets.
- Compares `head` (`github.sha`) against PR base (`pull_request.base.sha`) in the same matrix job.
- Publishes a sticky PR comment with grouped markdown tables and per-benchmark metric breakdowns.
- Optionally fails CI when regressions exceed a threshold.

## Reusable workflow

Use:

`your-org/github-action-iai-callgrind/.github/workflows/iai-callgrind-pr-bench.yml@v1`

### Example caller workflow

```yaml
name: PR Bench

on:
  pull_request:

jobs:
  bench:
    uses: your-org/github-action-iai-callgrind/.github/workflows/iai-callgrind-pr-bench.yml@v1
    with:
      auto_discover: true
      feature_sets_json: >-
        [
          {"name":"default","features":""},
          {"name":"simd","features":"simd"}
        ]
      regression_threshold_pct: 3
      fail_on_regression: true
```

## Inputs

- `benchmarks_json` (string, default `[]`)
  - JSON array of benchmark specs.
  - String entry means bench target name, e.g. `"parser_bench"`.
  - Object entry supports:
    - `name`: display name
    - `bench`: cargo bench target name (for `cargo bench --bench ...` mode)
    - `command`: full command override
    - `manifest_path`, `package`, `args`: optional command helpers
- `auto_discover` (boolean, default `true`)
  - When `benchmarks_json` is empty, discovers benchmarks from `benches/*.rs`.
- `feature_sets_json` (string)
  - JSON array of feature-set objects: `name`, `features`, `no_default_features`.
- `working_directory` (string, default `.`)
- `toolchain` (string, default `stable`)
- `cargo_args` (string, appended to all commands)
- `base_sha` (string, optional override)
- `regression_threshold_pct` (number, default `3`)
- `fail_on_regression` (boolean, default `false`)
- `comment_mode` (`always` | `on-regression` | `never`, default `always`)

## Benchmark location

By default, benchmarks are expected in Rust's standard `benches/` folder.

You can override this by either:

- Setting `working_directory` for workspace/member layouts.
- Providing explicit `benchmarks_json` entries.
- Using `command` in a benchmark spec for custom invocation.

## Notes

- Lower `iai-callgrind` instruction counts are treated as better.
- The workflow installs `valgrind` on Ubuntu runners if missing.
- Benchmark command overrides can use placeholders:
  - `{features}`
  - `{no_default_features_flag}`

## Local fixture for CI validation

This repository includes a sample Rust project at `examples/sample-rust-app`.

- It has an `iai-callgrind` benchmark target: `sample_bench`.
- It defines two feature sets: `default` and `alt-impl`.
- The workflow `.github/workflows/sample-self-test.yml` first runs clippy, then calls the reusable workflow in this repo to validate benchmark behavior on pull requests.
