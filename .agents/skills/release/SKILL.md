---
name: release
description: "Release the fmind CLI to PyPI and GitHub Releases when the owner authorizes a release or vX.Y.Z tag."
license: MIT
metadata:
  kind: task
  author: Médéric HURIER (Fmind)
  source: github.com/fmind/cli/tree/main/.agents/skills/release
  created: "2026-10-31"
  updated: "2026-11-12"
---

# Release

One owner instruction to release authorizes the entire automated flow end-to-end (commit, push `main`, tag `vX.Y.Z`, and unattended CD publication to PyPI and GitHub Releases); never treat a green gate alone as permission. Published versions and tags are immutable.

## Workflow

1. **Inspect state**: check `git status`, `main` against `origin/main`, local and remote tags (`git ls-remote --tags origin`), and the latest PyPI version (`curl -fsS https://pypi.org/pypi/fmind/json | jq -r .info.version`). Include only reviewed work.
1. **Select version**: use the owner's version; otherwise derive it with `git-cliff --config ~/.config/git-cliff/cliff.toml --unreleased --bumped-version`. A removed command, option, or `--json` field is a major release and needs a README `Migration to X.0.0` note; raising `requires-python` is also a major SemVer bump.
1. **Bump package version**: run `uv version X.Y.Z` to update `pyproject.toml` and `uv.lock`.
1. **Curate `CHANGELOG.md` by hand**: rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` (UTC date), or draft the section with `git-cliff --config ~/.config/git-cliff/cliff.toml --unreleased --tag vX.Y.Z --prepend CHANGELOG.md` and rewrite it. Never run `git-cliff -o` or `--bump -o` (which overwrite past curated notes). Keep user-facing bullets under the existing section names, drop internal refactor, docs, and CI entries, and replace the section on retries.
1. **Gate locally**: run `mise run all` and `mise run smoke` with zero warnings; fix any website/CLI contract failure before releasing.
1. **Commit and push `main`**: review `git diff`, commit only the release metadata (`CHANGELOG.md`, `pyproject.toml`, `uv.lock`) as `chore(release): vX.Y.Z`, and push `main`.
1. **Wait for CI on `HEAD`**: run `sha=$(git rev-parse HEAD)`, locate `ci.yml` with `gh run list --workflow ci.yml --commit "$sha" --json databaseId`, and run `gh run watch <run-id> --exit-status`. Every job (`gate`, `compat`, `lowest`) must succeed.
1. **Push the annotated tag**: run `git tag -m vX.Y.Z vX.Y.Z "$sha"` and `git push origin vX.Y.Z` (never `--force`).
1. **Watch automated CD**: locate `cd.yml` with `gh run list --workflow cd.yml --commit "$sha" --json databaseId` and run `gh run watch <run-id> --exit-status`. `cd.yml` reruns `ci.yml`, checks the tag against `pyproject.toml` and `CHANGELOG.md`, runs `mise run smoke`, attests distribution provenance, publishes to PyPI (`pypi` tag-gated environment, no manual reviewer), and publishes the GitHub Release with wheel/sdist assets.
1. **Verify publication**:
   - Peeled tag SHA: `git ls-remote --exit-code --tags origin refs/tags/vX.Y.Z 'refs/tags/vX.Y.Z^{}'`
   - PyPI version: `curl -fsS https://pypi.org/pypi/fmind/X.Y.Z/json | jq -r .info.version`
   - PyPI provenance: `curl -fsS -H 'Accept: application/vnd.pypi.integrity.v1+json' https://pypi.org/integrity/fmind/X.Y.Z/fmind-X.Y.Z-py3-none-any.whl/provenance | jq '.attestation_bundles[].publisher'` (`repository: "fmind/cli"`, `workflow: "cd.yml"`, `environment: "pypi"`)
   - GitHub attestation & release: `gh release view vX.Y.Z --json tagName,isDraft,isImmutable,assets,url` and `uvx --refresh fmind@X.Y.Z --version`

## Gotchas

- **Recover transient CD failures without moving tags**: rerun transient failures (such as a brief upstream outage during `smoke` or GitHub release creation) with `gh run rerun <run-id> --failed` (`publish` sets `skip-existing: true`). Never move or delete a pushed tag; fix defects on `main` and cut the next patch version.
