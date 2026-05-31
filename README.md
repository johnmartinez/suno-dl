# suno-dl

> Bulk-download a Suno Pro library to local disk.

`suno-dl` is a single-file Python CLI that authenticates with a browser-extracted Suno session cookie, paginates the internal API to enumerate every track in your library, and downloads each as MP3 (or WAV for Pro subscribers). Downloads are **resumable** and **idempotent** — re-running never re-downloads an existing file, and an interrupted run picks up exactly where it left off.

**Status:** v0.1.0. macOS / Linux only. Python 3.10+.

---

## Install

```bash
git clone https://github.com/johnmartinez/suno-dl.git
cd suno-dl
./install.sh
```

Run as your regular user — **not** with sudo. `install.sh` invokes `sudo` itself for the single step that needs it (the symlink into `/usr/local/bin`) and will prompt for your password at that point. Running the whole script as root would install the Python packages into the system site-packages instead of your user site. If you'd rather avoid sudo entirely, see [Install without sudo](#install-without-sudo) below.

`install.sh` does three things:

1. `pip install -r requirements.txt --break-system-packages` — installs `requests`, `tqdm`, `click` (as your user)
2. `chmod +x suno-dl.py`
3. `ln -sf "$(pwd)/suno-dl.py" /usr/local/bin/suno-dl` (via `sudo` if `/usr/local/bin` isn't writable by you)

After install, `suno-dl --help` should work from anywhere.

---

## Extract your session cookie

`suno-dl` reuses your logged-in browser session via the `__session` cookie. There's no separate login.

1. Open <https://suno.com> in your browser and log in.
2. Open DevTools:
   - macOS: `⌘+⌥+I` (Chrome/Edge/Brave) or `⌘+⌥+C` (Safari, after enabling the Develop menu)
   - Linux: `F12` (Chrome/Firefox)
3. Navigate: **Application** → **Cookies** → **https://suno.com**
4. Find the row named `__session` and copy its `Value` column.
5. Export it in your shell:

```bash
export SUNO_SESSION_COOKIE='paste_the_cookie_value_here'
```

Or use the `.env` pattern:

```bash
cp .env.example .env
# edit .env, paste your cookie value, then:
set -a; source .env; set +a
```

The cookie typically lasts a few days. If `suno-dl` starts exiting with `Session cookie invalid or expired`, re-extract.

---

## Usage

### Download your entire library

```bash
suno-dl
```

Defaults: `~/Music/suno`, MP3 format, 500 ms between downloads.

### Preview without downloading

```bash
suno-dl --dry-run
```

Prints `title<TAB>id<TAB>audio_url` per track, writes nothing, exits 0.

### Resume after interruption

Just re-run the same command. Files already on disk are skipped (matched by filename), and interrupted downloads leave no `.tmp` orphans behind:

```bash
suno-dl   # downloads what's missing; skips what isn't
```

### Pro-only: WAV format

```bash
suno-dl --format wav
```

Tracks without a server-rendered WAV silently fall back to MP3. Pass `--verbose` to see which.

### Only the most recent N tracks

```bash
suno-dl --limit 10
```

### Custom output directory

```bash
suno-dl --output-dir ~/Documents/suno-backup
```

### Verbose run with per-track logging and progress bar

```bash
suno-dl --verbose
```

---

## Flag reference

| Flag | Default | Description |
|------|---------|-------------|
| `--output-dir DIR` | `~/Music/suno` | Local directory for downloads. Created if absent. |
| `--format FORMAT` | `mp3` | `mp3` or `wav`. WAV silently falls back to MP3 per track. |
| `--page-delay MS` | `200` | Delay between pagination API calls (ms). |
| `--dl-delay MS` | `500` | Delay between file downloads (ms). |
| `--dry-run` | off | List tracks, write nothing. |
| `--limit N` | all | Download only the N most recent tracks. |
| `--verbose` | off | Per-track `[ok]/[skip]/[fail]` lines + `[wav→mp3]` fallback notices. |
| `--version` | — | Print version and exit. |
| `-h`, `--help` | — | Show help. |

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | All tracks downloaded or skipped successfully. |
| `1` | One or more tracks failed (e.g. CDN URL expired mid-run), or the run was interrupted with Ctrl+C. |
| `2` | Fatal error — missing/expired cookie (HTTP 401/403), invalid flag value, or unrecoverable API error. |

## Output

Filenames follow the pattern `<safe_title>_<first 8 chars of id>.<mp3|wav>`. Unicode titles are normalized to ASCII (`Café Estelar` → `Cafe_Estelar_b75f73f7.mp3`). On finish, you'll see a summary block:

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

If any tracks failed, their IDs are listed below the block.

---

## Troubleshooting

### `error: Session cookie invalid or expired. Re-extract from browser.`

Your `__session` cookie is no longer accepted. Re-extract per [the steps above](#extract-your-session-cookie) and `export SUNO_SESSION_COOKIE='...'` again.

### `error: SUNO_SESSION_COOKIE not set.`

Either you didn't export the variable in this shell, or you sourced `.env` in a different one. Confirm with:

```bash
echo "${SUNO_SESSION_COOKIE:0:4}..."
```

Should print the first 4 characters. If empty, re-export.

### A few tracks fail with `HTTP 403 from CDN`

Suno's CDN URLs are time-limited presigned URLs. If your library is very large and the run takes longer than the URL TTL, late downloads can fail mid-run. Re-run the command; the API will hand out fresh URLs and resume picks up only the missing tracks.

### Rate limiting

Defaults (`--page-delay 200`, `--dl-delay 500`) are conservative. If Suno starts rejecting requests, increase them. If you want to go faster and Suno doesn't push back, decrease them — but be a good neighbor.

### `pip install` fails with `error: externally-managed-environment`

That's why `install.sh` uses `--break-system-packages`. If you'd rather isolate, use a virtualenv:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python suno-dl.py --help
```

### Install without sudo

If you can't or don't want to write to `/usr/local/bin`, skip step 3 of `install.sh` and run the script directly:

```bash
pip install -r requirements.txt --break-system-packages
chmod +x suno-dl.py
./suno-dl.py --help
```

Or symlink to a directory you own that's already on `$PATH`:

```bash
ln -sf "$(pwd)/suno-dl.py" ~/.local/bin/suno-dl
```

---

## Caveats

`suno-dl` uses Suno's **internal** API — the same endpoints the web app uses. Suno doesn't publish a public API, so endpoints may change without notice and the tool can stop working until updated. The session cookie is read from an environment variable only; it's never written to disk by this tool.

## Documentation

- [SPEC.md](./SPEC.md) — behavior specification (source of truth)
- [CLAUDE.md](./CLAUDE.md) — implementation guide
- [CHANGELOG.md](./CHANGELOG.md) — release notes

## License

[MIT](./LICENSE) © 2026 John Martinez
