# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

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
