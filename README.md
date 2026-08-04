# Rust PR Bench

Rust PR Bench is a reusable GitHub workflow for benchmarking Rust pull requests with
[Gungraun](https://gungraun.github.io/gungraun/), Criterion, or both (`backend: all`),
and posting base-vs-head reports. Legacy IAI-Callgrind callers remain supported throughout v3.

The repository remains `terjekv/github-action-iai-callgrind` so existing reusable-workflow
references stay valid. The canonical workflow remains `.github/workflows/rust-pr-bench.yml`;
the old `.github/workflows/iai-callgrind-pr-bench.yml` path is a supported compatibility wrapper.
This is intentional because [GitHub Actions does not follow repository-rename redirects in
`uses:` references](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations).

Upgrading from v2? Follow the [v2 to v3 migration guide](#migrating-consumers-from-v2-to-v3),
including the staged v2.3 bridge and the machine-readable identifier changes.

## What this provides

- Runs configured benchmark targets for a matrix of feature sets.
- Supports `gungraun`, `criterion`, or `all` via the `backend` input, with deprecated
  `iai-callgrind`, `iai`, and `callgrind` aliases through v3.
- Installs the exact runner version requested by each benchmark binary, including mixed
  `iai-callgrind` base and Gungraun head comparisons.
- Compares `head` (`github.sha`) against PR base (`pull_request.base.sha`) in the same matrix job.
- Publishes a sticky PR comment with grouped markdown tables and per-benchmark metric breakdowns.
- Optionally fails CI when unaccepted regressions exceed a threshold.

## Reusable workflow

Use:

`terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v3`

Compatibility path (supported):
`terjekv/github-action-iai-callgrind/.github/workflows/iai-callgrind-pr-bench.yml@v3`

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
    uses: terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v3
    with:
      backend: all
      auto_discover: true
      criterion_statistic: median
      feature_sets_json: >-
        [
          {"name":"default","features":""},
          {"name":"simd","features":"simd"}
        ]
      regression_threshold_pct_gungraun: 3
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
    uses: terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v3
    with:
      backend: criterion
      auto_discover: true
      criterion_cli_args: "--noplot --sample-size 80 --measurement-time 6"
      criterion_statistic: median
      regression_threshold_pct_criterion: 10
      fail_on_regression: true
```

#### 3. Gungraun only, for instruction-level regression gating

Best when you want stricter deterministic gating on callgrind event counts.

```yaml
name: Gungraun Bench

on:
  pull_request:

jobs:
  bench:
    uses: terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v3
    with:
      backend: gungraun
      auto_discover: true
      feature_sets_json: >-
        [
          {"name":"default","features":""},
          {"name":"simd","features":"simd"}
        ]
      regression_threshold_pct_gungraun: 3
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
    uses: terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v3
    with:
      backend: all
      working_directory: crates/engine
      benchmarks_json: >-
        [
          {"name":"parser_gungraun","bench":"parser_callgrind","backend":"gungraun"},
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

- `backend` (`gungraun` | `criterion` | `all`, default `gungraun`)
  - Selects benchmark backend(s) and reporting mode.
  - Deprecated `iai-callgrind`, `iai`, and `callgrind` aliases normalize to `gungraun`.
    Legacy names emit one workflow warning and remain supported through every v3 release.
- `benchmarks_json` (string, default `[]`)
  - JSON array of benchmark specs.
  - String entry means bench target name, e.g. `"parser_bench"`.
  - Object entry supports:
    - `name`: display name
    - `bench`: cargo bench target name (for `cargo bench --bench ...` mode)
    - `command`: full command override
    - `manifest_path`, `package`, `args`: optional command helpers
    - `backend`: optional (`gungraun`, a legacy Callgrind alias, or `criterion`) to include
      the spec only for one backend
    - `criterion_args`: optional Criterion bench-binary args for this benchmark
    - `head_command`, `base_command`, `head`, `base`: optional per-side overrides for moved or renamed benchmarks
- `auto_discover` (boolean, default `true`)
  - When `benchmarks_json` is empty, discovers benchmarks from `benches/*.rs`.
  - At a workspace root, also discovers member `benches/*.rs` targets from workspace members.
  - Name-based backend routing for discovery:
    - contains `criterion` (and no Callgrind-family marker) => Criterion only
    - contains `gungraun`, `iai_callgrind`, or `callgrind` (and not `criterion`) =>
      Gungraun only
    - otherwise => included for both backends
- `auto_detect_moved_benchmarks` (boolean, default `false`)
  - Opt-in moved-benchmark detection for autodiscovered workspace benches.
  - Active only when `auto_discover: true` and `benchmarks_json` is empty.
  - Pairs moved benchmarks by backend and bench target name when the base candidate is unique.
  - Renamed or ambiguous benchmark targets should use explicit `benchmarks_json` mapping.
- `feature_sets_json` (string)
  - JSON array of feature-set objects: `name`, `features`, `no_default_features`.
- `working_directory` (string, default `.`)
- `toolchain` (string, default `stable`)
- `cargo_args` (string, appended to Cargo commands before Criterion's `--` separator)
- `criterion_cli_args` (string, default `--noplot`)
  - Added after `--` for default Criterion commands.
  - This action does not override Criterion's sampling defaults unless you pass additional CLI args.
- `criterion_statistic` (`mean` | `median`, default `mean`)
  - Statistic used for Criterion base-vs-head comparison deltas.
- `base_sha` (string, optional override)
- `regression_threshold_pct` (number, default `3`)
- `regression_threshold_pct_gungraun` (number, default `-1`)
  - Backend-specific threshold for Gungraun and legacy IAI-Callgrind benchmarks.
  - `-1` falls back to `regression_threshold_pct_iai_callgrind`, then the generic threshold.
- `regression_threshold_pct_iai_callgrind` (number, default `-1`)
  - Deprecated compatibility name for the same threshold. A non-`-1` value emits one
    workflow warning.
  - If both specific names are set, they must have the same value or the workflow fails.
- `regression_threshold_pct_criterion` (number, default `-1`)
  - Optional backend-specific threshold override for `criterion`.
  - `-1` means "use `regression_threshold_pct`".
- `fail_on_regression` (boolean, default `false`)
  - Fails when at least one regression exceeds its configured threshold and is not covered by an
    approved PR-body exception.
- `regression_override_label` (string, default empty)
  - Exact PR label required to activate PR-body regression exceptions.
  - Empty disables exception parsing and preserves the normal threshold gate.
- `comment_mode` (`always` | `on-regression` | `never`, default `always`)
- `action_repository` (string, default `terjekv/github-action-iai-callgrind`)
  - Repository containing this reusable workflow and its scripts.
- `action_ref` (string, default empty)
  - Empty uses the exact commit that defines the called reusable workflow.
  - A ref (SHA/tag/branch) is required when `action_repository` is not the default.

### Outputs

- `has_regressions`: `true` when the run measured any benchmark regression above its threshold,
  including accepted regressions.
- `has_unaccepted_regressions`: `true` when at least one measured regression is not covered by an
  approved exception. This is the value used by `fail_on_regression`.

## Accepting intentional regressions

Some changes, such as constant-time implementations or other security hardening, have a necessary
performance cost. Consumers can opt into reviewable, one-PR exceptions without hiding the measured
regression.

First, configure the exact approval label in the caller workflow and create that label in the caller
repository. The action does not create or apply labels.

```yaml
jobs:
  bench:
    uses: terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v3
    with:
      backend: all
      fail_on_regression: true
      regression_override_label: performance-regression-approved
```

Then add exactly one `rust-pr-bench` fenced JSON block to the PR body:

````markdown
```rust-pr-bench
{
  "accept_regressions": [
    {
      "benchmark": "verify_password",
      "backend": "gungraun",
      "feature": "default",
      "max_regression_pct": 35,
      "reason": "Constant-time verification required by the security fix"
    },
    {
      "benchmark": "tls_handshake",
      "max_regression_pct": "any",
      "reason": "Required protocol hardening"
    }
  ]
}
```
````

Each rule has these fields:

- `benchmark` (required): exact, case-sensitive benchmark display name.
- `max_regression_pct` (required): a finite non-negative percentage, or the string `"any"`.
  A number is the maximum total head-over-base delta, not extra tolerance. For example, `35`
  accepts up to `+35%`.
- `reason` (required): non-empty audit explanation shown in the report.
- `backend` (optional): `gungraun`, a deprecated legacy alias, or `criterion`; omission
  applies to both backends. Legacy aliases normalize to one scope, so new and old
  names for the same benchmark overlap.
- `feature` (optional): exact feature-set name; omission applies to all feature sets.

Exceptions apply to the benchmark-level delta used by the gate. Metric-breakdown rows remain
informational and keep their normal threshold classifications.

Rules use exact matching and do not support globs. Rules for the same benchmark must not overlap:
use disjoint backend or feature scopes when different limits are needed. Malformed JSON, unknown
fields, invalid limits, multiple directive blocks, or overlapping rules fail the report job rather
than silently weakening the gate.

The PR body declares the exception, but it has no effect until a maintainer applies the configured
label. The label application must be later than the PR body's most recent edit. Any subsequent body
edit invalidates that approval even if GitHub retains the label; remove and reapply the label after
reviewing the final directive. The report configuration records a SHA-256 digest of the parsed rules
so the approved directive can be audited independently of unrelated PR-body formatting.

An approved result within its limit is displayed as an accepted regression and remains part of
`has_regressions`; it is excluded only from `has_unaccepted_regressions`. Missing or stale approval
labels and exceeded limits leave the regression actionable. Approved rules that match no
above-threshold result are listed as unused so spelling or scope mistakes are visible.

The report job fetches the current PR body, its last-edit timestamp, and the configured label's most
recent application event. After adding or editing the block, apply or reapply the label, then use
**Re-run failed jobs** on the existing workflow run to reevaluate the report without intentionally
rerunning successful benchmark jobs. To run automatically on PR metadata changes, the caller may
opt into additional event types:

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened, edited, labeled, unlabeled]
```

Those additional event types start a new workflow run, including its benchmark jobs. Include
`unlabeled` if removing approval must automatically invalidate the result for the same commit.

## Benchmark location

By default, benchmarks are expected in Rust's standard `benches/` folder.

You can override this by either:

- Setting `working_directory` for a specific workspace member.
- Running at a Cargo workspace root and using autodiscovery for member crates.
- Providing explicit `benchmarks_json` entries.
- Using `command` in a benchmark spec for custom invocation.

## Benchmark autodiscovery

When `benchmarks_json` is empty and `auto_discover: true`, the workflow scans `benches/*.rs`.
If `working_directory` is a Cargo workspace root, it also scans each workspace member's `benches/*.rs`.

Backend routing is based on the benchmark filename:

- contains `criterion` and no Callgrind-family marker => Criterion only
- contains `gungraun`, `iai_callgrind`, or `callgrind` and not `criterion` =>
  Gungraun only
- contains neither => included for both backends

Examples:

- `parser_gungraun.rs` => Gungraun only
- `parser_iai_callgrind.rs` => Gungraun only (legacy filename retained for pairing)
- `parser_callgrind.rs` => Gungraun only
- `parser_criterion.rs` => Criterion only
- `parser.rs` => both backends

This lets a repo keep both benchmark styles in one `benches/` directory while still routing them predictably.

Use explicit `benchmarks_json` instead of autodiscovery when:

- the bench target names should not follow the filename convention
- different backends need different command lines
- benchmarks live outside the default `benches/` layout
- only a subset of benches should run in CI
- moved benchmark detection would be ambiguous, or the target was renamed

### Moved benchmarks

If `auto_detect_moved_benchmarks: true` is enabled with autodiscovery, the workflow compares discovered head and base benchmark targets. When the same bench target name moved from one workspace member to another and the base target is unique, the report compares the old base command against the new head command and lists the move.

```yaml
jobs:
  bench:
    uses: terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v3
    with:
      backend: all
      auto_discover: true
      auto_detect_moved_benchmarks: true
```

For renamed targets or ambiguous moves, use explicit per-side commands:

```yaml
benchmarks_json: >-
  [
    {
      "name":"parser_callgrind",
      "backend":"gungraun",
      "bench":"parser_callgrind_new",
      "manifest_path":"crates/new-parser/Cargo.toml",
      "base":{
        "bench":"parser_callgrind_old",
        "manifest_path":"crates/old-parser/Cargo.toml"
      }
    }
  ]
```

## Notes

- Lower values are treated as better for both backends:
  - Gungraun: Callgrind summary event counts
  - `criterion`: selected estimate statistic (`mean` or `median`, unit `ns`)
- With `backend: all`, the workflow posts a single consolidated PR comment with one section per backend.
- The workflow installs Valgrind only for the Callgrind family. It sets both
  `GUNGRAUN_RUNNER` and `IAI_CALLGRIND_RUNNER` to package-specific dispatchers. Each
  dispatcher validates the library version passed by the benchmark, reuses an exact-version
  cache, prefers a prebuilt `cargo-binstall` installation, and falls back to
  `cargo install --locked`.
- v3 retains exact-runner compatibility for the existing `iai-callgrind 0.16.1` baseline
  and supports Gungraun versions beginning at `0.17.0`. This permits a base revision on
  the old package and a head revision on Gungraun in the same comparison.
- Gungraun reports use `gungraun` in result JSON, summaries, artifacts, history, and comment
  markers. When a PR already has v2 history or an IAI-Callgrind comment marker, v3 reads and
  normalizes it, then updates that same comment in place.
- Standard `cargo bench --bench <target>` commands are precompiled once per revision and feature
  set. The resulting benchmark executables are distributed to the per-benchmark jobs, preserving
  parallel benchmark execution without rebuilding shared application dependencies for every case.
  Direct execution preserves Cargo's implicit `--bench` argument and dynamic-library search paths.
  Application binaries referenced by IAI binary benchmarks are bundled with their harnesses.
- Precompilation is disabled when a benchmark command, Rust flag, or Cargo configuration uses
  `target-cpu=native`. Those benchmarks build and run on the same runner so native instructions are
  never transferred to a potentially incompatible CPU.
- Full custom commands that cannot be separated into compilation and execution keep the original
  per-benchmark build behavior.
- Markdown layout is template-driven for easier iteration:
  - `scripts/templates/report_single.md.tmpl`
  - `scripts/templates/report_single_summary.md.tmpl`
  - `scripts/templates/report_single_history.md.tmpl`
  - `scripts/templates/report_combined.md.tmpl`
  - `scripts/templates/report_combined_backend_section.md.tmpl`
- Benchmark command overrides can use placeholders:
  - `{features}`
  - `{no_default_features_flag}`
- For full `command`/`head_command`/`base_command` overrides, `cargo_args` is appended to the custom command. Put Cargo and Criterion arguments directly in the custom command when argument ordering matters.

## Criterion defaults and noise

By default, this action passes only `--noplot` to Criterion.

That means Criterion's own defaults still apply unless you override them:

- sample size: `100`
- warm-up time: `3s`
- measurement time: `5s`
- noise threshold: `1%`

On shared CI runners, seeing about `1-3%` variation on unchanged code is not unusual. If you see that level of noise, treat Criterion as a higher-variance signal than Gungraun and tune it explicitly.

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
    uses: terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v3
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

- It has an `iai-callgrind 0.16.1` compatibility target:
  `sample_iai_callgrind_compat_bench`.
- Its retained canonical Callgrind target, `sample_callgrind_bench`, uses Gungraun 0.19.4.
- It has a `criterion` benchmark target: `sample_criterion_bench`.
- It defines two feature sets: `default` and `alt-impl`.
- The workflow `.github/workflows/sample-self-test.yml` runs fast script/unit tests first,
  then validates old-only, new-only, mixed old/new, combined `backend: all`, and autodiscovery
  modes against the sample fixture on pull requests.

## Migrating consumers from v2 to v3

For the safest history-preserving migration, move callers to the v2.3 bridge before changing
their benchmark crate. Callers pinned to `v1` or an immutable SHA must update explicitly;
floating `v1` and `v2` remain on their compatible implementations.

### Quick migration path

1. Change the caller workflow to `@v2.3` while it still uses IAI-Callgrind, then confirm a
   successful benchmark comparison.
2. While staying on `@v2.3`, migrate the benchmark crate to Gungraun and run a PR comparison
   with the base revision still on IAI-Callgrind. Keep the existing Cargo benchmark target name
   during this step so base/head metrics and PR history continue to pair.
3. Change the caller workflow to `@v3`, use the canonical Gungraun input names, and update any
   downstream automation that reads backend-specific artifacts or JSON.

The code and configuration changes are mechanical:

1. Rename the Cargo dependency from `iai-callgrind` to `gungraun = "0.19.4"`.
2. Replace Rust imports from `iai_callgrind::...` with `gungraun::...`.
3. If the consumer manages the runner directly, replace `iai-callgrind-runner` and
   `IAI_CALLGRIND_RUNNER` with `gungraun-runner` and `GUNGRAUN_RUNNER`.
4. Change workflow specs from `backend: iai-callgrind` to `backend: gungraun` and from
   `regression_threshold_pct_iai_callgrind` to `regression_threshold_pct_gungraun`.
5. Initially retain benchmark target filenames. Stable target names preserve base/head metric
   pairing and PR history while the dependency changes.
6. After a successful mixed base/head comparison on v2.3, change the workflow ref to `@v3`.

Before:

```toml
[dev-dependencies]
iai-callgrind = "0.16.1"
```

```rust
use iai_callgrind::{library_benchmark, library_benchmark_group, main};
```

```yaml
jobs:
  bench:
    uses: terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v2.3
    with:
      backend: iai-callgrind
      regression_threshold_pct_iai_callgrind: 3
```

After the mixed comparison succeeds:

```toml
[dev-dependencies]
gungraun = "0.19.4"
```

```rust
use gungraun::{library_benchmark, library_benchmark_group, main};
```

```yaml
jobs:
  bench:
    uses: terjekv/github-action-iai-callgrind/.github/workflows/rust-pr-bench.yml@v3
    with:
      backend: gungraun
      regression_threshold_pct_gungraun: 3
```

Regenerate the consumer's Cargo lockfile and compile its benchmark targets after renaming the
dependency. Consumers with custom runner setup must also install a matching
`gungraun-runner` and expose it through `GUNGRAUN_RUNNER`; the reusable workflow handles this
automatically.

### Compatibility and machine-readable changes

| Interface | v3 behavior | Consumer action |
| --- | --- | --- |
| Repository and canonical workflow | Remain `terjekv/github-action-iai-callgrind` and `.github/workflows/rust-pr-bench.yml` | No rename required |
| Compatibility workflow | `.github/workflows/iai-callgrind-pr-bench.yml` remains supported | Moving to the canonical path is optional |
| Workflow outputs | `has_regressions` and `has_unaccepted_regressions` are unchanged | No output wiring change required |
| Default backend | Calls that omit `backend` now select `gungraun` | Set `backend` explicitly if the default matters |
| Backend and threshold inputs | `gungraun` and `regression_threshold_pct_gungraun` are canonical | Rename legacy inputs to avoid deprecation warnings |
| Result JSON and summaries | Callgrind-family `backend` values serialize as `gungraun` | Update parsers that expect `iai-callgrind` |
| Backend-specific report data | Uses `summary-gungraun.json`, `gungraun-history`, and `<!-- gungraun-bench -->`; backend-specific artifact/report names use `gungraun` | Update external artifact, history, or comment tooling |
| Existing PR history and comments | Old history is normalized and the old comment is updated in place with the new marker | No manual cleanup or duplicate-comment removal required |
| Legacy names | `iai-callgrind`, `iai`, `callgrind`, and `regression_threshold_pct_iai_callgrind` still work but emit one warning | Migrate during v3; removal is no earlier than v4 |

Version 3 defaults to and serializes `gungraun`, migrates old history/comment markers in place,
and keeps `iai-callgrind`, `iai`, and `callgrind` as deprecated aliases. Those aliases remain
supported through every v3 release and will not be removed before v4.
