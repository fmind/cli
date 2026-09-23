# AGENTS.md — cli

Thin Python CLI that renders documents published by `www.fmind.dev`. It has no content of its own, no database, and no hosted server: portfolio commands fetch live documents and print them with Rich, while `fmind mcp` bridges the remote MCP server over stdio. The repository invariant is that **no portfolio fact is ever written down here** — if a command needs data, the website must publish it.

## Commands (mise)

`mise.toml` is the canonical task contract reused by Lefthook and CI. Run tasks from the repository root.

- `mise install` — install the pinned project toolchain.
- `mise run install` — frozen all-group, all-extra `uv` sync and Lefthook install.
- `mise run format` — Ruff imports/format and dprint.
- `mise run check` — lockfile, Ruff, ty, workflow lint/audit, secret scan, and dependency audit, in parallel.
- `mise run test` — offline pytest with branch coverage of at least 85%.
- `mise run smoke` — live API/article and MCP compatibility checks, run daily, on main pushes, manually, and before release; never a merge gate.
- `mise run build` — build the wheel and source distribution.
- `mise run all` — format, check, test, build. The single gate CI runs; hooks run its parts.

## Layout

Entries are in ASCII order: dotfiles, capitalized files, then lowercase paths.

- `.github/` — CI, PyPI release, scheduled secret/dependency scans, and dependency automation.
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
- `src/fmind/api.py` — fetch and validate the remote documents.
- `src/fmind/articles.py` — pure article selection: newest, matching, slug resolution.
- `src/fmind/cli.py` — Typer commands and global options; no rendering, no fetching.
- `src/fmind/mcp.py` — optional stdio bridge to the website's remote MCP server.
- `src/fmind/render.py` — Rich renderables; no I/O and no network.
- `tests/smoke.py` — the network-dependent live run behind `mise run smoke`.
- `uv.lock` — resolved Python dependency graph.

## Conventions

- **Upstream is the source of truth.** Commands read `https://www.fmind.dev/api/profile` and `…/articles/<slug>.md`. A new section means a new key published by the website first, then a command here. Never inline a fact, a date, or a URL that the profile already carries. `PROFILE_SHAPE` requires only the keys a command renders, so a field this CLI starts reading must be live on the website before the release that reads it; `mise run smoke` is that check.
- **One origin.** `FMIND_PROFILE_URL` overrides the profile endpoint, and article reads and the `/mcp` bridge derive their origin from it, so a single variable points the whole CLI at a local website.
- **Layers stay apart.** `api` does I/O, `articles` is pure selection, `render` builds renderables without I/O, `cli` wires them and owns exit codes. Tests target the layer, not the seam.
- **Failures are one line.** Every expected failure raises `FmindError` and surfaces as `fmind: <what failed>` on stderr with exit code 1. A traceback reaching the user is a bug.
- **Live data only.** Every invocation fetches from the website with HTTP cache revalidation. Do not add a local cache, stale fallback, or `--refresh`; network failures are explicit errors.
- **Untrusted input.** Slugs reach a URL, so they are matched against `SLUG_PATTERN` before use, and responses are size-bounded and shape-checked before rendering. Test fixtures use synthetic facts, not a copy of the portfolio.
- **Two dependencies.** Typer and Rich for portfolio commands. The optional `mcp` extra owns the official SDK and its typed HTTP/protocol dependencies. Adding another base dependency needs a reason that outweighs the install cost of an easter egg people run once. Lower bounds are real: CI runs the suite with `--resolution lowest-direct`, so raise a floor when that job fails.
- **Offline tests.** `mise run test` never touches the network; the live check is `mise run smoke`, run before a release.
- **Options stay few and mean one thing.** `--limit` bounds articles, search, and each project list; `--json` selects the output format; `--raw` prints an article's source. Search also accepts `--tag`, validated against the published `tags`; use `--json` piped through `jq` for other filters. A bare `fmind` shows the `whoami` card.
- **Experience status.** Preserve the published order without inferring that the first engagement is current; the profile does not publish employment dates or a current-status field.
- **Stable command names.** Commands group the website's API sections, and list commands are plural. Website navigation and design changes do not require CLI renames.
- **Output.** `--json` works before or after each portfolio command; JSON is undecorated stdout and takes precedence over `read --raw`. Root colour flags use terminal detection by default. Flush stdout inside the command so a closed reader surfaces as Click's quiet EPIPE exit, never an interpreter-shutdown warning. Redirected text is trimmed of trailing whitespace; `read` pages only when stdin and stdout are terminals.
- **Presentation.** Use terminal-default body text and a single blue accent; community and credential entries stack vertically with published links. Render links with `render._link` (never folded or cropped) and separate entries with `render._entry`, not `Padding`, which crops long lines. `whoami` JSON includes the featured `experience` list; credential JSON groups `certifications`, `thesis`, and `specializations`; project JSON groups `open_source` and `youtube_series`. Keep text and JSON information consistent and document schema migrations.
- **MCP.** Forward remote tools, resources, and prompts without copying their schemas or content. Stdio stdout is protocol-only. Disable SDK caching, bound remote responses and request duration, and propagate cancellation. Offline protocol tests use synthetic upstream data; `mise run smoke` makes a real subprocess call through the bridge.
- **Compatibility monitoring.** `.github/workflows/compatibility.yml` reuses `mise run smoke` independently of offline CI. Discover commands and MCP catalogs instead of maintaining content snapshots. Exercise tool calls, resource reads, and prompts, and report API and MCP failures independently. Content additions need no CLI release; removed or changed consumed fields need a tested client update.
- **Hooks.** Pre-commit runs `mise run check` without writing or staging files; pre-push runs `mise run test`. Run `mise run format` explicitly before committing.
- **Commits.** Conventional Commits. Releases are `v*` tags matching `pyproject.toml`; CD runs the full gate and the live smoke check before PyPI Trusted Publishing.
