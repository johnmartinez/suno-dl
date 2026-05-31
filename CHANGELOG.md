# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- CLI skeleton in `suno-dl.py`: `Config` dataclass, `AudioFormat` enum, `ConfigError`, and every flag from SPEC.md §3.1 wired through `click`. Session cookie loaded from `SUNO_SESSION_COOKIE` only; `--verbose` prints the loaded config with the cookie redacted. `__version__ = "0.1.0"` exposed via `--version`. (Phase 1, #1)
- `Track` dataclass, `AuthError`, `APIError`, and `SunoClient` with `get_tracks_page` / `get_all_tracks` per SPEC.md §3.2. Pagination stops on empty `clips` array; `--limit` caps mid-page; `page_delay_ms` is applied between page fetches. `--dry-run` now enumerates the library and prints `title\tid\taudio_url` per track. HTTP 401/403 surfaces as `AuthError` and the CLI prints the SPEC.md §5 message verbatim. (Phase 2, #2)
- `FileManager` with `make_output_dir`, `safe_filename`, `file_exists`, `resolve_dest` per SPEC.md §3.3. `safe_filename` NFKD-normalizes Unicode titles to ASCII (so `ñ→n`, `é→e`, `ã→a`, `ç→c`), strips disallowed chars, collapses whitespace to `_`, truncates the title component to 80 chars, and appends `_{track_id[:8]}`. Titles made entirely of stripped characters still produce a non-empty filename (the id suffix survives). (Phase 3, #3)
- `DownloadStatus` enum, `DownloadResult` dataclass, `DownloadError` exception, and `SunoClient.download_file` with streaming GET + atomic `.tmp`→`rename` write pattern. Main loop now wired per SPEC.md §4 step 7: per-track format selection (WAV falls back to MP3 when `wav_url` is None), existing files skipped via `file_exists`, per-track 403/500/network errors marked failed and the loop continues. On `DownloadError` the partial `.tmp` is cleaned up. `--dl-delay` applied between every track. Exit 0 if no failures, exit 1 otherwise. (Phase 4, #4)
- `RunSummary` dataclass, `ProgressReporter` (tqdm-based), and `compute_summary()` per SPEC.md §3.4 / §2. tqdm bar advances once per track. `--verbose` emits `[ok] / [skip] / [fail]` lines per track via `tqdm.write` so they interleave cleanly with the bar. At end of run, a fixed-format summary block prints to stdout (`Total tracks / Downloaded / Skipped / Failed / Output dir / Elapsed` with the exact column alignment from CLAUDE.md Phase 5), bookended by 36-char `━` rules. When `failed > 0`, a `Failed track IDs:` section follows. Exit 0 when `failed == 0`, exit 1 otherwise. Replaces the terse Phase 4 placeholder line. (Phase 5, #5)
- `SunoClient.download_file` restructured to clean up partial `.tmp` on **any** non-success exit path — DownloadError, KeyboardInterrupt (Ctrl+C), SystemExit, or any other exception — via a success-flag + outer `finally`. Main download loop now catches KeyboardInterrupt, prints the partial summary block, prints an "interrupted by user — re-run the same command to resume" hint to stderr, and exits 1. Together with the existing `file_exists` skip-check, this gives full SPEC.md Scenario 2 behavior: interrupted runs leave no `.tmp` orphans and the next run resumes idempotently with previously-downloaded files byte-identical (mtime preserved). (Phase 6, #6)
- Renamed script from `suno_dl.py` to `suno-dl.py` to match the repo and installed binary name. The script is no longer importable as a Python module — version is now inspected via `python suno-dl.py --version`. (#10)

### Planned for v0.1.0 (MVP)

- Optional WAV format with MP3 fallback (Phase 7, #7)
- `install.sh`, `requirements.txt`, `.env.example`, full README (Phase 8, #8)

[Unreleased]: https://github.com/johnmartinez/suno-dl/compare/HEAD...HEAD
