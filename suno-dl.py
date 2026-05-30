#!/usr/bin/env python3
"""suno-dl — bulk-download a Suno Pro library to local disk.

See SPEC.md for the authoritative behavior specification and CLAUDE.md for
the phased implementation plan. Phases 1–3 complete: CLI + Config + paginated
track enumeration with --dry-run + Unicode-safe filename generation.
Downloads land in Phase 4.
"""
from __future__ import annotations

import dataclasses
import enum
import os
import re
import sys
import time
import unicodedata
from typing import Any

import click
import requests

__version__ = "0.1.0"

_COOKIE_ENV_VAR = "SUNO_SESSION_COOKIE"
_DEFAULT_OUTPUT_DIR = "~/Music/suno"


class ConfigError(Exception):
    """Missing required env var or invalid flag value. Fatal; exit code 2."""


class AuthError(Exception):
    """HTTP 401/403 from Suno API. Fatal; exit code 2."""


class APIError(Exception):
    """Non-200, non-auth response (or network failure) from Suno API."""


class DownloadError(Exception):
    """Per-track download failure: network error or non-200 from CDN. Non-fatal."""


class AudioFormat(str, enum.Enum):
    MP3 = "mp3"
    WAV = "wav"


class DownloadStatus(str, enum.Enum):
    DOWNLOADED = "downloaded"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclasses.dataclass(frozen=True)
class Track:
    id: str
    title: str
    audio_url: str
    wav_url: str | None
    image_url: str | None
    created_at: str
    tags: str
    metadata: dict[str, Any] = dataclasses.field(compare=False, repr=False)


@dataclasses.dataclass(frozen=True)
class DownloadResult:
    track_id: str
    title: str
    status: DownloadStatus
    path: str | None
    error: str | None


class SunoClient:
    """Read-only client for the Suno internal feed API.

    Spec: SPEC.md §3.2. Headers are sent verbatim from the spec.
    """

    BASE_URL = "https://studio-api.suno.ai"
    _USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    _REQUEST_TIMEOUT_S = 30

    def __init__(
        self,
        session_cookie: str,
        page_delay_ms: int,
        *,
        verbose: bool = False,
    ) -> None:
        self._cookie = session_cookie
        self._page_delay_ms = page_delay_ms
        self._verbose = verbose
        self._session = requests.Session()

    def _headers(self) -> dict[str, str]:
        return {
            "Cookie": f"__session={self._cookie}",
            "User-Agent": self._USER_AGENT,
            "Accept": "application/json",
        }

    def get_tracks_page(self, page: int, page_size: int = 20) -> list[Track]:
        url = f"{self.BASE_URL}/api/feed/?page={page}&page_size={page_size}"
        try:
            resp = self._session.get(
                url, headers=self._headers(), timeout=self._REQUEST_TIMEOUT_S
            )
        except requests.RequestException as e:
            raise APIError(f"network error fetching page {page}: {e}") from e

        if resp.status_code in (401, 403):
            raise AuthError(
                f"HTTP {resp.status_code} from {self.BASE_URL} — session cookie rejected"
            )
        if resp.status_code != 200:
            snippet = resp.text[:200] if self._verbose else ""
            raise APIError(
                f"HTTP {resp.status_code} on page {page}"
                + (f": {snippet}" if snippet else "")
            )

        try:
            data = resp.json()
        except ValueError as e:
            raise APIError(f"page {page} returned non-JSON body: {e}") from e

        clips = data.get("clips") or []
        if self._verbose and not clips:
            click.echo(f"[verbose] page {page}: empty clips array — pagination end", err=True)
        return [self._clip_to_track(c) for c in clips]

    @staticmethod
    def _clip_to_track(clip: dict[str, Any]) -> Track:
        tags = clip.get("tags") or clip.get("metadata", {}).get("tags") or ""
        return Track(
            id=clip["id"],
            title=clip.get("title") or "",
            audio_url=clip["audio_url"],
            wav_url=clip.get("wav_url") or None,
            image_url=clip.get("image_url") or None,
            created_at=clip.get("created_at") or "",
            tags=tags,
            metadata=clip,
        )

    def get_all_tracks(self, limit: int | None = None) -> list[Track]:
        all_tracks: list[Track] = []
        page = 0
        while True:
            if page > 0 and self._page_delay_ms > 0:
                time.sleep(self._page_delay_ms / 1000)
            tracks = self.get_tracks_page(page)
            if not tracks:
                break
            all_tracks.extend(tracks)
            if limit is not None and len(all_tracks) >= limit:
                return all_tracks[:limit]
            page += 1
        return all_tracks

    def download_file(self, url: str, dest_path: str) -> None:
        """Stream `url` to `dest_path` atomically: write to .tmp, then rename.

        Raises DownloadError on non-200, network error, or write failure.
        On DownloadError the partial .tmp is cleaned up. KeyboardInterrupt
        propagates with the .tmp left in place — Phase 6 (#6) adds a signal
        handler to clean it up on Ctrl+C.
        """
        tmp_path = f"{dest_path}.tmp"
        try:
            try:
                resp = self._session.get(
                    url,
                    headers=self._headers(),
                    stream=True,
                    timeout=self._REQUEST_TIMEOUT_S,
                )
            except requests.RequestException as e:
                raise DownloadError(f"network error: {e}") from e

            try:
                if resp.status_code != 200:
                    raise DownloadError(f"HTTP {resp.status_code} from CDN")
                try:
                    with open(tmp_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=64 * 1024):
                            if chunk:
                                f.write(chunk)
                    os.rename(tmp_path, dest_path)
                except (OSError, requests.RequestException) as e:
                    raise DownloadError(f"stream/write error: {e}") from e
            finally:
                resp.close()
        except DownloadError:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise


