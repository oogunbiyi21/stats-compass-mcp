# How a release happens

**Decided 9 October 2026, by the founder: "Yes to all 3".** Nothing ships
unless the tests pass on the exact commit being shipped. Merging a pull request
is the founder's go, so merging one that bumps the version *is* the release
go. A pull request whose tests fail cannot be merged.

**Why it changed.** Publishing used to work like this:
- `deploy.yml` published to PyPI with a stored token when a `v*` tag was
  pushed, with no tests run first;
- sessions also published by hand from a laptop, without pushing tags;
- so the MCP Registry, which only `deploy.yml` updated, stopped at 0.3.28
  while PyPI reached 0.3.33.

`deploy.yml` is gone. Its droplet deploy job had been commented out since the
droplet was shut down; it is in git history if it is ever needed.

## How it works

| Workflow | When it runs | What it does |
|---|---|---|
| `.github/workflows/ci.yml` | Every pull request, every push to `main` | Installs the package with its dev tools and runs `tests/`. The job is named **`tests`**. |
| `.github/workflows/release.yml` | After CI passes on a push to `main` | See below. |
| `.github/workflows/release.yml`, run by hand | Actions tab, with `registry_only_version` | Publishes a version PyPI already has to the MCP Registry, and skips PyPI. |
| `.github/workflows/pages.yml` | Pushes to `main` | Unchanged. |

What `release.yml` does after CI passes on `main`, step by step:
1. Builds the exact commit CI tested.
2. Stops if PyPI already has the version in `pyproject.toml`.
3. Otherwise:
   - publishes to PyPI with trusted publishing (OIDC), with no token;
   - tags the commit `v<version>`;
   - publishes the listing to the MCP Registry, with `server.json`'s version set
     from the release.

**To release:**
1. Open a pull request that bumps `version` in `pyproject.toml` and
   `__version__` in `stats_compass_mcp/__init__.py`.
2. If core moved, update the `stats-compass-core` range in `pyproject.toml` and
   run `poetry lock`. The Docker image installs from `poetry.lock`.
3. Wait for `tests` to pass.
4. Merge.

**If a step fails:** re-run the `Release` workflow. A version PyPI already has
is skipped, and an existing tag is left alone. If only the registry step failed,
run the workflow by hand with `registry_only_version`.

## One-off setup, for the founder

Do these once. Until step 1 is done, a version bump merged to `main` fails at
the publish step and ships nothing.

**1. Trusted publisher on PyPI**
1. Sign in at <https://pypi.org>.
2. Open **Your projects → stats-compass-mcp → Manage → Publishing**.
3. Under **Add a new publisher**, choose **GitHub** and enter exactly:
   - Owner: `oogunbiyi21`
   - Repository name: `stats-compass-mcp`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
4. Click **Add**.

**2. The `pypi` environment on GitHub**
1. In the repository, open **Settings → Environments → New environment**.
2. Name it `pypi`.
3. Under **Deployment branches and tags**, choose **Selected branches and tags**
   and add `main`.

**3. Make the tests required**
1. Open **Settings → Rules → Rulesets → New ruleset → New branch ruleset**.
2. Name it, set **Enforcement status** to **Active**, and target the
   **Default branch**.
3. Turn on:
   - **Require a pull request before merging**;
   - **Require status checks to pass**, then add the check **`tests`**;
   - **Block force pushes**.
4. Save.

After this, nobody, Claude sessions included, can push to `main` directly.

**4. Bring the MCP Registry up to date.** It lists 0.3.28 while PyPI has 0.3.33.
After merging this change:
1. Open **Actions → Release → Run workflow**.
2. Enter `0.3.33` as `registry_only_version`.
3. Click **Run workflow**.

That one run publishes the 0.3.33 listing. The registry only needs the latest
version, so 0.3.29 to 0.3.32 can stay unlisted.

**5. Old secrets.** Once the first trusted release has worked:
1. Delete the `PYPI_TOKEN` secret under **Settings → Secrets and variables →
   Actions**.
2. Revoke the matching token on PyPI under **Account settings → API tokens**.
