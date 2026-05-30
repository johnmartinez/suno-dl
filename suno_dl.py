#!/usr/bin/env python3
"""suno-dl — bulk-download a Suno Pro library to local disk.

See SPEC.md for the authoritative behavior specification and CLAUDE.md for
the phased implementation plan. This is the Phase 1 skeleton: CLI surface
and Config only. Pagination, downloads, and progress reporting land in
later phases.
"""
from __future__ import annotations

import dataclasses
import enum
import os
import sys

import click

__version__ = "0.1.0"

_COOKIE_ENV_VAR = "SUNO_SESSION_COOKIE"
_DEFAULT_OUTPUT_DIR = "~/Music/suno"


class ConfigError(Exception):
    """Missing required env var or invalid flag value. Fatal; exit code 2."""


class AudioFormat(str, enum.Enum):
    MP3 = "mp3"
    WAV = "wav"


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

    # Pagination, download loop, and reporting are implemented in later phases
    # (see GitHub issues #2–#7). For now Phase 1 is just the skeleton.


if __name__ == "__main__":
    main()
