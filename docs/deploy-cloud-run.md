# Deploy to Google Cloud Run

This guide takes you from a working local app (see [google-cloud-setup.md](google-cloud-setup.md) if you're not there yet) to a live, publicly accessible URL on Cloud Run.

**Architecture**:
- **Artifact Registry** stores the built Docker image
- **Cloud Run** runs the image as a serverless container, autoscaling from 0 to N
- **Secret Manager** holds `service-account.json` and `GOOGLE_MAPS_API_KEY` — never baked into the image, never in git
- **Cloud Build** (optional, recommended) rebuilds the image on every git push

**Cost**: Cloud Run has a generous always-free tier (2M requests/month). For this app's expected traffic, deployment cost is $0.

---

## Two deploy paths

Pick one. **Path A is recommended** — set it up once, and every `git push` gets deployed automatically.

- **Path A: GitHub-triggered Cloud Build** — connect the repo to Cloud Run once. Push to `main`, Cloud Build rebuilds the image, Cloud Run rolls out a new revision. This is the workflow that actually got this project deployed.
- **Path B: Manual CLI deploy** — build and push from your laptop, run `gcloud run deploy`. Useful for one-off deploys, testing, or environments where you can't connect GitHub.

Both paths share the same prerequisite setup (APIs, Artifact Registry, secrets).

---

## Shared prerequisites (do these once)

- Completed [google-cloud-setup.md](google-cloud-setup.md) — project exists, billing enabled, Geocoding API key created, `service-account.json` downloaded locally
- `gcloud` CLI installed: https://cloud.google.com/sdk/docs/install
- App runs cleanly locally via `uv run python app.py`

Log in and set your project:

```
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### S1 — Enable the deployment APIs

```
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com
```

### S2 — Create the Artifact Registry repo

Artifact Registry is where the built image lives.

**If you're going to use Path A (GitHub trigger)**, you can **skip this step** — Cloud Build auto-creates a repo called `cloud-run-source-deploy` in your chosen region the first time it runs, and pushes images tagged with the git commit SHA (e.g. `europe-west1-docker.pkg.dev/PROJECT_ID/cloud-run-source-deploy/sbm-mapsearch-google/sbm-mapsearch-google:f819c78e...`).

**If you're going with Path B (CLI)** and want a dedicated repo:
```
gcloud artifacts repositories create sbm-mapsearch-google \
  --repository-format=docker \
  --location=europe-west1 \
  --description="Falls prevention map Docker images"
```

### S3 — Put both credentials in Secret Manager

**Sheets service-account JSON:**
```
gcloud secrets create sbm-sheets-sa \
  --data-file=service-account.json \
  --replication-policy=automatic
```

**Geocoding API key** (piped in so it never lands in shell history as a file):
```
printf "YOUR_API_KEY_HERE" | gcloud secrets create sbm-geocoding-key \
  --data-file=- \
  --replication-policy=automatic
```

### S4 — Grant Cloud Run access to read both secrets

Cloud Run runs as the "default compute service account" unless you configure otherwise. Grant it access:

```
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for SECRET in sbm-sheets-sa sbm-geocoding-key; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor"
done
```

---

# Path A — GitHub-triggered Cloud Build (recommended)

Set this up once through the Console UI, then every `git push` to your chosen branch triggers a rebuild + rollout.

## A1 — Push your repo to GitHub

Make sure the current code is on GitHub with the `Dockerfile`, `pyproject.toml`, `uv.lock`, `app.py`, `templates/`, and `static/` at the repo root.

## A2 — Create the Cloud Run service and connect GitHub

1. Cloud Run → **Create Service**
2. Select **Continuously deploy from a repository (source or function)**
3. Click **Set up with Cloud Build**
   - **Repository provider**: GitHub — authorize if prompted
   - **Repository**: pick your repo
   - **Branch**: `^main$` (or whatever branch you deploy from)
   - **Build type**: **Dockerfile**
   - **Source location**: `/Dockerfile`
4. Save. You return to the service creation page.
5. **Service name**: `sbm-mapsearch-google`
6. **Region**: `europe-west1` (same as your Artifact Registry — cross-region pulls are slow and cost extra)
7. **Authentication**: **Allow unauthenticated invocations** (required for the WordPress iframe)

## A3 — Configure the container (Containers tab)

### Container port
Set to **`5005`** — matches [app.py:88](../app.py#L88).

### Variables & Secrets tab

Under **Environment variables** (plain text, top section):

| Name | Value |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_FILE` | `/secrets/service-account.json` |

Under **Secrets exposed as environment variables** (bottom section):

| Name | Secret | Version |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | `sbm-geocoding-key` | `latest` |

### Volumes tab

Add a Secret volume:
- **Volume type**: Secret
- **Volume name**: `sheets-sa-vol` (or any name)
- **Secret**: `sbm-sheets-sa`
- **Mount path**: `/secrets` — ⚠️ **NOT** `/app` (mounting at `/app` blanks out `app.py` and everything else with a tmpfs)
- Under **Specified paths for secret versions**:
  - **Path 1**: `service-account.json` — this is the filename that appears inside the mount
  - **Version 1**: `latest`

Result: the JSON file will exist at `/secrets/service-account.json` inside the container, matching the `GOOGLE_SERVICE_ACCOUNT_FILE` env var above.

## A4 — Create the service

Click **Create**. Cloud Build immediately runs and deploys. First build takes ~3 minutes.

The service URL prints when the deploy succeeds:
```
https://sbm-mapsearch-google-<hash>-uc.a.run.app
```

## A5 — Verify

Open the URL. Search "hauppauge ny". If markers render and nearby locations appear, both credentials are wired.

## A6 — Redeploy after code changes

Just:
```
git push
```

Cloud Build detects the push, rebuilds the image, and rolls out a new revision. Watch progress in Cloud Build → History or Cloud Run → your service → Revisions.

No re-configuration needed — env vars, volume mounts, and the port setting persist across revisions until you edit them.

---

# Path B — Manual CLI deploy (alternative)

For one-off deploys or when you can't use GitHub.

## B1 — Build and push the image

**On Apple Silicon**, you **must** cross-compile to `linux/amd64` — Cloud Run does not run arm64. Also disable buildx's attestation manifest, which some resolvers mishandle:

```
gcloud auth configure-docker europe-west1-docker.pkg.dev

PROJECT_ID=$(gcloud config get-value project)
IMAGE="europe-west1-docker.pkg.dev/${PROJECT_ID}/sbm-mapsearch-google/app:latest"

docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  -t $IMAGE \
  --push .
```

## B2 — Deploy

```
gcloud run deploy sbm-mapsearch-google \
  --image=$IMAGE \
  --region=europe-west1 \
  --port=5005 \
  --allow-unauthenticated \
  --set-secrets=/secrets/service-account.json=sbm-sheets-sa:latest \
  --set-secrets=GOOGLE_MAPS_API_KEY=sbm-geocoding-key:latest \
  --set-env-vars=GOOGLE_SERVICE_ACCOUNT_FILE=/secrets/service-account.json
```

Note that the CLI's `--set-secrets=/secrets/service-account.json=SECRET` is a **file-level** mount, so you can safely mount inside `/secrets` without a separate volume config. The env var still has to match.

## B3 — Redeploy after changes

```
docker buildx build --platform linux/amd64 --provenance=false --sbom=false -t $IMAGE --push .
gcloud run deploy sbm-mapsearch-google --image=$IMAGE --region=europe-west1
```

The second command reuses the flags from the previous deploy — you don't need to re-specify them unless you're changing them.

---

# Verify + troubleshoot

If the deploy succeeds but the service returns errors, check the app logs (not the system logs):

```
gcloud run services logs read sbm-mapsearch-google --region=europe-west1 --limit=50
```

## Common failures (and what actually caused them for us)

| Error | Root cause | Fix |
|---|---|---|
| `the --mount option requires BuildKit` during Cloud Build | Cloud Build's classic docker builder doesn't enable BuildKit | Don't use `--mount=type=cache` in the Dockerfile. This project's Dockerfile is already clean. |
| `python: can't open file '/app/app.py'` | Build context didn't include `app.py` — usually because Cloud Build pulled a git commit that predates the file, or a volume mounted at `/app` shadowed it | Verify latest commit is on GitHub; check that no volume mount uses `/app` as its mount path |
| `FileNotFoundError: 'service-account.json'` (no path prefix) | `GOOGLE_SERVICE_ACCOUNT_FILE` env var not set; app fell through to the local-dev default | Set the env var per Path A step A3 |
| `FileNotFoundError: '/secrets/service-account.json'` | Env var value doesn't match volume's actual mount path + Path 1 | Make sure Mount path is `/secrets` **and** Path 1 is `service-account.json` — they must combine to match the env var |
| `SpreadsheetNotFound` | New service account isn't shared on the Google Sheet | Open the sheet → Share → paste the `client_email` from `service-account.json` as Viewer |
| `REQUEST_DENIED` from Google | API key restrictions are wrong, or the key wasn't picked up from Secret Manager | See Part 4 of [google-cloud-setup.md](google-cloud-setup.md); verify with `gcloud run services describe sbm-mapsearch-google --region=europe-west1 --format="value(spec.template.spec.containers[0].env)"` |
| Container fails to start with "port 8080" error | You forgot `--port=5005` or the UI's Container port field | Cloud Run defaults to expecting port 8080 |

---

## Rotating a credential

Add a new version to the secret and update Cloud Run to point at `:latest`:

```
printf "NEW_KEY_VALUE" | gcloud secrets versions add sbm-geocoding-key --data-file=-
gcloud run services update sbm-mapsearch-google --region=europe-west1 \
  --update-secrets=GOOGLE_MAPS_API_KEY=sbm-geocoding-key:latest
```

Same pattern for `sbm-sheets-sa` if you generate a new service account JSON.

## Cleanup (if you want to tear it all down)

Order matters — delete the service before the image, or you'll get orphaned resources:

```
gcloud run services delete sbm-mapsearch-google --region=europe-west1
gcloud artifacts repositories delete sbm-mapsearch-google --location=europe-west1
gcloud secrets delete sbm-sheets-sa
gcloud secrets delete sbm-geocoding-key
```

If you also want to disconnect the GitHub trigger:
```
gcloud builds triggers list
gcloud builds triggers delete TRIGGER_ID
```

---

## Appendix: why the app reads credentials from an env var

[app.py:16-17](../app.py#L16-L17) reads the JSON path from `GOOGLE_SERVICE_ACCOUNT_FILE` with a fallback:

```python
creds_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'service-account.json')
creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
```

This is deliberate:
- **Locally**: the env var is unset, so the app reads `./service-account.json` from the project root (matches [.env.template](../.env.template))
- **Cloud Run**: the env var is set to `/secrets/service-account.json`, matching the Secret Manager volume mount

The alternative — hardcoding a single path — would either break local dev (if we hardcoded `/secrets/...`) or make the Cloud Run mount awkward (if we hardcoded `./service-account.json` and had to mount into `/app`, which breaks the app files). Env-var-driven paths let both environments work naturally.

## Appendix: why not bake credentials into the image?

The old workflow was to copy `service-account.json` and `.env` into the Docker image at build time. Two problems:
1. Anyone with pull access to the registry has your credentials — every image layer is inspectable.
2. Rotating a credential means rebuilding + redeploying instead of a one-line `secrets versions add`.

The Secret Manager approach in S3 fixes both. The `.gitignore` and [.dockerignore](../.dockerignore) ensure neither file ever enters the image in the first place — verify by running `docker run --rm YOUR_IMAGE ls /app` and confirming `service-account.json` is *not* listed. (It should only appear at runtime via the Cloud Run mount.)
