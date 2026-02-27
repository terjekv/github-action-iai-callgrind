# github-action-iai-callgrind

Reusable GitHub workflow for benchmarking Rust PRs with `iai-callgrind`, `criterion`, or both (`backend: all`), and posting base-vs-head reports.

## What this provides

- Runs configured benchmark targets for a matrix of feature sets.
- Supports `iai-callgrind`, `criterion`, or `all` via the `backend` input.
- Compares `head` (`github.sha`) against PR base (`pull_request.base.sha`) in the same matrix job.
- Publishes a sticky PR comment with grouped markdown tables and per-benchmark metric breakdowns.
- Optionally fails CI when regressions exceed a threshold.

## Reusable workflow

Use:

`your-org/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v1`

Compatibility path (deprecated but supported):
`your-org/github-action-iai-callgrind/.github/workflows/iai-callgrind-pr-bench.yml@v1`

### Example caller workflow

```yaml
name: PR Bench

on:
  pull_request:

jobs:
  bench-callgrind:
    uses: your-org/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v1
    with:
      backend: iai-callgrind
      auto_discover: true
      feature_sets_json: >-
        [
          {"name":"default","features":""},
          {"name":"simd","features":"simd"}
        ]
      regression_threshold_pct: 3
      fail_on_regression: true

  bench-criterion:
    uses: your-org/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v1
    with:
      backend: criterion
      auto_discover: true
      criterion_cli_args: "--noplot --sample-size 80 --measurement-time 6"
      criterion_statistic: median
      regression_threshold_pct: 10
      fail_on_regression: false

  bench-all:
    uses: your-org/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v1
    with:
      backend: all
      auto_discover: true
      criterion_statistic: median
```

## Inputs

- `backend` (`iai-callgrind` | `criterion` | `all`, default `iai-callgrind`)
  - Selects benchmark backend(s) and reporting mode.
- `benchmarks_json` (string, default `[]`)
  - JSON array of benchmark specs.
  - String entry means bench target name, e.g. `"parser_bench"`.
  - Object entry supports:
    - `name`: display name
    - `bench`: cargo bench target name (for `cargo bench --bench ...` mode)
    - `command`: full command override
    - `manifest_path`, `package`, `args`: optional command helpers
    - `backend`: optional (`iai-callgrind` or `criterion`) to include spec only for one backend
    - `criterion_args`: optional Criterion bench-binary args for this benchmark
- `auto_discover` (boolean, default `true`)
  - When `benchmarks_json` is empty, discovers benchmarks from `benches/*.rs`.
  - Name-based backend routing for discovery:
    - contains `criterion` (and not `callgrind`) => Criterion only
    - contains `callgrind` (and not `criterion`) => IAI-Callgrind only
    - otherwise => included for both backends
- `feature_sets_json` (string)
  - JSON array of feature-set objects: `name`, `features`, `no_default_features`.
- `working_directory` (string, default `.`)
- `toolchain` (string, default `stable`)
- `cargo_args` (string, appended to all commands)
- `criterion_cli_args` (string, default `--noplot`)
  - Added after `--` for default Criterion commands.
- `criterion_statistic` (`mean` | `median`, default `mean`)
  - Statistic used for Criterion base-vs-head comparison deltas.
- `base_sha` (string, optional override)
- `regression_threshold_pct` (number, default `3`)
- `fail_on_regression` (boolean, default `false`)
- `comment_mode` (`always` | `on-regression` | `never`, default `always`)
- `action_repository` (string, default `terjekv/github-action-iai-callgrind`)
  - Repository containing this reusable workflow and its scripts.
- `action_ref` (string, default empty)
  - Ref (sha/tag/branch) for `action_repository`. Required when `action_repository` is not the default.

## Benchmark location

By default, benchmarks are expected in Rust's standard `benches/` folder.

You can override this by either:

- Setting `working_directory` for workspace/member layouts.
- Providing explicit `benchmarks_json` entries.
- Using `command` in a benchmark spec for custom invocation.

## Notes

- Lower values are treated as better for both backends:
  - `iai-callgrind`: callgrind summary event counts
  - `criterion`: selected estimate statistic (`mean` or `median`, unit `ns`)
- With `backend: all`, the workflow posts a single consolidated PR comment with one section per backend.
- The workflow installs `valgrind` and `iai-callgrind-runner` only for `iai-callgrind`.
- Benchmark command overrides can use placeholders:
  - `{features}`
  - `{no_default_features_flag}`

## Local fixture for CI validation

This repository includes a sample Rust project at `examples/sample-rust-app`.

- It has an `iai-callgrind` benchmark target: `sample_bench`.
- It has a `criterion` benchmark target: `sample_criterion_bench`.
- It defines two feature sets: `default` and `alt-impl`.
- The workflow `.github/workflows/sample-self-test.yml` first runs clippy, then calls the reusable workflow in `backend: all` mode to validate both backends end-to-end on pull requests.
