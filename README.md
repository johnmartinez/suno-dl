# suno-dl

> Bulk-download a Suno Pro library to local disk.

**Status:** pre-alpha — under active development. First release targeted at `v0.1.0`.

`suno-dl` is a single-file Python CLI that authenticates with a browser-extracted Suno session cookie, paginates the internal API to enumerate every track in your library, and downloads each as MP3 (or WAV for Pro subscribers). Downloads are idempotent and resumable.

## Documentation

- [SPEC.md](./SPEC.md) — behavior specification (source of truth)
- [CLAUDE.md](./CLAUDE.md) — implementation guide
- [CHANGELOG.md](./CHANGELOG.md) — release notes

## Quickstart

_Not yet implemented. Planned usage:_

```bash
export SUNO_SESSION_COOKIE='...'   # __session value from suno.com cookies
suno-dl --output-dir ~/Music/suno
```

The cookie extraction steps and full flag reference will land with `v0.1.0`.

## Development

Implementation work is tracked as GitHub issues, one per phase (see [CLAUDE.md](./CLAUDE.md) §Implementation Order). Each phase ships as its own PR against `main`.

## License

[MIT](./LICENSE) © 2026 John Martinez
