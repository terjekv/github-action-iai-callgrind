# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Expand the v2-to-v3 migration guide with a staged upgrade path, before/after examples,
  and an explicit list of stable interfaces and machine-readable identifier changes.

## [3.0.0] - 2026-07-31

### Added

- Emit one GitHub Actions deprecation warning when a workflow call uses legacy backend
  names or `regression_threshold_pct_iai_callgrind`.
- Add v3 migration coverage for legacy benchmark specifications, regression overrides,
  history payloads, comment markers, and exact old/new runner dispatch.

### Changed

- Make `gungraun` the default and canonical backend in matrices, result JSON, summaries,
  artifacts, reports, history, and regression-override scopes.
- Rename internal report and artifact paths from `iai-callgrind` to `gungraun`, and title
  standalone reports “Gungraun Benchmark Report.”
- Normalize `target/iai` and `target/gungraun` metric paths to the canonical `gungraun`
  component.
- Update all documentation and caller examples to use the Rust PR Bench v3 workflow.

### Deprecated

- Deprecate the `iai-callgrind`, `iai`, and `callgrind` backend aliases and
  `regression_threshold_pct_iai_callgrind`. They remain supported through every v3
  release and will not be removed before v4.

### Fixed

- Read `gungraun-history` before falling back to `iai-callgrind-history`, normalize old
  history entries, and rewrite legacy PR comments using the Gungraun marker without
  creating duplicates.
- Pin helper-script checkouts to the exact reusable-workflow commit when `action_ref` is
  empty, while preserving the v2 wire contract for immutable older workflows that
  historically loaded helpers from the default branch.

## [2.3.0] - 2026-07-30

### Added

- Add `gungraun` as a v2-compatible backend name and
  `regression_threshold_pct_gungraun` as the preferred Callgrind-family threshold input.
- Add exact-version package-specific dispatchers for `iai-callgrind-runner 0.16.1` and
  `gungraun-runner >= 0.17.0`, preferring `cargo-binstall` and falling back to
  `cargo install --locked`.
- Add a Gungraun 0.19.4 sample fixture plus old-only, new-only, mixed-runner, combined, and
  autodiscovery self-test coverage.

### Changed

- Brand the workflow and reports as Rust PR Bench with Gungraun / IAI-Callgrind and Criterion
  backends.
- Recognize `gungraun`, `iai_callgrind`, and `callgrind` benchmark filenames during
  autodiscovery, and normalize Gungraun names in benchmark specs and regression exceptions.
- Bake both runner dispatcher paths into precompiled benchmark executables so base and head can
  request different runner families and exact versions.
- Update all Cargo lockfile dependencies and versioned GitHub Actions to their latest releases,
  and add weekly Dependabot coverage for GitHub Actions.

### Fixed

- Normalize `target/iai` and `target/gungraun` Callgrind metric paths so detailed metrics pair
  across a migration.
- Reject conflicting new and legacy Callgrind threshold inputs with an actionable error.
- Generalize runner/library mismatch diagnostics for both IAI-Callgrind and Gungraun.

## [2.2.0] - 2026-07-22

### Added

- Add opt-in, label-approved PR-body exceptions for intentional benchmark regressions while keeping
  raw and unaccepted regression signals separate in reports and reusable-workflow outputs.
- Precompile standard Cargo benchmark targets once per revision and feature set, then distribute
  their executables to the existing parallel benchmark jobs.

### Security

- Bind regression-exception approval to a label application newer than the latest PR-body edit and
  record the parsed directive digest, preventing retained labels from approving edited exceptions.

### Fixed

- Preserve Cargo's `--bench` execution semantics and dynamic-library search paths for precompiled
  benchmarks, keep binary artifacts out of report downloads, and avoid cross-runner execution for
  `target-cpu=native` builds.

Changelog tracking formally starts with `2.0.0`. Earlier releases, including `v1`, were not backfilled here.

## [2.1.3] - 2026-07-12

### Fixed

- Prevent moved benchmarks from inheriting the head revision's manifest path when their base source is the workspace root.

## [2.1.2] - 2026-07-10

### Fixed

- Restrict release automation to full version tags so the floating `v2` and `v2.1` action tags can be maintained safely.

## [2.1.1] - 2026-07-10

### Changed

- Updated all versioned GitHub Actions to their latest major releases.

## [2.1.0] - 2026-07-10

### Added

- Added workspace benchmark autodiscovery and moved-benchmark detection.

### Fixed

- Honor workspace exclusions when workspace member declarations use glob patterns.
- Only compare moved benchmarks when their source is absent from the head revision.
- Exclude failed benchmark runs from report summaries, averages, regressions, and history.

## [2.0.2] - 2026-04-20

### Fixed

- Bump checkout and upload-artifact actions.
- Fix release python validator.

## [2.0.1] - 2026-02-27

### Fixed

- Fixed the report job dependency graph so benchmark artifacts are downloaded correctly before rendering the PR report.

## [2.0.0] - 2026-02-27

### Added

- Added Criterion benchmark support alongside `iai-callgrind`.
- Added `backend: all` to run both supported backends in one workflow invocation.
- Added consolidated PR reporting for combined runs, with one section per backend.
- Added per-backend regression threshold overrides for `iai-callgrind` and `criterion`.
- Added template-driven report rendering, including split summary/history partial templates.
- Added a sample Criterion benchmark fixture in `examples/sample-rust-app`.
- Added local script and snapshot tests for matrix expansion, report rendering, report composition, and PR comment helpers.
- Added CI coverage for explicit backend runs, combined runs, and autodiscovery.

### Changed

- Renamed the canonical reusable workflow entrypoint to `.github/workflows/rust-pr-bench.yml`.
- Kept the previous `.github/workflows/iai-callgrind-pr-bench.yml` path as a compatibility wrapper.
- Improved README usage examples to show realistic backend-specific and combined setups.
- Documented autodiscovery behavior and filename-based backend routing.

### Fixed

- Fixed hidden PR history preservation when a run produces no benchmark results.
- Fixed duplicate run metadata in combined reports by moving shared metadata to the top-level report.
- Fixed artifact naming collisions across multiple workflow invocations in the same workflow run.
