# AGENTS.md — cli

Thin Python CLI that renders documents published by `www.fmind.dev`. It has no content of its own, no database, and no server: every command fetches a live document, caches it, and prints it with Rich. The repository invariant is that **no portfolio fact is ever written down here** — if a command needs data, the website must publish it.

## Commands (mise)

`mise.toml` is the canonical task contract reused by Lefthook and CI. Run tasks from the repository root.

- `mise install` — install the pinned project toolchain.
- `mise run install` — frozen all-group `uv` sync and Lefthook install.
- `mise run format` — Ruff imports/format and dprint.
- `mise run check` — lockfile, Ruff, ty, workflow lint/audit, and secret scan, in parallel.
- `mise run test` — offline pytest with branch coverage of at least 85%.
- `mise run smoke` — network-dependent run of every command against the live site; never a merge gate.
- `mise run build` — build the wheel and source distribution.
- `mise run all` — format, check, test, build. The single gate CI runs; hooks run its parts.

## Layout

Entries are in ASCII order: dotfiles, capitalized files, then lowercase paths.

- `.github/` — CI, PyPI release, scheduled secret scan, and dependency automation.
- `.gitignore` — local and generated exclusions.
- `.python-version` — selected Python runtime version.
- `AGENTS.md` — agent instructions and repository invariants.
- `CLAUDE.md` — Claude entry point importing this file.
- `LICENSE` — MIT license.
- `README.md` — human install, commands, and development.
- `dprint.json` — JSON, Markdown, TOML, and YAML formatting.
- `lefthook.yml` — git hooks delegating to mise tasks.
- `mise.lock` — pinned mise tool checksums.
- `mise.toml` — tool versions and canonical tasks.
- `pyproject.toml` — package metadata, dependencies, Ruff, pytest, and coverage configuration.
- `src/fmind/api.py` — fetch, cache, and validate the remote documents.
- `src/fmind/articles.py` — pure article selection: newest, matching, slug resolution.
- `src/fmind/cli.py` — Typer commands and global options; no rendering, no fetching.
- `src/fmind/render.py` — Rich renderables; no I/O and no network.
- `tests/smoke.py` — the network-dependent live run behind `mise run smoke`.
- `uv.lock` — resolved Python dependency graph.

## Conventions

- **Upstream is the source of truth.** Commands read `https://www.fmind.dev/api/profile` and `…/articles/<slug>.md`. A new section means a new key published by the website first, then a command here. Never inline a fact, a date, or a URL that the profile already carries.
- **One origin.** `FMIND_PROFILE_URL` overrides the profile endpoint, and article reads derive their origin from it, so a single variable points the whole CLI at a local website.
- **Layers stay apart.** `api` does I/O, `articles` is pure selection, `render` builds renderables without I/O, `cli` wires them and owns exit codes. Tests target the layer, not the seam.
- **Failures are one line.** Every expected failure raises `FmindError` and surfaces as `fmind: <what failed>` on stderr with exit code 1. A traceback reaching the user is a bug.
- **Caches are optional.** An unwritable, stale, or corrupt cache must never break a working command; a stale copy is preferred over an error when the network fails.
- **Untrusted input.** Slugs reach a URL and a cache path, so they are matched against `SLUG_PATTERN` before use, and responses are size-bounded and shape-checked before they are cached.
- **Two dependencies.** Typer and Rich. Adding a third needs a reason that outweighs the install cost of an easter egg people run once.
- **Offline tests.** `mise run test` never touches the network; the live check is `mise run smoke`, run before a release.
- **Commits.** Conventional Commits. Releases are `v*` tags; CD publishes to PyPI through Trusted Publishing.
