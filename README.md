# fmind

Read [Médéric Hurier's (Fmind)](https://www.fmind.dev/) portfolio from the terminal.

```bash
uvx fmind whoami
```

## Why it stays small

Every command renders a document the website already publishes — the portfolio at [`/api/profile`](https://www.fmind.dev/api/profile) and, for `fmind read`, the Markdown source of an article at `/articles/<slug>.md`. Those are the same sources behind the site, the Atom feed, `llms.txt` and the MCP server.

This package therefore carries no copy of the portfolio and needs **no release when the website changes**: new articles, a renewed certification or a new engagement appear on the next run.

Every command fetches from the website and asks HTTP caches to revalidate. There is no local cache and no `--refresh` option. An internet connection is required: if the website cannot be read, the command reports an error instead of showing stale information.

## Commands

| Command                                     | Shows                                             |
| ------------------------------------------- | ------------------------------------------------- |
| `fmind whoami`                              | Name, current mission, availability, contact      |
| `fmind about`                               | The biography                                     |
| `fmind skills`                              | Core expertise, as published on the site          |
| `fmind experiences`                         | Engagements, current one first                    |
| `fmind community`                           | Ambassador and advisory roles                     |
| `fmind certifications`                      | Certifications, the PhD, specializations          |
| `fmind papers`                              | The doctorate and the peer-reviewed publications  |
| `fmind projects [--limit 6]`                | Open-source repositories and video series         |
| `fmind sites`                               | Interactive tools published alongside the writing |
| `fmind articles [--limit 6]`                | The most recent writing                           |
| `fmind search [query] [--tag] [--limit 10]` | Articles matching every term, newest first        |
| `fmind read <slug> [--raw]`                 | One article, rendered in the terminal             |
| `fmind hire`                                | What can be booked right now                      |

The command names are the sections of [the website's command bar](https://www.fmind.dev/), spelled the same way: what the page prints, the shell accepts.

There are three options and they mean the same thing everywhere: `--limit` bounds any listing, `--json` prints the raw section instead of prose, and `--raw` prints an article's Markdown source. Nothing filters through a flag of its own — `--json` and `jq` do that better.

`--json` works before or after the command: both `fmind --json experiences` and `fmind experiences --json` print the raw website section. Global `--color` / `--no-color` and `--version` go before the command. Colour is detected automatically, including `NO_COLOR` and redirected output. Use `fmind --help` or `fmind <command> --help` for options.

### Reading

`fmind search` matches titles, summaries, tags and slugs; terms are ANDed, so each extra word narrows the result. `--tag` restricts to one of the site's own tags.

```bash
fmind search "agent security"
fmind search --tag MLOps --limit 3
```

`fmind read` takes a slug, or enough of one to be unambiguous, and prints the article. Use `--raw` for the Markdown source.

```bash
slug="$(fmind articles --limit 1 --json | jq -r '.[0].slug')"
fmind read "$slug"
fmind read "$slug" --raw | glow -
```

### Piping

`--json` turns every command into a data source, so the portfolio composes with the rest of the shell. JSON goes to stdout without colour or prose; errors go to stderr. With `read --raw --json`, JSON takes precedence and includes the Markdown in its `markdown` field.

```bash
fmind articles --limit 20 --json | jq -r '.[] | "\(.date[:10])  \(.title)"'
fmind search agent --json | jq -r '.[].url'
fmind certifications --json | jq -r '.[] | select(.active) | .title'
```

## Install

```bash
uvx fmind whoami       # zero install
uv tool install fmind  # persistent
pipx install fmind     # alternative
```

Point it at another origin with `FMIND_PROFILE_URL` — useful against a local `mise run watch` server of the website:

```bash
FMIND_PROFILE_URL=http://127.0.0.1:8080/api/profile fmind whoami
```

Article reads and the MCP bridge follow the same origin, so one variable moves the whole CLI.

## MCP over stdio

Install the optional MCP dependencies and let your agent host launch the bridge:

```bash
uv tool install 'fmind[mcp]'
fmind mcp
```

For a host that accepts JSON configuration:

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

`fmind mcp` connects to `https://www.fmind.dev/mcp` using Streamable HTTP and forwards the website's tools, resources, and prompts over stdio. The website owns their names, schemas, and content. Set `FMIND_PROFILE_URL` in the host's environment to use `/mcp` on another website origin. No local data or response cache is used. Requests have a 15-second deadline and remote HTTP responses are limited to 8 MiB.

Stdout carries only MCP messages; startup errors go to stderr. Portfolio output flags such as `--json` do not apply to `mcp`. The bridge forwards read-only request/response operations; subscriptions and server-initiated sampling or elicitation are not advertised.

From this checkout, run `uv run --extra mcp fmind mcp`. The optional extra uses the [official MCP Python SDK](https://py.sdk.modelcontextprotocol.io/); ordinary portfolio commands still need only Typer and Rich.

## Development

```bash
mise install       # install the pinned toolchain
mise run install   # sync the locked environment and install hooks
mise run format    # ruff imports and format, dprint
mise run check     # ruff, ty, actionlint, zizmor, gitleaks, dependency audit
mise run test      # offline pytest with branch coverage
mise run smoke     # exercise every command against the live site
mise run all       # format, check, test, build — the gate CI runs
```

The pre-commit hook runs checks without changing or staging files; run `mise run format` before committing. The pre-push hook runs the offline tests. CI runs the full gate on the pinned Python and tests Python 3.11–3.13 for compatibility.

A release tag must match the version in `pyproject.toml` (for example, `v0.1.0`). CD runs the same full gate for that tag and checks the live commands before publishing through PyPI Trusted Publishing. The live smoke check is a release check, not a pull-request gate.

Commands exit with 0 on success, 1 for website or article-resolution failures, and 2 for invalid CLI usage.

## License

[MIT](LICENSE) — © 2026 Médéric Hurier (Fmind).
