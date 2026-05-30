# suno-dl — NLSpec

## 1. Overview

suno-dl is a CLI tool that bulk-downloads a user's entire Suno Pro library to
local disk. It authenticates via a browser-extracted session cookie, paginates
the Suno internal API to enumerate all tracks, and downloads each as MP3 (with
optional WAV for Pro subscribers). Downloads are resumable, idempotent, and
name-safe.

The tool runs as a single Python script or installed CLI on macOS/Linux (UNIX
native). No Docker required. No external services.

### 1.1 Design Principles

- **Single-file CLI**: One Python script, stdlib + three pip dependencies. No framework overhead.
- **Spec-driven development**: This document is the source of truth. Claude Code implements against it.
- **Idempotent by default**: Re-running never re-downloads existing files. Skip logic is file-existence based.
- **Resume-capable**: Interrupted runs pick up exactly where they left off.
- **Token-safe**: Session cookie read from env var only — never hardcoded, never logged.
- **Linux/macOS first**: UNIX path conventions throughout. No Windows accommodation.

### 1.2 Constraints

- Suno does not publish an official public API. This tool uses the same internal endpoints the web UI uses. Endpoints may change without notice.
- Session cookie (`__session` from suno.com) is the auth mechanism. It expires; the user must re-extract if it stops working.
- CDN URLs in the API responses are time-limited presigned URLs. Download must occur during the same session.
- Rate limiting: enforce a configurable delay between requests to avoid triggering Suno's rate limiter (default: 500ms between downloads, 200ms between pagination calls).
- MP3 only from CDN; WAV is generated on-demand server-side and may take longer to resolve.

---

## 2. Data Structures

```
RECORD Track:
    id          : String          -- Suno UUID (e.g. "b75f73f7-e535-4e40-982b-b59342ac1291")
    title       : String          -- display title, may contain special characters
    audio_url   : String          -- CDN presigned MP3 URL
    wav_url     : String | None   -- CDN presigned WAV URL (Pro only, may be None)
    image_url   : String | None   -- cover art URL
    created_at  : Timestamp       -- ISO 8601
    tags        : String          -- Suno style prompt (the "tags" field in API response)
    metadata    : Map<String,Any> -- full raw API record, preserved for future use

RECORD DownloadResult:
    track_id    : String
    title       : String
    status      : DownloadStatus
    path        : String | None   -- local file path if success
    error       : String | None   -- error message if failed or skipped

ENUM DownloadStatus:
    downloaded  -- newly downloaded this run
    skipped     -- file already exists
    failed      -- download attempted, error occurred

RECORD RunSummary:
    total_tracks    : Int
    downloaded      : Int
    skipped         : Int
    failed          : Int
    failed_ids      : List<String>
    output_dir      : String
    elapsed_seconds : Float

RECORD Config:
    session_cookie  : String      -- from env: SUNO_SESSION_COOKIE
    output_dir      : String      -- from flag: --output-dir, default: ~/Music/suno
    format          : AudioFormat -- from flag: --format, default: mp3
    page_delay_ms   : Int         -- from flag: --page-delay, default: 200
    dl_delay_ms     : Int         -- from flag: --dl-delay, default: 500
    dry_run         : Boolean     -- from flag: --dry-run, default: false
    limit           : Int | None  -- from flag: --limit, default: None (all tracks)
    verbose         : Boolean     -- from flag: --verbose, default: false

ENUM AudioFormat:
    mp3
    wav
```

---

## 3. Interfaces

### 3.1 CLI Interface

```
COMMAND suno-dl:

    FLAGS:
        --output-dir DIR     Local directory for downloads. Created if absent.
                             Default: ~/Music/suno
        --format FORMAT      Audio format: mp3 | wav. Default: mp3.
        --page-delay MS      Delay between pagination API calls in ms. Default: 200.
        --dl-delay MS        Delay between file downloads in ms. Default: 500.
        --dry-run            Enumerate tracks and print what would be downloaded.
                             No files written.
        --limit N            Download only the N most recent tracks. Default: all.
        --verbose            Print per-track status as downloads complete.
        --help               Print usage and exit.

    ENV VARS:
        SUNO_SESSION_COOKIE  Required. The __session cookie value from suno.com.
                             Extract from browser DevTools → Application → Cookies.

    EXIT CODES:
        0    All tracks downloaded or skipped (clean run).
        1    One or more tracks failed to download.
        2    Fatal error (auth failure, bad config, unrecoverable API error).
```

### 3.2 Suno API Client

