---
name: release
description: "Release the fmind CLI to PyPI and GitHub Releases when the owner authorizes a release or vX.Y.Z tag."
license: MIT
metadata:
  kind: task
  author: Médéric HURIER (Fmind)
  source: github.com/fmind/cli/tree/main/.agents/skills/release
  created: "2026-10-31"
  updated: "2026-11-22"
---

# Release

One owner instruction to release authorizes the end-to-end flow: bump metadata, qualify locally, push `main`, wait for CI, tag `vX.Y.Z`, watch CD, and verify PyPI and GitHub Releases. Never treat a green gate alone as permission; published versions and tags are immutable. Requires `git` push access, authenticated `gh`, `curl`, `jq`, and optional external `git-cliff`.

## Workflow

1. **Inspect state**: verify clean `git status`, `main` synced with `origin/main`, remote tags (`git ls-remote --tags origin`), and live PyPI (`curl -fsS https://pypi.org/pypi/fmind/json | jq -r .info.version`). Include only reviewed work.
1. **Pick version and bump**: use the owner's version or `git-cliff --unreleased --bumped-version` (removed command/option/`--json` field or higher `requires-python` is a major bump; include a `README.md` migration note for breaking changes). Run `uv version X.Y.Z` to update `pyproject.toml` and `uv.lock`.
1. **Curate `CHANGELOG.md`**: add `## [X.Y.Z] - YYYY-MM-DD` (UTC date) by hand, or draft with `git-cliff --unreleased --tag vX.Y.Z --prepend CHANGELOG.md` and edit. Never run `git-cliff -o` or `--bump -o` (overwrites past curated notes). Keep user-facing changes under existing headings and drop internal refactors, docs, and CI noise.
1. **Gate locally**: run `mise run all` and `mise run smoke` with zero warnings.
1. **Commit, push, and wait for CI**: commit only `CHANGELOG.md`, `pyproject.toml`, `uv.lock` (plus `README.md` if a breaking migration note was added) as `chore(release): vX.Y.Z`, push `main`, and wait for every `ci.yml` job (`gate`, `compat`, `lowest`) on exact `HEAD`:
   ```bash
   sha=$(git rev-parse HEAD)
   gh run list --workflow ci.yml --commit "$sha" --json databaseId,status,conclusion
   gh run watch <run-id> --exit-status
   ```
1. **Tag and watch CD**: push the annotated tag without `--force` and watch `cd.yml` (reruns CI + `smoke`, attests provenance, publishes to PyPI and GitHub Releases):
   ```bash
   git tag -m vX.Y.Z vX.Y.Z "$sha"
   git push origin refs/tags/vX.Y.Z
   gh run list --workflow cd.yml --commit "$sha" --json databaseId,status,conclusion
   gh run watch <run-id> --exit-status
   ```
1. **Verify publication**:
   - Peeled tag matches `$sha`: `git ls-remote --exit-code --tags origin refs/tags/vX.Y.Z 'refs/tags/vX.Y.Z^{}'`
   - PyPI version and PEP 740 provenance (`fmind/cli`, `cd.yml`, `pypi`): `curl -fsS https://pypi.org/pypi/fmind/X.Y.Z/json | jq -r .info.version` and `curl -fsS -H 'Accept: application/vnd.pypi.integrity.v1+json' https://pypi.org/integrity/fmind/X.Y.Z/fmind-X.Y.Z-py3-none-any.whl/provenance | jq '.attestation_bundles[].publisher'`
   - GitHub Release and artifact attestations:
     ```bash
     gh release view vX.Y.Z -R fmind/cli --json tagName,isDraft,isImmutable,assets,url
     gh release verify vX.Y.Z -R fmind/cli
     dir=$(mktemp -d)
     gh release download vX.Y.Z -R fmind/cli --dir "$dir"
     for f in "$dir"/fmind-X.Y.Z-py3-none-any.whl "$dir"/fmind-X.Y.Z.tar.gz; do
       gh attestation verify "$f" --repo fmind/cli --signer-workflow fmind/cli/.github/workflows/cd.yml --source-ref refs/tags/vX.Y.Z --source-digest "$sha"
     done
     rm -rf "$dir"
     ```
   - Live install: `uvx --refresh fmind@X.Y.Z --version`

## Gotchas

- **Recover CD without moving tags**: rerun transient failures via `gh run rerun <run-id> --failed` (`publish` sets `skip-existing: true`). Never move or delete a pushed tag; fix on `main` and cut the next patch.
