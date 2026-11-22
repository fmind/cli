# AGENTS.md

Thin Python 3.14+ CLI (`typer`, `rich`; optional `mcp` extra) rendering live data from `www.fmind.dev` and bridging its `/mcp` server over stdio. Stateless with no local cache, and **no portfolio facts live in this repo** (publish new data on the website first). See [README.md](README.md) for usage.

## Commands

- **Local gates**: `mise run install` (locked `.venv` + Lefthook), `mise run format`, `mise run check` (`check:local` + `check:network`), `mise run test` (offline, `>=85%` branch coverage, warnings as errors), `mise run build`, and `mise run all` (read-only CI gate; pass before done).
- **Live smoke**: `mise run smoke` (`tests/smoke.py`) exercises live API, articles, and MCP; keep it out of offline `test` and PR CI.
- **Releases**: follow [release](.agents/skills/release/SKILL.md). Hand-curate `CHANGELOG.md` without regenerating past releases.

## Invariants

- **Single live origin**: fetch `/api/profile`, `/api/news`, and `/articles/<slug>.md` live (`Cache-Control: no-cache`, no cache or `--refresh`). `FMIND_PROFILE_URL` sets the origin for all endpoints including `/mcp`. `PROFILE_SHAPE` and `NEWS_SHAPE` check only rendered keys; newly consumed fields must be live (`mise run smoke`) before release.
- **Minimal dependencies**: keep only `typer` and `rich` in base dependencies; only `fmind.mcp` imports `mcp`, `mcp_types`, or `httpx2` at module level (Ruff `TID253`). Raise lower bounds when `--resolution lowest-direct` fails.
- **Strict boundary validation**: validate slugs, enforce safe redirects (no credentials, HTTPS downgrade, auth/cookie forwarding, or redirect body drains), close `HTTPError` responses, enforce `15s` / `8 MiB` limits, parse strict JSON (bounded depth, finite numbers, no control/bidi characters), and use synthetic test fixtures only.
- **Stable CLI contract**: raise `FmindError` for one-line `fmind: ...` stderr errors (exit `1`; usage `2`, `SIGINT` `130`, `BrokenPipeError` `1` quietly; no tracebacks). Keep commands aligned with API sections (`fmind` runs `whoami`; preserve `experience` order; `--json` works before or after portfolio commands and overrides `read --raw`; keep grouped JSON schemas synced with [README.md](README.md#piping)).
- **Clean terminal output**: flush stdout inside commands, strip trailing whitespace, page `read` only on capable TTYs, use terminal-default body text with one blue accent, avoid Rich `Padding` (crops long lines), and keep URLs unwrapped.
- **Stateless MCP bridge**: keep stdio stdout protocol-only, forward remote tools, resources, and prompts without caching (stripping cache hints), support POST-only upstream (`405` on GET/HEAD), cap redirects (`max_redirects=3`) and exchanges/handshake (`15s` / `8 MiB`), and propagate cancellation.

## Layout

- `src/fmind/`: `api.py` (HTTP and validation), `articles.py` & `news.py` (selection), `render.py` (Rich views), `cli.py` (Typer CLI), `mcp.py` (optional stdio bridge).
- `tests/`: layer-scoped unit suites (`test_{api,articles,news,render,cli,mcp,smoke}.py`) and `smoke.py`.
- `.agents/skills/release/SKILL.md`: authorized release workflow.