```
INTERFACE SunoClient:

    BASE_URL: "https://studio-api.suno.ai"

    HEADERS (all requests):
        Cookie: "__session={session_cookie}"
        User-Agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        Accept: "application/json"

    FUNCTION get_tracks_page(page: Int, page_size: Int = 20) -> List<Track>:
        -- GET {BASE_URL}/api/feed/?page={page}&page_size={page_size}
        -- Parse response: data["clips"] array
        -- Map each clip to Track record
        -- Return empty list when clips array is empty (signals end of pagination)
        -- Raise AuthError on HTTP 401 or 403
        -- Raise APIError on other non-200 responses

    FUNCTION get_all_tracks(limit: Int | None) -> List<Track>:
        -- Paginate get_tracks_page() starting at page=0
        -- Stop when: empty page returned OR limit reached
        -- Apply page_delay_ms between each page request
        -- Return full list of Track records

    FUNCTION download_file(url: String, dest_path: String) -> None:
        -- HTTP GET url with streaming response
        -- Write to dest_path atomically (write to .tmp, rename on success)
        -- Raise DownloadError on non-200 or connection failure
```

### 3.3 File Manager

```
INTERFACE FileManager:

    FUNCTION make_output_dir(path: String) -> None:
        -- os.makedirs(path, exist_ok=True)

    FUNCTION safe_filename(title: String, track_id: String) -> String:
        -- Strip characters not in [a-zA-Z0-9 _\-]
        -- Replace runs of whitespace with single underscore
        -- Truncate title component to 80 characters
        -- Append track_id suffix for uniqueness
        -- Format: "{sanitized_title}_{track_id[:8]}"
        -- Example: "Un_Junio_Manero_b75f73f7.mp3"

    FUNCTION file_exists(path: String) -> Boolean:
        -- os.path.exists(path)

    FUNCTION resolve_dest(output_dir: String, filename: String) -> String:
        -- os.path.join(output_dir, filename)
```

### 3.4 Progress Reporter

```
INTERFACE ProgressReporter:

    FUNCTION start(total: Int) -> None:
        -- Initialize tqdm progress bar with total track count

    FUNCTION update(result: DownloadResult) -> None:
        -- Advance progress bar by 1
        -- If verbose: print status line per track

    FUNCTION finish(summary: RunSummary) -> None:
        -- Close progress bar
        -- Print RunSummary to stdout
        -- If failed_ids non-empty: print list of failed IDs
```

---

## 4. Core Workflow

```
FUNCTION main():

    1. Load Config from env + flags. Fail fast if SUNO_SESSION_COOKIE missing.

    2. Instantiate SunoClient, FileManager, ProgressReporter.

    3. FileManager.make_output_dir(config.output_dir)

    4. Print: "Fetching track list from Suno..."
       tracks = SunoClient.get_all_tracks(limit=config.limit)
       Print: "Found {len(tracks)} tracks."

    5. If config.dry_run:
           For each track: print title, id, audio_url
           Exit 0.

    6. ProgressReporter.start(total=len(tracks))
       results = []

    7. For each track in tracks:

           ext = "wav" if config.format == wav AND track.wav_url != None else "mp3"
           url = track.wav_url if ext == "wav" else track.audio_url
           filename = FileManager.safe_filename(track.title, track.id) + "." + ext
           dest = FileManager.resolve_dest(config.output_dir, filename)

           IF FileManager.file_exists(dest):
               result = DownloadResult(track.id, track.title, skipped, dest, None)
           ELSE:
               TRY:
                   SunoClient.download_file(url, dest)
                   result = DownloadResult(track.id, track.title, downloaded, dest, None)
               CATCH DownloadError as e:
                   result = DownloadResult(track.id, track.title, failed, None, str(e))

           results.append(result)
           ProgressReporter.update(result)
           sleep(config.dl_delay_ms / 1000)

    8. summary = compute_summary(results, config.output_dir, elapsed)
       ProgressReporter.finish(summary)

    9. Exit 0 if summary.failed == 0 else Exit 1.
```

---

## 5. Error Handling

```
EXCEPTION AuthError:
    -- HTTP 401 or 403 from Suno API
    -- Fatal: print "Session cookie invalid or expired. Re-extract from browser."
    -- Exit 2.

EXCEPTION APIError:
    -- Non-200, non-auth HTTP response from Suno API
    -- Fatal on pagination failures (can't enumerate library)
    -- Per-track on download failures (log, continue)

EXCEPTION DownloadError:
    -- Network error or non-200 during file download
    -- Non-fatal: mark track as failed, continue to next track

EXCEPTION ConfigError:
    -- Missing required env var or invalid flag value
    -- Fatal: print specific error, Exit 2.
```

