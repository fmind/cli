# fmind

Read [Médéric Hurier's (Fmind)](https://www.fmind.dev/) portfolio from the terminal.

```bash
uvx fmind whoami
```

## Why it stays small

Every command renders a document the website already publishes — the portfolio at [`/api/profile`](https://www.fmind.dev/api/profile) and, for `fmind read`, the Markdown source of an article at `/articles/<slug>.md`. Those are the same sources behind the site, the Atom feed, `llms.txt` and the MCP server.

This package therefore carries no copy of the portfolio and needs **no release when the website changes**: new articles, a renewed certification or a new engagement appear on the next run.

Responses are cached under `${XDG_CACHE_HOME:-~/.cache}/fmind/` for one hour, matching the endpoints' own `Cache-Control`. Once a cache exists the CLI also works offline, falling back to the stale copy when the network is unavailable.

## Commands

| Command                     | Shows                                             |
| --------------------------- | ------------------------------------------------- |
| `fmind whoami`              | Name, current mission, contact, availability      |
| `fmind about`               | The biography                                     |
| `fmind skills`              | Core expertise, laid out like a usage screen      |
| `fmind work`                | Engagements, current one first                    |
| `fmind community`           | Ambassador and advisory roles                     |
| `fmind cert [--verify]`     | Certifications, the PhD, specializations          |
| `fmind papers`              | The doctorate and the peer-reviewed publications  |
| `fmind project [--top 6]`   | Open-source repositories and video series         |
| `fmind sites`               | Interactive tools published alongside the writing |
| `fmind article [--limit 6]` | The most recent writing                           |
| `fmind search <query>`      | Articles matching every term, newest first        |
| `fmind read <slug> [--raw]` | One article, rendered in the terminal             |
| `fmind hire`                | What can be booked right now                      |

Global options: `--refresh` to bypass the cache, `--json` to emit the raw section, `--no-color` for pipes, `--version`.

### Reading

`fmind search` matches titles, summaries, tags and slugs; terms are ANDed, so each extra word narrows the result. `--tag` restricts to one of the site's own tags.

```bash
fmind search "agent security"
fmind search "" --tag MLOps --limit 3
```

`fmind read` takes a slug, or enough of one to be unambiguous, and prints the article. Use `--raw` for the Markdown source.

```bash
fmind read agentgateway            # resolves to agentgateway-vs-litellm
fmind read mlops-adventure-continue --raw | glow -
```

### Piping

`--json` turns every command into a data source, so the portfolio composes with the rest of the shell.

```bash
fmind --json article --limit 20 | jq -r '.[] | "\(.date[:10])  \(.title)"'
fmind --json search agent | jq -r '.[].url'
fmind --json cert --verify | jq -r '.[].title'
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

Article reads follow the same origin, so one variable moves the whole CLI.

## Development

```bash
mise install       # install the pinned toolchain
mise run install   # sync the locked environment and install hooks
mise run format    # ruff imports and format, dprint
mise run check     # ruff, ty, actionlint, zizmor, gitleaks
mise run test      # offline pytest with branch coverage
mise run smoke     # exercise every command against the live site
mise run all       # format, check, test, build — the gate CI runs
```

## License

[MIT](LICENSE) — © 2026 Médéric Hurier (Fmind).
