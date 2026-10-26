# Mobile CI Red — Root Cause & Fix

**Date:** 2026-10-25
**Scope:** GitHub Actions workflow *CI* (job *Analyze & Test*), failing at step *Run dart analyze* on every push since `cbb3e6a` through `5640305`.

## Symptom

Every CI run failed at `dart analyze` with `Process completed with exit code 2`; the `flutter test --coverage` step never ran (skipped).

## Root cause

`pubspec.yaml` declares `assets/images/` as a Flutter asset directory, but the directory contained **no files at all** — and git does not track empty directories.

Consequence:

- On any **fresh checkout** (CI, new clones) `assets/images/` does not exist.
- The analyzer then emits a diagnostic on `pubspec.yaml:57`:
  `asset_directory_does_not_exist — The asset directory 'assets/images/' doesn't exist.`
- `dart analyze` exits with code **2** on any issue found (including warnings), which fails the CI step.

Local development machines never saw this because `assets/images/` existed locally as an empty, untracked directory — analyzer output was clean there, masking the failure. This affected every commit since the asset declaration was introduced in the initial commit `cbb3e6a`.

The Dart/Flutter SDK versions were ruled out: reproducing CI exactly (fresh clone + stable `3.47.8` / Dart `3.13.7`, the version `subosito/flutter-action@v2` resolves) showed the same single warning and exit code 2, and no other analyzer issues anywhere in `lib/` or `test/`.

## Fix

- `assets/images/.gitkeep` — tracks the directory in git so fresh checkouts have it. Dotfiles are ignored by the Flutter asset bundler, so the declared asset directory resolves and no app behavior changes. No workflow, dependency, or API changes.

## Verification

- `dart analyze` → `No issues found!`, exit 0 (local SDK 3.47.1/Dart 3.13.1 **and** CI-parity SDK 3.47.8/Dart 3.13.7 on a fresh clone).
- `flutter test --coverage` → 117/117 tests pass on both SDKs.
