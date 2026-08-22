# Fork setup: default branch rename + own Docker CI/CD

Date: 2026-08-22
Status: Approved, ready for implementation plan

## Context

`phoenixTW/plane` is a fork of `makeplane/plane` (remote `upstream`). Intent:
keep custom functionality in this fork long-term rather than upstreaming it.
Currently self-hosting via the upstream OSS Docker images
(`makeplane/plane-*` on Docker Hub), which lack functionality this fork adds.
Need: this repo's own default branch, and its own CI/CD that builds and
publishes Docker images from this fork's code so self-hosted deploys run the
fork's build, not upstream's.

Current state:
- Remotes: `origin` = `git@github.com:phoenixTW/plane.git`,
  `upstream` = `git@github.com:makeplane/plane.git`.
- Only branch: `preview` (also the current GitHub default).
- `.github/workflows/build-branch.yml` builds 6 service images (web, space,
  admin, live, backend, proxy) plus an optional AIO image, and pushes to
  Docker Hub under the `makeplane` org via a reusable composite action
  (`makeplane/actions/build-push@v1.4.0`). That action hardcodes a Docker Hub
  login (`docker/login-action` with no `registry:`, i.e. defaults to
  `docker.io`) and uses makeplane's own cloud buildx endpoint
  (`makeplane/plane-dev`) and Docker Hub secrets — none of it usable here.
- Actual self-host deployment config is
  `deployments/cli/community/docker-compose.yml` (what `install.sh` sets up),
  which pulls 6 separate images: `makeplane/plane-frontend`,
  `plane-space`, `plane-admin`, `plane-live`, `plane-backend`, `plane-proxy`
  (all tagged `${APP_RELEASE:-stable}`). This fork's deploy method is this
  docker-compose flow, not the AIO single-container image.
- The AIO image (`deployments/aio/community/Dockerfile`) is itself built
  `FROM makeplane/plane-frontend`, `FROM makeplane/plane-backend`, etc. — it
  assembles the 6 published images rather than building from source. Not in
  scope: this fork doesn't use AIO.
- `feature-deployment.yml` is makeplane-internal: deploys to their k8s via
  Helm, using their `DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN` secrets and a
  `FEATURE_PREVIEW_HELM_CHART_URL` var this repo doesn't have. It cannot run
  here and would just fail red on every push.
- Several other workflows (`codeql.yml`, `copyright-check.yml`,
  `i18n-sync-check.yml`, `pull-request-build-lint-api.yml`,
  `pull-request-build-lint-web-apps.yml`, `react-doctor.yml`) trigger on
  `branches: [preview]` and are otherwise generic QA — no makeplane-infra
  dependency, just need the branch ref updated.

## Decisions

1. **Default branch**: rename `preview` → `main` on GitHub and locally. This
   fork's `main` is unrelated to upstream's default branch, which stays
   `preview` — no naming collision when syncing from `upstream`.
2. **Registry**: GHCR (`ghcr.io/phoenixtw/*`), not Docker Hub. Auth via the
   built-in `GITHUB_TOKEN` — no registry secrets to create or rotate.
3. **Images built**: the same 6 services as today (frontend, space, admin,
   live, backend, proxy). No AIO image — not this fork's deploy method.
4. **Image names**: keep `plane-<service>` suffixes for now (e.g.
   `ghcr.io/phoenixtw/plane-frontend`). A product rebrand is a separate,
   later decision — deferred so it doesn't block this setup. Renaming later
   is a one-line change to the image-name list in the workflow plus the
   compose file, not a re-architecture.
5. **Pipeline ownership**: do not reuse `makeplane/actions/build-push`. It
   hardcodes a Docker Hub login and depends on an external repo this fork
   doesn't control. Write a self-contained workflow using standard,
   widely-used actions (`docker/login-action`, `docker/setup-buildx-action`,
   `docker/metadata-action`, `docker/build-push-action`) targeting GHCR
   directly.
6. **Package visibility**: public GHCR packages. Simplest for self-host pulls
   — no pull secret needed on the deploy host. (Can be flipped to private +
   a pull secret later if needed.)
7. **Upstream sync**: keep pulling from `upstream` periodically via manual
   merge (`git fetch upstream && git merge upstream/preview`), resolving
   conflicts by hand. No automation — infrequent, needs human judgment where
   this fork's custom code touches files upstream also changes.
8. **Cleanup**: delete `feature-deployment.yml` (dead weight, makeplane-only
   infra). Update the `branches: [preview]` trigger in the other listed
   workflows to `main`.

## Design

### Branch rename

- GitHub: rename `preview` → `main` (Settings → Branches, or
  `gh api repos/phoenixTW/plane/branches/preview/rename -f new_name=main`),
  confirm it's the default branch, recreate/move any branch protection rules
  onto `main`.
- Local: `git branch -m preview main; git fetch origin; git branch -u origin/main main`.
- Update every `branches: [preview]` / `branches: - preview` reference across
  `.github/workflows/*.yml` to `main`.
- Delete `.github/workflows/feature-deployment.yml`.

### `.github/workflows/docker-build-push.yml` (new, replaces `build-branch.yml`)

- Triggers: `push` to `main`; `workflow_dispatch` for manual/backfill runs.
- Permissions: `packages: write`, `contents: read`.
- One job, matrix over the 6 services. Matrix entries carry: image name
  suffix, Dockerfile path, build context — mirroring the paths
  `build-branch.yml` already uses (e.g. `apps/web/Dockerfile.web`,
  `apps/api/Dockerfile.api` with context `./apps/api`, `apps/proxy/Dockerfile.ce`
  with context `./apps/proxy`, etc.).
- Steps per matrix leg: checkout → `docker/login-action` against `ghcr.io`
  with `${{ github.actor }}` / `${{ secrets.GITHUB_TOKEN }}` →
  `docker/setup-buildx-action` (standard `docker-container` driver,
  `linux/amd64` platform — matches this fork's current single-arch build;
  add `linux/arm64` later if ever needed) → `docker/metadata-action` to
  compute tags (`main`, `sha-<short-sha>`, `latest`) →
  `docker/build-push-action` with `push: true`, registry cache
  (`cache-from`/`cache-to: type=registry`).
- Delete/out of scope: semver release/prerelease inputs, cloud buildx
  endpoint, AIO build job, CLI-asset upload job, GitHub Release publish job —
  all specific to makeplane's release process, not this fork's "build on
  merge to main" need.
- Old `build-branch.yml` deleted (superseded).

### Deploy config

- `deployments/cli/community/docker-compose.yml`: each `image:` line changes
  from `makeplane/plane-<service>:${APP_RELEASE:-stable}` to
  `ghcr.io/phoenixtw/plane-<service>:${APP_RELEASE:-main}` (default tag
  becomes `main` since this fork isn't running a formal `stable` release
  channel yet).

### Fork maintenance

- No new tooling. `upstream` remote already exists. Document the sync
  command (`git fetch upstream && git merge upstream/preview`) in this
  repo's README or a short `CONTRIBUTING`-style note so it isn't tribal
  knowledge.

## Out of scope (explicitly deferred)

- Product rebrand / renaming images away from `plane-*`.
- AIO single-container image build.
- ARM64 builds.
- Automated/scheduled upstream sync.
- Formal semver release process (tags, GitHub Releases) for this fork.
