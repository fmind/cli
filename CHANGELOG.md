# Changelog

All notable changes to this project are documented in this file.

## [3.0.4] - 2026-11-22

### 📚 Documentation

- _(readme)_ Simplify installation, commands, examples, piping, and MCP documentation

## [3.0.3] - 2026-11-22

### 🐛 Bug Fixes

- _(cli)_ Suppress ANSI SGR and OSC 8 escapes under `--no-color` and `NO_COLOR` (including on TTYs, in `$PAGER`, and under `FORCE_COLOR`), render plain `--help` without `<bool>` flag metavars or forced CI colour, distinguish broken MCP installs from missing `[mcp]` extras, and cut startup latency with lazy metadata and command-module imports
- _(api)_ Strip `Authorization`, `Proxy-Authorization`, and `Cookie` headers on HTTP redirects, read proxy settings at call time, reject Unicode bidirectional control characters across rendered text, Markdown, `--json`, and errors, and expose typed `TypedDict` return contracts
- _(render)_ Restrict clickable OSC 8 terminal links to printable non-whitespace ASCII and compute tag counts in a single pass
- _(mcp)_ Normalize `Content-Encoding` case-insensitively, cap HTTP redirects at 3, and bound the startup handshake by the 15s deadline

## [3.0.2] - 2026-11-22

### 🐛 Bug Fixes

- _(api)_ Close HTTP error and rejected-redirect sockets, stop draining redirect bodies into memory, and reject bare carriage returns and DEL/C1 controls in URLs and text
- _(cli)_ Support `-h` short help, reject empty `read` slugs before fetching, add `--` to dash-prefixed search hints, show truncation counts past 10 ambiguous slugs, handle `SIGINT` cleanly during pager close and exit, treat any `cat` path as unpaged, and cut startup latency with lazy imports
- _(render)_ Replace `Padding` in `about`, show an empty message when no biography is published, omit `PUBLICATIONS` when no papers are published, and guard whitespace in clickable terminal links
- _(mcp)_ Strip upstream cache hints with `model_copy` without re-serializing non-cacheable results

### 🧹 Miscellaneous

- _(deps)_ Upgrade locked Python dependencies (`typer 0.29.2`, `httpx2 2.16.2`, `pydantic 2.14.4`), ship PEP 561 typing metadata (`py.typed`), and align pinned tools and CI workflows

## [3.0.1] - 2026-11-15

### 🧹 Miscellaneous

- _(pypi)_ Publish verified repository, changelog, issue, and security policy links in package metadata and omit the unverified author email

## [3.0.0] - 2026-11-11

### 🚀 Features

- _(python)_ [**breaking**] Require Python 3.14 or newer (`uvx fmind` selects a compatible interpreter automatically)
- _(projects)_ Link each open-source project's separate code repository when its project URL points elsewhere

### 🐛 Bug Fixes

- _(read)_ Use standard ANSI colour slots for fenced code blocks so dark and light terminal themes stay readable
- _(api)_ Block cross-scheme, credentialed, and HTTPS-downgrade redirects, reject oversized `Content-Length` responses before reading the body, and validate project `repo` URLs
- _(cli)_ Route broken-pipe writes cleanly without leaking file descriptors, keep long social labels separated from URLs in `whoami`, and match the website's deterministic slug tie-break order

### 🧹 Miscellaneous

- _(deps)_ Upgrade locked Python dependencies (`typer 0.29.1`, `markdown-it-py 4.3.0`) and `mise`

## [2.1.0] - 2026-11-08

### 🚀 Features

- _(news)_ Add `fmind news [query...]` for the website's daily curated links: the latest edition by default, `--limit` editions, and search terms that keep only matching links
- _(tags)_ Add `fmind tags`, listing the article tags with their descriptions, article counts, and `search --tag` hint
- _(whoami)_ Show the secondary headline, work location, and published social profiles
- _(papers)_ Link each paper's published code repository

### 🐛 Bug Fixes

- _(smoke)_ Read a live news slug for the website's new `get_news` MCP tool, which made the compatibility check fail

### 🧹 Miscellaneous

- _(deps)_ Upgrade the pinned tools, Python dependencies, dprint plugins, and GitHub Actions; run the gate on Python 3.15 and test Python 3.11–3.14 for compatibility

## [2.0.5] - 2026-10-31

### 🐛 Bug Fixes

- _(read)_ Leave Ctrl-C to the pager so `less` restores the terminal, and print directly when `TERM` cannot drive a full-screen pager
- _(mcp)_ Keep `fmind mcp` serving when one upstream exchange fails, times out, or exceeds its bounds
- _(cli)_ Trim forced-colour output, bound JSON nesting, keep the fetched Markdown in `read --json`, and print a line for empty sections
- _(search)_ Accept unquoted multi-word queries and print a runnable `read` hint

### 🧹 Miscellaneous

- _(deps)_ Lock pydantic 2.14.2 for its validation-bypass fixes; run the full CI matrix, including Python 3.15, before publishing

## [2.0.4] - 2026-10-29

### 🐛 Bug Fixes

- _(api)_ Read the profile endpoint in one place and reject overflowing JSON numbers before they can become invalid `Infinity` output
- _(cli)_ Keep contact and website links complete in narrow identity cards
- _(mcp)_ Bound HTTP headers and bodies by one deadline, including legacy responses that ignore cancellation
- _(build)_ Include the MIT license text in wheels and source distributions

### 🧪 Testing

- _(smoke)_ Check every MCP catalog page and bare portfolio invocations

### 🧹 Miscellaneous

- _(deps)_ Upgrade the pinned tools, Python dependencies, build backend, and GitHub Actions; test Python 3.11–3.14 and keep Dependabot on security updates only

## [2.0.3] - 2026-10-06

### 🐛 Bug Fixes

- _(cli)_ Escape terminal controls and reject non-finite numbers in JSON

### 📚 Documentation

- _(readme)_ Trim internal architecture and compatibility details
- _(agents)_ Drop the CLAUDE.md shim and list the changelog

### 🧹 Miscellaneous

- _(deps)_ Upgrade mise tools to latest
- _(deps)_ Upgrade python dependencies to latest
- _(deps)_ Upgrade github actions to latest
- _(deps)_ Upgrade dprint plugins to latest

## [2.0.2] - 2026-09-25

### 🐛 Bug Fixes

- _(cli)_ Bound downloads and harden output failures

### 🧹 Miscellaneous

- _(deps)_ Upgrade uv and compatible Python dependencies

## [2.0.1] - 2026-09-23

### 📚 Documentation

- _(mcp)_ Describe request-response transport and health probes

## [2.0.0] - 2026-09-23

### 🚀 Features

- _(cli)_ [**breaking**] Group project JSON and keep links readable

### 🧹 Miscellaneous

- Format workflows and sort gitignore

## [1.0.0] - 2026-09-19

### 🚀 Features

- _(cli)_ [**breaking**] Simplify presentation and group credential JSON

### 🧪 Testing

- _(cli)_ Validate the installed release version exactly

## [0.2.0] - 2026-09-16

### 🚀 Features

- Add MCP bridge and improve live data commands

### 🐛 Bug Fixes

- Restore website compatibility and monitor live API and MCP
- Align portfolio rendering and MCP checks with website

## [0.1.0] - 2026-09-12

### 🚀 Features

- Read the fmind.dev portfolio from the terminal

### 🐛 Bug Fixes

- _(ci)_ Lock tool download URLs for linux and macOS
