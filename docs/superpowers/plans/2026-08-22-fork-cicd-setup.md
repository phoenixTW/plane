# Fork Default-Branch Rename + Own Docker CI/CD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `main` this fork's default branch, and make merges to it build and publish this fork's own Docker images to GHCR so self-hosted deploys run the fork's code instead of upstream `makeplane/plane-*` images.

**Architecture:** Rename `preview` → `main` on GitHub and locally; replace `build-branch.yml` with a lean matrix workflow that builds the 6 service images with standard `docker/*` actions and pushes to `ghcr.io/phoenixtw/*` using the built-in `GITHUB_TOKEN`; point the self-host `docker-compose.yml` at those new images; document the existing `upstream` remote as the ongoing sync path.

**Tech Stack:** GitHub Actions, Docker Buildx, GHCR (GitHub Container Registry), `gh` CLI.

**Spec:** `docs/superpowers/specs/2026-08-22-fork-cicd-setup-design.md`

## Global Constraints

- Registry: GHCR at `ghcr.io/phoenixtw/*`, not Docker Hub. (spec §Decisions 2)
- Images built: exactly `plane-frontend`, `plane-space`, `plane-admin`, `plane-live`, `plane-backend`, `plane-proxy`. No AIO image. (spec §Decisions 3)
- Image names stay `plane-<service>` — no rebrand in this plan. (spec §Decisions 4)
- No dependency on `makeplane/actions/build-push` — only standard `docker/login-action`, `docker/setup-buildx-action`, `docker/metadata-action`, `docker/build-push-action`. (spec §Decisions 5)
- GHCR packages: public visibility. (spec §Decisions 6)
- No new automation for upstream sync — manual `git fetch upstream && git merge upstream/preview`. (spec §Decisions 7)
- Auth: built-in `GITHUB_TOKEN` only — no new secrets. (spec §CI/CD pipeline design)
- Platform: `linux/amd64` only for now. (spec §Out of scope)

Two steps in this plan touch the shared GitHub repo in a way that isn't
locally reversible (branch rename; first push to `main` triggering a public
image publish). Those steps are marked **CONFIRM WITH USER FIRST** — stop
and get explicit go-ahead immediately before running them, even under
subagent-driven or inline execution.

---

### Task 1: Rename default branch, clean up dead/stale workflow refs

**Files:**
- Modify (GitHub API, not a local file): default branch name
- Modify: `.github/workflows/codeql.yml`
- Modify: `.github/workflows/copyright-check.yml`
- Modify: `.github/workflows/i18n-sync-check.yml`
- Modify: `.github/workflows/pull-request-build-lint-api.yml`
- Modify: `.github/workflows/pull-request-build-lint-web-apps.yml`
- Modify: `.github/workflows/react-doctor.yml`
- Delete: `.github/workflows/feature-deployment.yml`

**Interfaces:**
- Produces: repo default branch `main`; no other task depends on this beyond it existing before Task 2/4 land.

- [ ] **Step 1: Confirm no branch protection needs migrating**

Run: `gh api repos/phoenixTW/plane/branches/preview/protection`
Expected: `404 Branch not protected` (already verified during design — re-check
here in case it changed). If it now returns protection rules instead of
404, stop and ask the user how they want those rules to carry over to
`main` before continuing.

- [ ] **Step 2 (CONFIRM WITH USER FIRST): Rename the branch on GitHub**

This changes the shared repo's default branch and rewrites every open PR's
base branch. Get explicit confirmation, then run:

```bash
gh api repos/phoenixTW/plane/branches/preview/rename -f new_name=main
```

- [ ] **Step 3: Verify the rename**

```bash
gh api repos/phoenixTW/plane --jq .default_branch
```

Expected: `main`

- [ ] **Step 4: Update local repo to track the renamed branch**

```bash
git branch -m preview main
git fetch origin
git branch -u origin/main main
git remote set-head origin -a
```

- [ ] **Step 5: Update workflow branch triggers**

In each of these files, change the `preview` branch reference to `main`:

`.github/workflows/codeql.yml` (two occurrences, both `branches: ["preview", "canary", "master"]`):
```yaml
branches: ["main", "canary", "master"]
```

`.github/workflows/copyright-check.yml`:
```yaml
    branches:
        - "main"
```

`.github/workflows/i18n-sync-check.yml` (two occurrences):
```yaml
    branches:
      - "main"
```

