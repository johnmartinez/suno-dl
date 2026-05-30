#!/usr/bin/env python3
"""suno-dl — bulk-download a Suno Pro library to local disk.

See SPEC.md for the authoritative behavior specification and CLAUDE.md for
the phased implementation plan. Phases 1–2 complete: CLI + Config + paginated
track enumeration with --dry-run. Downloads land in Phase 4.
"""
from __future__ import annotations

import dataclasses
import enum
import os
import sys
import time
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


class AudioFormat(str, enum.Enum):
    MP3 = "mp3"
    WAV = "wav"


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

    # Download loop lands in Phase 4 (#4). Until then non-dry-run is a no-op
    # after enumeration.


if __name__ == "__main__":
    main()
