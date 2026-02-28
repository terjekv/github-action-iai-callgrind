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

`terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v2`

Compatibility path (deprecated but supported):
`terjekv/github-action-iai-callgrind/.github/workflows/iai-callgrind-pr-bench.yml@v2`

### Example caller workflows

Most consumers will use one of these patterns at a time.

#### 1. Run both backends in one job

Best when you want one consolidated PR comment and one benchmark status check.

```yaml
name: PR Bench

on:
  pull_request:

jobs:
  bench:
    uses: terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v2
    with:
      backend: all
      auto_discover: true
      criterion_statistic: median
      feature_sets_json: >-
        [
          {"name":"default","features":""},
          {"name":"simd","features":"simd"}
        ]
      regression_threshold_pct_iai_callgrind: 3
      regression_threshold_pct_criterion: 10
      fail_on_regression: true
```

#### 2. Criterion only, with tuned sampling

Best when wall-clock benchmarking is what you care about and you want to tune Criterion's CLI settings.

```yaml
name: Criterion Bench

on:
  pull_request:

jobs:
  bench:
    uses: terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v2
    with:
      backend: criterion
      auto_discover: true
      criterion_cli_args: "--noplot --sample-size 80 --measurement-time 6"
      criterion_statistic: median
      regression_threshold_pct_criterion: 10
      fail_on_regression: true
```

#### 3. Callgrind only, for instruction-level regression gating

Best when you want stricter deterministic gating on callgrind event counts.

```yaml
name: Callgrind Bench

on:
  pull_request:

jobs:
  bench:
    uses: terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v2
    with:
      backend: iai-callgrind
      auto_discover: true
      feature_sets_json: >-
        [
          {"name":"default","features":""},
          {"name":"simd","features":"simd"}
        ]
      regression_threshold_pct_iai_callgrind: 3
      fail_on_regression: true
```

#### 4. Explicit benchmark list for a workspace member or mixed setup

Best when autodiscovery is not enough, or when each backend should target a different bench binary.

```yaml
name: Explicit Bench Setup

on:
  pull_request:

jobs:
  bench:
    uses: terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v2
    with:
      backend: all
      working_directory: crates/engine
      benchmarks_json: >-
        [
          {"name":"parser_callgrind","bench":"parser_callgrind","backend":"iai-callgrind"},
          {"name":"parser_criterion","bench":"parser_criterion","backend":"criterion","criterion_args":"--noplot --sample-size 50"}
        ]
      feature_sets_json: >-
        [
          {"name":"default","features":""},
          {"name":"serde","features":"serde"}
        ]
      regression_threshold_pct_criterion: 10
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
  - This action does not override Criterion's sampling defaults unless you pass additional CLI args.
- `criterion_statistic` (`mean` | `median`, default `mean`)
  - Statistic used for Criterion base-vs-head comparison deltas.
- `base_sha` (string, optional override)
- `regression_threshold_pct` (number, default `3`)
- `regression_threshold_pct_iai_callgrind` (number, default `-1`)
  - Optional backend-specific threshold override for `iai-callgrind`.
  - `-1` means "use `regression_threshold_pct`".
- `regression_threshold_pct_criterion` (number, default `-1`)
  - Optional backend-specific threshold override for `criterion`.
  - `-1` means "use `regression_threshold_pct`".
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

## Benchmark autodiscovery

When `benchmarks_json` is empty and `auto_discover: true`, the workflow scans `benches/*.rs`.

Backend routing is based on the benchmark filename:

- contains `criterion` and not `callgrind` => Criterion only
- contains `callgrind` and not `criterion` => IAI-Callgrind only
- contains neither => included for both backends

Examples:

- `parser_callgrind.rs` => IAI-Callgrind only
- `parser_criterion.rs` => Criterion only
- `parser.rs` => both backends

This lets a repo keep both benchmark styles in one `benches/` directory while still routing them predictably.

Use explicit `benchmarks_json` instead of autodiscovery when:

- the bench target names should not follow the filename convention
- different backends need different command lines
- benchmarks live outside the default `benches/` layout
- only a subset of benches should run in CI

## Notes

- Lower values are treated as better for both backends:
  - `iai-callgrind`: callgrind summary event counts
  - `criterion`: selected estimate statistic (`mean` or `median`, unit `ns`)
- With `backend: all`, the workflow posts a single consolidated PR comment with one section per backend.
- The workflow installs `valgrind` and `iai-callgrind-runner` only for `iai-callgrind`.
- Markdown layout is template-driven for easier iteration:
  - `scripts/templates/report_single.md.tmpl`
  - `scripts/templates/report_single_summary.md.tmpl`
  - `scripts/templates/report_single_history.md.tmpl`
  - `scripts/templates/report_combined.md.tmpl`
  - `scripts/templates/report_combined_backend_section.md.tmpl`
- Benchmark command overrides can use placeholders:
  - `{features}`
  - `{no_default_features_flag}`

## Criterion defaults and noise

By default, this action passes only `--noplot` to Criterion.

That means Criterion's own defaults still apply unless you override them:

- sample size: `100`
- warm-up time: `3s`
- measurement time: `5s`
- noise threshold: `1%`

On shared CI runners, seeing about `1-3%` variation on unchanged code is not unusual. If you see that level of noise, treat Criterion as a higher-variance signal than `iai-callgrind` and tune it explicitly.

Recommended ways to reduce noise:

- Prefer `criterion_statistic: median` over `mean` for PR comparisons.
- Increase `--sample-size` and `--measurement-time`.
- Raise `regression_threshold_pct_criterion` above your observed noise floor.
- Use explicit `benchmarks_json` entries with per-benchmark `criterion_args` if only some benches are noisy.
- Prefer dedicated or less contended runners if you want tighter regression gates.

Example tuned Criterion setup:

```yaml
jobs:
  bench:
    uses: terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v2
    with:
      backend: criterion
      auto_discover: true
      criterion_cli_args: "--noplot --sample-size 120 --measurement-time 8"
      criterion_statistic: median
      regression_threshold_pct_criterion: 5
      fail_on_regression: true
```

Per-benchmark overrides are also supported:

```yaml
benchmarks_json: >-
  [
    {
      "name":"parser_criterion",
      "bench":"parser_criterion",
      "backend":"criterion",
      "criterion_args":"--noplot --sample-size 200 --measurement-time 15"
    }
  ]
```

## Local fixture for CI validation

This repository includes a sample Rust project at `examples/sample-rust-app`.

- It has an `iai-callgrind` benchmark target: `sample_callgrind_bench`.
- It has a `criterion` benchmark target: `sample_criterion_bench`.
- It defines two feature sets: `default` and `alt-impl`.
- The workflow `.github/workflows/sample-self-test.yml` runs fast script/unit tests first, then validates explicit callgrind, explicit criterion, combined `backend: all`, and autodiscovery modes against the sample fixture on pull requests.