`.github/workflows/pull-request-build-lint-api.yml`:
```yaml
    branches:
      - "main"
```

`.github/workflows/pull-request-build-lint-web-apps.yml`:
```yaml
    branches:
      - "main"
```

`.github/workflows/react-doctor.yml`:
```yaml
    branches: [main]
```

(Keep the existing indentation style of each file — match what's already
there, only swap the literal string `preview` for `main`.)

- [ ] **Step 6: Delete the dead makeplane-internal deploy workflow**

```bash
git rm .github/workflows/feature-deployment.yml
```

- [ ] **Step 7: Verify no remaining `preview` branch references in workflows**

```bash
grep -rn '"preview"\|: preview\|\[preview\]' .github/workflows/*.yml
```

Expected: no output (the only remaining hits, if any, should be unrelated
strings like a `canary` branch or comment text, not a `preview` branch
trigger).

- [ ] **Step 8: Commit**

```bash
git add .github/workflows
git commit -m "chore(ci): move branch triggers from preview to main, drop dead feature-deployment workflow"
```

- [ ] **Step 9 (CONFIRM WITH USER FIRST): Push to origin**

```bash
git push origin main
```

---

### Task 2: New `docker-build-push.yml` workflow (GHCR, own images)

**Files:**
- Create: `.github/workflows/docker-build-push.yml`
- Delete: `.github/workflows/build-branch.yml`

**Interfaces:**
- Consumes: nothing from Task 1 except that `main` must exist as the push trigger branch.
- Produces: 6 GHCR packages under `ghcr.io/phoenixtw/plane-{frontend,space,admin,live,backend,proxy}`, tagged `main`, `sha-<short-sha>`, `latest` — Task 3 depends on these package names existing.

- [ ] **Step 1: Write the new workflow**

Create `.github/workflows/docker-build-push.yml`:

```yaml
name: Build and Push Docker Images

on:
  push:
    branches:
      - main
  workflow_dispatch: {}

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  REGISTRY: ghcr.io
  IMAGE_OWNER: phoenixtw

permissions:
  contents: read
  packages: write

jobs:
  build-and-push:
    name: Build-Push ${{ matrix.image.name }}
    runs-on: ubuntu-22.04
    strategy:
      fail-fast: false
      matrix:
        image:
          - name: plane-frontend
            dockerfile: apps/web/Dockerfile.web
            context: .
          - name: plane-space
            dockerfile: apps/space/Dockerfile.space
            context: .
          - name: plane-admin
            dockerfile: apps/admin/Dockerfile.admin
            context: .
          - name: plane-live
            dockerfile: apps/live/Dockerfile.live
            context: .
          - name: plane-backend
            dockerfile: apps/api/Dockerfile.api
            context: ./apps/api
          - name: plane-proxy
            dockerfile: apps/proxy/Dockerfile.ce
            context: ./apps/proxy
    steps:
      - name: Checkout
        uses: actions/checkout@v6

      - name: Log in to GHCR
        uses: docker/login-action@v4.0.0
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v4.0.0

      - name: Compute image metadata
        id: meta
        uses: docker/metadata-action@v5.0.0
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_OWNER }}/${{ matrix.image.name }}
          tags: |
            type=raw,value=main
            type=sha,prefix=sha-,format=short
            type=raw,value=latest

      - name: Build and push
        uses: docker/build-push-action@v7.0.0
        with:
          context: ${{ matrix.image.context }}
          file: ${{ matrix.image.dockerfile }}
          platforms: linux/amd64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_OWNER }}/${{ matrix.image.name }}:buildcache
          cache-to: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_OWNER }}/${{ matrix.image.name }}:buildcache,mode=max
```

- [ ] **Step 2: Delete the old workflow**

```bash
git rm .github/workflows/build-branch.yml
```

