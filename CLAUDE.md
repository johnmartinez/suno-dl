# CLAUDE.md — suno-dl Implementation Instructions

This file is the implementation guide for Claude Code. SPEC.md is the source of
truth for all behavior, data structures, interfaces, and scenarios. This file
defines the build order, implementation rules, and validation checkpoints.

---

## Ground Rules

- Implement against SPEC.md exactly. Do not invent features or behaviors not
  specified there.
- All logic lives in `suno_dl.py`. Do not split into multiple modules unless
  explicitly instructed.
- Do not add dependencies beyond `requests`, `tqdm`, and `click`.
- Never log or print the session cookie value at any log level.
- All file writes must be atomic: write to `{dest}.tmp`, then `os.rename()`.
- Exit codes must match the spec exactly: 0, 1, or 2. No other values.

---

## Implementation Order

Build in this sequence. Complete and validate each phase before starting the
next. Do not skip ahead.

### Phase 1 — Skeleton and Config

1. Create `suno_dl.py` with a `@click.command()` entry point.
2. Implement `Config` dataclass. Load `SUNO_SESSION_COOKIE` from `os.environ`.
   Raise `ConfigError` with a clear message if missing.
3. Wire all CLI flags from Section 3.1 of SPEC.md to `Config` fields.
4. Print `Config` (redacting cookie) when `--verbose` is set.
5. Validate: `python suno_dl.py --help` shows all flags. Missing cookie exits 2.

### Phase 2 — SunoClient (Pagination Only)

1. Implement `SunoClient` class with `get_tracks_page()` and `get_all_tracks()`.
2. Use the headers from Section 3.2 verbatim.
3. Implement `AuthError` and `APIError` exceptions.
4. `get_all_tracks()` must apply `page_delay_ms` between pages.
5. `get_all_tracks()` must respect `limit` if set.
6. Validate: `suno-dl --dry-run` prints track list without downloading.
   Confirm pagination stops correctly on empty page.

### Phase 3 — FileManager

1. Implement `FileManager` with all four functions from Section 3.3.
2. `safe_filename()` must handle Unicode titles (normalize to ASCII, strip
   non-alphanumeric). Test with Spanish and Portuguese characters from
   real Suno track titles (ñ, é, ã, etc.).
3. Validate: filenames generated for "Café Estelar", "Un Junio Mañanero",
   "Innie Mañana" produce safe, readable results with no illegal characters.

### Phase 4 — Download + Atomic Write

1. Implement `SunoClient.download_file()` with streaming GET and atomic
   `.tmp` → rename pattern.
2. Implement `DownloadError`.
3. Wire the main download loop from Section 4 of SPEC.md.
4. Apply `dl_delay_ms` between each track download.
5. Validate: download a single track with `--limit 1`. Confirm file exists,
   is non-zero bytes, and has the correct filename format.

### Phase 5 — Progress Reporter and RunSummary

1. Implement `ProgressReporter` using `tqdm`.
2. Implement `compute_summary()` to produce `RunSummary` from results list.
3. `finish()` must print summary in this format:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
suno-dl complete
  Total tracks : 47
  Downloaded   : 12
  Skipped      : 35
  Failed       : 0
  Output dir   : /Users/john/Music/suno
  Elapsed      : 43.2s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

4. If `failed > 0`, print failed IDs below the summary block.
5. Validate: Run against full library. Confirm summary counts are accurate.

### Phase 6 — Resume and Idempotency

1. Validate that re-running after a complete download results in all tracks
   skipped and exit code 0.
2. Simulate interruption (KeyboardInterrupt mid-run). Confirm `.tmp` files
   are not left behind (handle `KeyboardInterrupt` to clean up in-progress
   `.tmp` file).
3. Validate: Re-run after interruption resumes correctly.

### Phase 7 — WAV Format

1. Implement WAV fallback logic: if `--format wav` but `track.wav_url` is
   None, fall back to MP3 silently (no error).
2. Validate: Run with `--format wav`. Confirm mix of `.wav` and `.mp3` files
   as appropriate.

### Phase 8 — Supporting Files

1. Write `requirements.txt` with pinned minimum versions from Section 8 of
   SPEC.md.
2. Write `install.sh`:
   - `pip install -r requirements.txt --break-system-packages`
   - `chmod +x suno_dl.py`
   - `ln -sf $(pwd)/suno_dl.py /usr/local/bin/suno-dl`
3. Write `.env.example` with placeholder cookie value and instructions.
4. Write `README.md` covering: cookie extraction steps (DevTools path),
   install, basic usage, flag reference, and troubleshooting expired cookies.

---

## Validation Checklist (run before declaring done)

- [ ] `suno-dl --help` shows all flags with correct defaults
- [ ] Missing `SUNO_SESSION_COOKIE` exits 2 with clear message
- [ ] `--dry-run` prints tracks, writes no files, exits 0
- [ ] Full library download completes, all files present, summary accurate
- [ ] Re-run skips all existing files, exits 0
- [ ] Interrupted run leaves no `.tmp` files
- [ ] Re-run after interruption downloads only missing tracks
- [ ] Filenames with Spanish/Portuguese characters are safe and readable
- [ ] `--limit 10` downloads exactly 10 tracks
- [ ] `--format wav` falls back to MP3 gracefully when wav_url is None
- [ ] Stale cookie scenario exits 2 with correct message
- [ ] Per-track download failure logs error, continues, exits 1

---

## Known API Notes (as of May 2026)

- Endpoint: `https://studio-api.suno.ai/api/feed/?page={n}&page_size=20`
- Response shape: `{ "clips": [ { "id": ..., "title": ..., "audio_url": ..., ... } ] }`
- Auth: Cookie header with `__session={value}` extracted from browser
- Pagination: zero-indexed pages; empty `clips` array signals end of library
- If endpoint returns 404 or shape changes, log the raw response body in
  verbose mode to aid debugging

---

## What Not To Do

- Do not use `selenium`, `playwright`, or any browser automation
- Do not store or cache the session cookie to disk
- Do not add retry loops on auth failures (fail fast on 401/403)
- Do not parallelize downloads (serial only, rate-limit-safe)
- Do not create subdirectories per album or date — flat output dir only in v1
