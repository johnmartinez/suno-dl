# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- CLI skeleton in `suno-dl.py`: `Config` dataclass, `AudioFormat` enum, `ConfigError`, and every flag from SPEC.md §3.1 wired through `click`. Session cookie loaded from `SUNO_SESSION_COOKIE` only; `--verbose` prints the loaded config with the cookie redacted. `__version__ = "0.1.0"` exposed via `--version`. (Phase 1, #1)
- `Track` dataclass, `AuthError`, `APIError`, and `SunoClient` with `get_tracks_page` / `get_all_tracks` per SPEC.md §3.2. Pagination stops on empty `clips` array; `--limit` caps mid-page; `page_delay_ms` is applied between page fetches. `--dry-run` now enumerates the library and prints `title\tid\taudio_url` per track. HTTP 401/403 surfaces as `AuthError` and the CLI prints the SPEC.md §5 message verbatim. (Phase 2, #2)
- Renamed script from `suno_dl.py` to `suno-dl.py` to match the repo and installed binary name. The script is no longer importable as a Python module — version is now inspected via `python suno-dl.py --version`. (#10)

### Planned for v0.1.0 (MVP)

- `FileManager` with Unicode-safe filename generation (Phase 3, #3)
- Streaming downloads with atomic `.tmp` → rename pattern (Phase 4, #4)
- tqdm progress bar and `RunSummary` output (Phase 5, #5)
- Resume / idempotency via file-existence checks (Phase 6, #6)
- Optional WAV format with MP3 fallback (Phase 7, #7)
- `install.sh`, `requirements.txt`, `.env.example`, full README (Phase 8, #8)

[Unreleased]: https://github.com/johnmartinez/suno-dl/compare/HEAD...HEAD