_UNSAFE_CHARS = re.compile(r"[^a-zA-Z0-9 _-]")
_WHITESPACE = re.compile(r"\s+")
_MAX_TITLE_CHARS = 80


class FileManager:
    """Filesystem helpers per SPEC.md §3.3.

    All methods are stateless; FileManager is grouped for clarity, not for state.
    """

    @staticmethod
    def make_output_dir(path: str) -> None:
        os.makedirs(path, exist_ok=True)

    @staticmethod
    def safe_filename(title: str, track_id: str) -> str:
        # NFKD decomposes accented chars into base+combining-mark; ASCII-encode
        # with ignore drops the combining marks and any other non-ASCII.
        ascii_title = (
            unicodedata.normalize("NFKD", title)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        cleaned = _UNSAFE_CHARS.sub("", ascii_title)
        collapsed = _WHITESPACE.sub("_", cleaned)
        # Strip leading/trailing punctuation so we don't produce "_X_id" or "X__id".
        sanitized = collapsed.strip("_-")[:_MAX_TITLE_CHARS]
        suffix = track_id[:8]
        return f"{sanitized}_{suffix}" if sanitized else f"_{suffix}"

    @staticmethod
    def file_exists(path: str) -> bool:
        return os.path.exists(path)

    @staticmethod
    def resolve_dest(output_dir: str, filename: str) -> str:
        return os.path.join(output_dir, filename)


@dataclasses.dataclass(frozen=True)
class Config:
    session_cookie: str
    output_dir: str
    format: AudioFormat
    page_delay_ms: int
    dl_delay_ms: int
    dry_run: bool
    limit: int | None
    verbose: bool


def load_config(
    *,
    output_dir: str,
    audio_format: str,
    page_delay: int,
    dl_delay: int,
    dry_run: bool,
    limit: int | None,
    verbose: bool,
) -> Config:
    cookie = os.environ.get(_COOKIE_ENV_VAR, "").strip()
    if not cookie:
        raise ConfigError(
            f"{_COOKIE_ENV_VAR} not set. Extract the __session cookie from "
            "suno.com (DevTools → Application → Cookies → suno.com → __session) "
            f"and export it: export {_COOKIE_ENV_VAR}='...'"
        )
    return Config(
        session_cookie=cookie,
        output_dir=os.path.expanduser(output_dir),
        format=AudioFormat(audio_format),
        page_delay_ms=page_delay,
        dl_delay_ms=dl_delay,
        dry_run=dry_run,
        limit=limit,
        verbose=verbose,
    )


def _redacted_cookie(cookie: str) -> str:
    n = len(cookie)
    if n <= 8:
        return f"<redacted, {n} chars>"
    return f"<redacted, {n} chars, {cookie[:2]}…{cookie[-2:]}>"


def _print_config(config: Config) -> None:
    click.echo("config:")
    click.echo(f"  session_cookie : {_redacted_cookie(config.session_cookie)}")
    click.echo(f"  output_dir     : {config.output_dir}")
    click.echo(f"  format         : {config.format.value}")
    click.echo(f"  page_delay_ms  : {config.page_delay_ms}")
    click.echo(f"  dl_delay_ms    : {config.dl_delay_ms}")
    click.echo(f"  dry_run        : {config.dry_run}")
    click.echo(f"  limit          : {config.limit}")
    click.echo(f"  verbose        : {config.verbose}")


@click.command(context_settings={"help_option_names": ["--help", "-h"]})
@click.version_option(__version__, prog_name="suno-dl")
@click.option(
    "--output-dir",
    "output_dir",
    default=_DEFAULT_OUTPUT_DIR,
    show_default=True,
    metavar="DIR",
    help="Local directory for downloads. Created if absent.",
)
@click.option(
    "--format",
    "audio_format",
    type=click.Choice([f.value for f in AudioFormat], case_sensitive=False),
    default=AudioFormat.MP3.value,
    show_default=True,
    metavar="FORMAT",
    help="Audio format: mp3 | wav.",
)
@click.option(
    "--page-delay",
    "page_delay",
    type=int,
    default=200,
    show_default=True,
    metavar="MS",
    help="Delay between pagination API calls in ms.",
)
@click.option(
    "--dl-delay",
    "dl_delay",
    type=int,
    default=500,
    show_default=True,
    metavar="MS",
    help="Delay between file downloads in ms.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Enumerate tracks and print what would be downloaded. No files written.",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    metavar="N",
    help="Download only the N most recent tracks. Default: all.",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Print per-track status as downloads complete.",
)
def main(
    output_dir: str,
    audio_format: str,
    page_delay: int,
    dl_delay: int,
    dry_run: bool,
    limit: int | None,
    verbose: bool,
) -> None:
    """Bulk-download a Suno Pro library to local disk."""
    try:
        config = load_config(
            output_dir=output_dir,
            audio_format=audio_format,
            page_delay=page_delay,
            dl_delay=dl_delay,
            dry_run=dry_run,
            limit=limit,
            verbose=verbose,
        )
    except ConfigError as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(2)

    if config.verbose:
        _print_config(config)

    client = SunoClient(
        session_cookie=config.session_cookie,
        page_delay_ms=config.page_delay_ms,
        verbose=config.verbose,
    )

    click.echo("Fetching track list from Suno...")
    try:
        tracks = client.get_all_tracks(limit=config.limit)
    except AuthError:
        click.echo(
            "error: Session cookie invalid or expired. Re-extract from browser.",
            err=True,
        )
        sys.exit(2)
    except APIError as e:
        click.echo(f"error: API request failed: {e}", err=True)
        sys.exit(2)
    click.echo(f"Found {len(tracks)} tracks.")

    if config.dry_run:
        for t in tracks:
            click.echo(f"{t.title}\t{t.id}\t{t.audio_url}")
        sys.exit(0)

    # output_dir is created here (post dry-run gate) so Scenario 3 holds:
    # a dry-run never touches the filesystem.
    FileManager.make_output_dir(config.output_dir)

    results: list[DownloadResult] = []
    for track in tracks:
        if config.format == AudioFormat.WAV and track.wav_url:
            ext = "wav"
            url = track.wav_url
        else:
            ext = "mp3"
            url = track.audio_url
        filename = FileManager.safe_filename(track.title, track.id) + "." + ext
        dest = FileManager.resolve_dest(config.output_dir, filename)

        if FileManager.file_exists(dest):
            result = DownloadResult(track.id, track.title, DownloadStatus.SKIPPED, dest, None)
            if config.verbose:
                click.echo(f"[skip] {filename}")
        else:
            try:
                client.download_file(url, dest)
                result = DownloadResult(
                    track.id, track.title, DownloadStatus.DOWNLOADED, dest, None
                )
                if config.verbose:
                    click.echo(f"[ok]   {filename}")
            except DownloadError as e:
                result = DownloadResult(
                    track.id, track.title, DownloadStatus.FAILED, None, str(e)
                )
                click.echo(f"[fail] {track.title} ({track.id[:8]}): {e}", err=True)
        results.append(result)

        if config.dl_delay_ms > 0:
            time.sleep(config.dl_delay_ms / 1000)

    # Phase 5 (#5) replaces this terse line with the formal RunSummary block
    # and tqdm progress bar.
    n_dl = sum(1 for r in results if r.status == DownloadStatus.DOWNLOADED)
    n_sk = sum(1 for r in results if r.status == DownloadStatus.SKIPPED)
    n_fail = sum(1 for r in results if r.status == DownloadStatus.FAILED)
    click.echo(f"done: {n_dl} downloaded, {n_sk} skipped, {n_fail} failed")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
