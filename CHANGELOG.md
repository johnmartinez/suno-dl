# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- CLI skeleton in `suno_dl.py`: `Config` dataclass, `AudioFormat` enum, `ConfigError`, and every flag from SPEC.md §3.1 wired through `click`. Session cookie loaded from `SUNO_SESSION_COOKIE` only; `--verbose` prints the loaded config with the cookie redacted. `__version__ = "0.1.0"`. (Phase 1, #1)

### Planned for v0.1.0 (MVP)

- `SunoClient` with paginated track enumeration (Phase 2, #2)
- `FileManager` with Unicode-safe filename generation (Phase 3, #3)
- Streaming downloads with atomic `.tmp` → rename pattern (Phase 4, #4)
- tqdm progress bar and `RunSummary` output (Phase 5, #5)
- Resume / idempotency via file-existence checks (Phase 6, #6)
- Optional WAV format with MP3 fallback (Phase 7, #7)
- `install.sh`, `requirements.txt`, `.env.example`, full README (Phase 8, #8)

[Unreleased]: https://github.com/johnmartinez/suno-dl/compare/HEAD...HEAD
