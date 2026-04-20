# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Changelog tracking formally starts with `2.0.0`. Earlier releases, including `v1`, were not backfilled here.

## [2.0.2] - 2026-04-20

### Fixed

- Bump checkout and upload-artifact actions.

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
