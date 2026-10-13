# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### 🐛 Bug Fixes

- _(api)_ Reject overflowing JSON numbers before they can become invalid `Infinity` output
- _(cli)_ Keep contact and website links complete in narrow identity cards
- _(mcp)_ Bound HTTP headers and bodies by one deadline, including legacy responses that ignore cancellation
- _(build)_ Include the MIT license text in wheels and source distributions

### 🧪 Testing

- _(smoke)_ Check every MCP catalog page and bare portfolio invocations
- _(smoke)_ Supply default parameters to the website's MCP context cost calculator

### 🧹 Miscellaneous

- _(deps)_ Upgrade the pinned tools, Python dependencies, build backend, and GitHub Actions; test Python 3.11–3.15

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
