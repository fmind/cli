# AGENTS.md — cli

Thin Python CLI (`typer` + `rich`; optional `mcp` extra) that renders live documents from `www.fmind.dev` and bridges its remote `/mcp` server over stdio. It has no database, hosted server, or local cache, and **no portfolio fact is ever written down here**—new data must be published by the website first.

## Delivery

- **Pass `mise run all` before done** ([README.md](README.md#development)): `mise.toml` owns the task contract (`format`, `check`, offline `test` at `>=85%` branch coverage with warnings as errors, and `build`). Pre-commit formats staged files and runs offline `check:local`; pre-push runs `check:network` (`uv audit`) and `test`; `check:leaks:full` scans complete Git history (`security.yml`).
- **Keep live smoke out of merge gates**: `mise run smoke` (`tests/smoke.py`, `.github/workflows/compatibility.yml`) discovers CLI commands and live MCP catalogs/slugs—reporting API and MCP failures independently—on `main`, daily, and before release, never in offline `test` or PR CI.
- **Release via skill**: follow [release](.agents/skills/release/SKILL.md) (`.claude/skills` symlinks `.agents/skills`). Hand-curate `CHANGELOG.md` without regenerating past releases; CD (`cd.yml`) reruns `ci.yml` (Python 3.15 gate, 3.14 compatibility, `--resolution lowest-direct` floors) and `smoke` on `v*` tags before unattended PyPI Trusted Publishing and GitHub Release creation.

## Invariants

- **Treat upstream as sole source of truth**: fetch `https://www.fmind.dev/api/profile`, `…/api/news`, and `…/articles/<slug>.md` live on every call (`Cache-Control: no-cache`; no local cache, stale fallback, or `--refresh`). `PROFILE_SHAPE` and `NEWS_SHAPE` require only rendered keys, so newly consumed fields must be live (`mise run smoke`) before release.
- **Derive one origin**: `FMIND_PROFILE_URL` overrides the profile endpoint; news, article reads, and `/mcp` derive their origin from it.
- **Keep two base dependencies**: only `typer` and `rich` for portfolio commands; only `fmind.mcp` imports `mcp`/`mcp_types`/`httpx2` at module level (Ruff `TID253`). Raise lower bounds when `--resolution lowest-direct` fails.
- **Validate untrusted inputs and responses**: match slugs against `SLUG_PATTERN`; enforce safe HTTP(S) redirects (no credentials or HTTPS downgrade), `15s` wall-clock deadline, and `8 MiB` size cap; parse strict JSON (`MAX_DEPTH = 32`, no `NaN`/`Infinity`, valid UTF-8, no `CONTROL_PATTERN` in rendered fields) and escape controls in errors and `--json`. Use synthetic test fixtures only.
- **Fail in one line**: expected failures raise `FmindError` and exit `1` with `fmind: <what failed>` on stderr—never a traceback.
- **Keep commands and options stable and minimal**: plural list commands grouped by API sections; bare `fmind` runs `whoami`; `--limit` bounds articles, search, news (`1` default, `10` with terms), and each project list; `--json` works before or after portfolio commands (taking precedence over `read --raw`); `search --tag` validates against `fmind tags`. Preserve `experience` order without inferring current status.
- **Flush, trim, and guard paging**: flush stdout inside commands (routing Rich `BrokenPipeError` to Click) for quiet EPIPE exits; strip trailing whitespace even under forced colour; page `read` only when stdin/stdout are TTYs and terminfo knows `TERM` (not `dumb`).
- **Keep text and JSON consistent**: use terminal-default body text and a single blue accent, stack entries with `render._entry` (never `Padding`, which crops long lines), and render unwrapped URLs with `render._link`. Document JSON schema migrations (`whoami`: `metadata`/`experience`/`services`; `certifications`: `certifications`/`thesis`/`specializations`; `projects`: `open_source`/`youtube_series`; `news`: editions with matching `items`).
- **Forward MCP without caching**: keep stdio stdout protocol-only; forward remote tools, resources, and prompts without copying schemas or content; work with finite POST-only upstream (`405` on GET/HEAD without background streams), strip cache hints, bound `15s` / `8 MiB` per exchange, and propagate cancellation.

## Ownership

- `src/fmind/`: `api.py` (HTTP I/O and validation), `articles.py` and `news.py` (pure selection), `render.py` (pure Rich renderables), `cli.py` (Typer commands and exit codes), `mcp.py` (optional stdio-to-Streamable-HTTP bridge). Tests in `tests/` target the owning layer, not the seam.
