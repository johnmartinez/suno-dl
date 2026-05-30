# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned for v0.1.0 (MVP)

- CLI entry point with all flags defined in SPEC.md §3.1
- `SunoClient` with paginated track enumeration
- `FileManager` with Unicode-safe filename generation
- Streaming downloads with atomic `.tmp` → rename pattern
- tqdm progress bar and `RunSummary` output
- Resume / idempotency via file-existence checks
- Optional WAV format with MP3 fallback
- `install.sh`, `requirements.txt`, `.env.example`, full README

[Unreleased]: https://github.com/johnmartinez/suno-dl/compare/HEAD...HEAD