---

## 6. Project Structure

```
suno-dl/
├── suno_dl.py          -- single-file implementation (all logic)
├── requirements.txt    -- requests, tqdm, click
├── install.sh          -- pip install + symlink to /usr/local/bin/suno-dl
├── .env.example        -- SUNO_SESSION_COOKIE=your_cookie_here
├── SPEC.md             -- this file
├── CLAUDE.md           -- implementation instructions for Claude Code
└── README.md           -- quickstart, cookie extraction steps
```

---

## 7. Scenarios

### Scenario 1: Full Library Download

```
USER runs: SUNO_SESSION_COOKIE=abc123 suno-dl --output-dir ~/Music/suno

EXPECTED BEHAVIOR:
    - Paginates API until all tracks enumerated.
    - Downloads each as MP3 to ~/Music/suno/.
    - Shows tqdm progress bar.
    - Prints RunSummary on completion.

VALIDATION:
    - File count in output dir == total_tracks - skipped.
    - Each file named "{safe_title}_{id[:8]}.mp3".
    - No existing files overwritten.
```

### Scenario 2: Resume Interrupted Download

```
USER re-runs same command after interruption mid-library.

EXPECTED BEHAVIOR:
    - Already-downloaded files detected via file_exists check.
    - Skipped without re-downloading.
    - Only remaining tracks downloaded.

VALIDATION:
    - summary.skipped > 0.
    - No duplicate files created.
    - Previously downloaded files byte-identical (no re-write).
```

### Scenario 3: Dry Run

```
USER runs: suno-dl --dry-run

EXPECTED BEHAVIOR:
    - Track list fetched and printed: title, id, audio_url per line.
    - No files written to disk.
    - Exit 0.

VALIDATION:
    - output_dir unchanged or not created.
    - stdout contains one line per track.
```

### Scenario 4: Expired Session Cookie

```
USER runs with stale cookie.

EXPECTED BEHAVIOR:
    - First API call returns HTTP 401.
    - Tool prints: "Session cookie invalid or expired. Re-extract from browser."
    - Exit 2.

VALIDATION:
    - No files written.
    - Exit code == 2.
```

### Scenario 5: Partial Failure (Some Tracks Fail)

```
CDN URL for 3 tracks returns 403 (presigned URL expired mid-run).

EXPECTED BEHAVIOR:
    - Failed tracks logged with error message.
    - Remaining tracks continue downloading.
    - summary.failed == 3, summary.failed_ids lists those 3 IDs.
    - Exit 1.

VALIDATION:
    - Run does not abort on per-track failure.
    - Exit code == 1 (not 0).
```

### Scenario 6: WAV Format (Pro)

```
USER runs: suno-dl --format wav

EXPECTED BEHAVIOR:
    - For tracks with wav_url: download WAV, filename ends in .wav.
    - For tracks without wav_url: fall back to MP3, filename ends in .mp3.

VALIDATION:
    - Mix of .wav and .mp3 in output dir depending on track availability.
    - No crash on None wav_url.
```

### Scenario 7: Limit Flag

```
USER runs: suno-dl --limit 10

EXPECTED BEHAVIOR:
    - Fetch pages until 10 tracks collected (may require 1 page).
    - Download only those 10.
    - summary.total_tracks == 10.

VALIDATION:
    - Exactly 10 files maximum in output dir post-run.
```

---

## 8. Dependencies

```
requests>=2.31.0    -- HTTP client, streaming downloads
tqdm>=4.66.0        -- progress bar
click>=8.1.0        -- CLI flag parsing

Python: 3.10+
OS: macOS, Linux (UNIX)
```

---

## 9. Security Considerations

- Session cookie read from env var only. Never logged at any level.
- No credentials written to disk by this tool.
- Atomic file writes (.tmp → rename) prevent partial files on interruption.
- No PHI or sensitive data involved; standard operational security applies.
- Tool makes only GET requests. No mutations to Suno account data.

---

## 10. Future Extensions (Out of Scope for v1)

- Metadata embedding (ID3 tags: title, tags/style, creation date)
- Cover art download and embedding
- JSON manifest export (full track metadata alongside audio files)
- Filter by date range, title pattern, or tag/style keyword
- Playlist-aware folder organization
- SunoSync-compatible output format
