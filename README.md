# fmind

Read [Médéric Hurier's (Fmind)](https://www.fmind.dev/) portfolio and daily tech news from the terminal, or bridge its `/mcp` server over stdio.

[![CI](https://github.com/fmind/cli/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/fmind/cli/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/fmind?color=174EA6)](https://pypi.org/project/fmind/) [![Python](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Ffmind%2Fcli%2Fmain%2Fpyproject.toml)](https://pypi.org/project/fmind/) [![License: MIT](https://img.shields.io/badge/license-MIT-174EA6)](https://github.com/fmind/cli/blob/main/LICENSE)

<a href="https://raw.githubusercontent.com/fmind/cli/main/docs/assets/overview.svg">
  <img
    src="https://raw.githubusercontent.com/fmind/cli/main/docs/assets/overview.svg"
    alt="fmind overview: live endpoints on www.fmind.dev flow through the stateless fmind CLI to Rich terminal cards, JSON pipelines, and MCP over stdio."
    width="960"
  >
</a>

## Install

Requires Python 3.14+ and HTTPS access to `www.fmind.dev`. Run with [uv](https://docs.astral.sh/uv/) (which provisions Python 3.14+ automatically) or install persistently:

```bash
uvx fmind                     # run once (shows whoami)
uv tool install fmind         # install portfolio and news commands
uv tool install 'fmind[mcp]'  # include the stdio MCP bridge
```

## Commands

Running `fmind` with no subcommand shows `whoami`. Commands mirror the website's `/api/profile` and `/api/news` sections:

| Command                                               | Shows                                                     |
| ----------------------------------------------------- | --------------------------------------------------------- |
| `fmind whoami`                                        | Name, headline, location, experience, availability, links |
| `fmind about`                                         | Biography                                                 |
| `fmind skills`                                        | Core expertise                                            |
| `fmind experiences`                                   | Engagements in website order                              |
| `fmind certifications`                                | Certifications, PhD, and specializations                  |
| `fmind community`                                     | Ambassador and advisory roles                             |
| `fmind papers`                                        | Doctorate and peer-reviewed papers, with code links       |
| `fmind projects [--limit <n>]`                        | Open-source projects and video series, with code links    |
| `fmind sites`                                         | Interactive tools published alongside the writing         |
| `fmind articles [--limit <n>]`                        | Recent articles                                           |
| `fmind search [query...] [--tag <tag>] [--limit <n>]` | Articles matching all terms, newest first                 |
| `fmind read <slug> [--raw]`                           | Article rendered in the terminal (or raw Markdown)        |
| `fmind tags`                                          | Article tags with counts and `search --tag` hints         |
| `fmind news [query...] [--limit <n>]`                 | Daily curated links, newest edition first                 |
| `fmind hire`                                          | Services available to book                                |
| `fmind mcp`                                           | Stdio MCP bridge to `www.fmind.dev/mcp` (`fmind[mcp]`)    |

- `--limit` (`1`–`200`) bounds `articles` (`6`), `search` (`10`), `news` editions (`1`, or `10` with terms), and each `projects` list (`6`).
- `--json` works on bare `fmind` and before or after every command except `mcp`; it overrides `read --raw`.
- Global `--color` / `--no-color` (respects `NO_COLOR`) and `--version` go before the command; `-h` / `--help` works everywhere.

## Examples

`search` and `news` AND-match terms case-insensitively (`search --tag` validates against `fmind tags`; `news` also matches dates like `2026-11-06`). `read` accepts an exact or unique partial slug and pages via `$PAGER` (set `PAGER=cat` to disable).

```bash
fmind search agent security --tag MLOps --limit 3
fmind read "$(fmind articles --limit 1 --json | jq -r '.[0].slug')" --raw | glow -
fmind news --limit 7
fmind news agent security
```

### Piping

`--json` writes raw JSON to stdout and errors to stderr:

```bash
fmind articles --limit 20 --json | jq -r '.[] | "\(.date[:10])  \(.title)"'
fmind news --limit 7 --json | jq -r '.[].items[] | "\(.domain)  \(.title)"'
```

Grouped JSON keys: `whoami` (`metadata`, `experience`, `services`), `certifications` (`certifications`, `thesis`, `specializations`), `papers` (`thesis`, `papers`), `projects` (`open_source`, `youtube_series`), `news` (editions with matching `items`), and `read` (article metadata plus `slug` and `markdown`).

## MCP over stdio

Portfolio commands depend only on Typer and Rich. The optional `mcp` extra adds the [official MCP Python SDK](https://py.sdk.modelcontextprotocol.io/) to bridge `https://www.fmind.dev/mcp` over protocol-only stdio:

```json
{
  "mcpServers": {
    "fmind": {
      "command": "uvx",
      "args": ["--from", "fmind[mcp]", "fmind", "mcp"]
    }
  }
}
```

Forwards read-only tools, resources, and prompts with no local cache (`--json` rejected) and a 15s / 8 MiB limit per call.

## Development

```bash
mise install && mise run install  # toolchain, locked venv, and git hooks
mise run all                      # check, test, and build (CI gate)
mise run format                   # format Python, JSON, Markdown, TOML, YAML
mise run smoke                    # live API, article, and MCP check
```

Set `FMIND_PROFILE_URL` to target another origin for all endpoints (e.g., `FMIND_PROFILE_URL=http://127.0.0.1:8080/api/profile fmind whoami`). See [AGENTS.md](https://github.com/fmind/cli/blob/main/AGENTS.md) for invariants and release details.

[Changelog](https://github.com/fmind/cli/blob/main/CHANGELOG.md) · [Issues](https://github.com/fmind/cli/issues) · [Security](https://github.com/fmind/cli/security/policy) · [MIT License](https://github.com/fmind/cli/blob/main/LICENSE)
