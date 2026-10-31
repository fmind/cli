---
name: release
description: Release the fmind CLI and publish fmind to PyPI, from a curated changelog through PyPI provenance proof. Use for "release cli", "publish fmind to PyPI", or a new vX.Y.Z tag, and only when the owner explicitly authorizes the release.
license: MIT
metadata:
  author: Médéric HURIER (Fmind)
---

# Release

Commit, push, tag, the `pypi` deployment approval, and the GitHub release each need the owner's authorization; reuse authorization already given, and never treat a green gate as permission. Published versions and tags are immutable.

1. Inspect `git status`, `main` against `origin/main`, local and remote tags (`git ls-remote --tags origin`), and the latest PyPI version (`curl -fsS https://pypi.org/pypi/fmind/json | jq -r .info.version`). Include only reviewed work.
1. Use the owner's version; otherwise derive it with `git-cliff --config ~/.config/git-cliff/cliff.toml --unreleased --bumped-version`. A removed command, option, or `--json` field is a major release and needs a README `Migration to X.0.0` note.
1. Set the version with `uv version X.Y.Z`, which updates `pyproject.toml` and `uv.lock`.
1. Curate `CHANGELOG.md` by hand. Either rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` (UTC date), or draft the section with `git-cliff --config ~/.config/git-cliff/cliff.toml --unreleased --tag vX.Y.Z --prepend CHANGELOG.md` and rewrite it. Never run `git-cliff -o` or `--bump -o`: they regenerate the whole file and overwrite earlier curated notes. Keep user-facing bullets under the existing section names, drop internal refactor, docs, and CI entries, and on a retry replace the section instead of adding another.
1. Run `mise run all` and `mise run smoke`. Both must pass without warnings; a smoke failure means the website and CLI contract changed, so fix it before releasing.
1. Review the diff, commit only the release metadata as `chore(release): vX.Y.Z`, and push `main`.
1. Wait for CI on that exact commit: `sha=$(git rev-parse HEAD)`, `gh run list --workflow ci.yml --commit "$sha" --json databaseId,status,conclusion`, then `gh run watch <run-id> --exit-status`. Every job must succeed: the canonical gate, the Python matrix, and the lowest-direct floors.
1. Create the annotated tag on that commit and push it without force: `git tag -m vX.Y.Z vX.Y.Z "$sha"` and `git push origin vX.Y.Z`.
1. Find the CD run with `gh run list --workflow cd.yml --commit "$sha"`. CD reruns CI, checks that the tag matches `pyproject.toml`, runs the live smoke check, builds, and then waits for the `pypi` environment.
1. The owner approves the `pypi` deployment in the Actions UI. Only when the owner asks you to approve it, read the environment id with `gh api repos/fmind/cli/actions/runs/<run-id>/pending_deployments --jq '.[].environment.id'`, then run `gh api -X POST repos/fmind/cli/actions/runs/<run-id>/pending_deployments -F 'environment_ids[]=<id>' -f state=approved -f comment='Release vX.Y.Z'`. Watch it with `gh run watch <run-id> --exit-status`.
1. CD does not create the GitHub release. Extract the curated section and publish it:

   ```bash
   notes=$(mktemp)
   awk -v head="## [X.Y.Z]" 'index($0, head) == 1 {on = 1; next} on && /^## \[/ {exit} on' CHANGELOG.md > "$notes"
   gh release create vX.Y.Z --verify-tag --title vX.Y.Z --notes-file "$notes"
   rm "$notes"
   ```

1. Verify the release: `curl -fsS https://pypi.org/pypi/fmind/X.Y.Z/json | jq -r .info.version`; the wheel provenance with `curl -fsS -H 'Accept: application/vnd.pypi.integrity.v1+json' https://pypi.org/integrity/fmind/X.Y.Z/fmind-X.Y.Z-py3-none-any.whl/provenance | jq '.attestation_bundles[].publisher'` (repository `fmind/cli`, workflow `cd.yml`, environment `pypi`); `uvx --refresh fmind@X.Y.Z --version`; and `gh release view vX.Y.Z --json tagName,isDraft,url`.

If CD fails for a transient reason, such as a website outage during smoke, rerun it with `gh run rerun <run-id> --failed`. Otherwise never move or delete the pushed tag: fix the cause on `main` and release the next patch version.