- [ ] **Step 3: Validate YAML syntax locally**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/docker-build-push.yml'))" && echo OK
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/docker-build-push.yml
git commit -m "ci: replace build-branch.yml with GHCR-based docker-build-push.yml"
```

- [ ] **Step 5 (CONFIRM WITH USER FIRST): Push and trigger the pipeline**

This performs the first real build and publishes 6 public images under the
`phoenixTW` GitHub org. Get explicit confirmation, then:

```bash
git push origin main
gh workflow run docker-build-push.yml
```

- [ ] **Step 6: Watch the run and verify it goes green**

```bash
gh run watch $(gh run list --workflow=docker-build-push.yml --limit=1 --json databaseId --jq '.[0].databaseId')
```

Expected: all 6 matrix legs conclude `success`.

- [ ] **Step 7: Verify the packages exist**

```bash
gh api /orgs/phoenixtw/packages?package_type=container --jq '.[].name'
```

Expected: output includes `plane-frontend`, `plane-space`, `plane-admin`,
`plane-live`, `plane-backend`, `plane-proxy`.

---

### Task 3: Make GHCR packages public

**Files:** none (GitHub API state only)

**Interfaces:**
- Consumes: the 6 package names produced by Task 2.

- [ ] **Step 1: Set each package to public visibility**

```bash
for pkg in plane-frontend plane-space plane-admin plane-live plane-backend plane-proxy; do
  gh api --method PATCH "orgs/phoenixtw/packages/container/${pkg}" -f visibility=public
done
```

- [ ] **Step 2: Verify**

```bash
for pkg in plane-frontend plane-space plane-admin plane-live plane-backend plane-proxy; do
  gh api "orgs/phoenixtw/packages/container/${pkg}" --jq '.name + ": " + .visibility'
done
```

Expected: all 6 lines end with `: public`.

---

### Task 4: Point self-host deploy config at the new images

**Files:**
- Modify: `deployments/cli/community/docker-compose.yml`

**Interfaces:**
- Consumes: image names/tags produced by Task 2 (`ghcr.io/phoenixtw/plane-<service>:main`).

- [ ] **Step 1: Update the 6 image references**

In `deployments/cli/community/docker-compose.yml`, change each of these
lines (they currently read `makeplane/plane-<service>:${APP_RELEASE:-stable}`):

```yaml
image: ghcr.io/phoenixtw/plane-frontend:${APP_RELEASE:-main}
image: ghcr.io/phoenixtw/plane-space:${APP_RELEASE:-main}
image: ghcr.io/phoenixtw/plane-admin:${APP_RELEASE:-main}
image: ghcr.io/phoenixtw/plane-live:${APP_RELEASE:-main}
image: ghcr.io/phoenixtw/plane-backend:${APP_RELEASE:-main}
image: ghcr.io/phoenixtw/plane-proxy:${APP_RELEASE:-main}
```

(`plane-backend` appears 4 times in the file — one per service that shares
the backend image: api, worker, beat-worker, migrator. Update all 4
occurrences.)

- [ ] **Step 2: Verify no `makeplane/` image refs remain in this file**

```bash
grep -n 'makeplane/' deployments/cli/community/docker-compose.yml
```

Expected: no output.

- [ ] **Step 3: Validate compose file syntax**

```bash
docker compose -f deployments/cli/community/docker-compose.yml config --quiet
```

Expected: no error (missing `.env` values are fine — this only checks YAML/schema validity, not runtime).

- [ ] **Step 4: Commit**

```bash
git add deployments/cli/community/docker-compose.yml
git commit -m "chore(deploy): point self-host compose at ghcr.io/phoenixtw images"
```

---

### Task 5: Document the upstream sync process

**Files:**
- Modify: `CONTRIBUTING.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Add a "Syncing with upstream" section**

Append to `CONTRIBUTING.md`:

```markdown
## Syncing with upstream

This fork (`phoenixTW/plane`) keeps custom functionality that isn't
contributed back to `makeplane/plane`. To pull in upstream fixes and
features periodically:

```bash
git remote -v | grep upstream || git remote add upstream git@github.com:makeplane/plane.git
git fetch upstream
git merge upstream/preview
```

Resolve conflicts where this fork's custom code touches the same files
upstream changed, then push `main` as usual. There's no automated sync —
do this manually, on your own cadence, so conflicts get a human's judgment.
```

- [ ] **Step 2: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: document upstream sync process for this fork"
```

- [ ] **Step 3 (CONFIRM WITH USER FIRST): Push**

```bash
git push origin main
```

---

## Post-plan verification (manual, whole-plan)

- [ ] `gh api repos/phoenixTW/plane --jq .default_branch` returns `main`.
- [ ] `gh run list --workflow=docker-build-push.yml --limit=1` shows a successful run.
- [ ] All 6 packages at `github.com/phoenixTW/plane/pkgs/container/plane-<service>` are visible and public.
- [ ] `docker pull ghcr.io/phoenixtw/plane-backend:main` succeeds from a machine with no GHCR auth configured (proves public visibility works end-to-end).
