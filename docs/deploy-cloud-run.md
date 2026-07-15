# Deploy to Google Cloud Run

This guide takes you from a working local app (see [google-cloud-setup.md](google-cloud-setup.md) if you're not there yet) to a live, publicly accessible URL on Cloud Run.

**Architecture**:
- **Artifact Registry** stores your built Docker image
- **Cloud Run** runs the image as a serverless container, autoscaling from 0 to N
- **Secret Manager** holds `service-account.json` and `GOOGLE_MAPS_API_KEY` — never baked into the image, never in git

**Estimated time**: 30 minutes for a first-time setup, ~2 minutes per redeploy after that.

**Cost**: Cloud Run has a generous always-free tier (2M requests/month). For this app's expected traffic, deployment cost is $0.

---

## Prerequisites

- Completed [google-cloud-setup.md](google-cloud-setup.md) — project exists, billing enabled, Geocoding API key created, `service-account.json` downloaded
- `gcloud` CLI installed: https://cloud.google.com/sdk/docs/install
- Docker installed locally (or use Cloud Build — noted in Part 4)
- App runs cleanly locally via `uv run python app.py`

Log in and set your project once:

```
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

Replace `YOUR_PROJECT_ID` with your actual project ID (from the Cloud Console top bar). Every command below uses that project by default.

## Part 1 — Enable the deployment APIs

```
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com
```

(You already enabled Geocoding, Sheets, and Drive in the setup guide. These are new ones for deployment.)

## Part 2 — Create the Artifact Registry repo

Artifact Registry is where your Docker image lives. Create one Docker repo per project (or per app):

```
gcloud artifacts repositories create sbm-falls-map \
  --repository-format=docker \
  --location=us-central1 \
  --description="Falls prevention map Docker images"
```

Then let your local Docker push to it:

```
gcloud auth configure-docker us-central1-docker.pkg.dev
```

This writes credentials into `~/.docker/config.json` so `docker push` works against `us-central1-docker.pkg.dev/...`.

## Part 3 — Put secrets in Secret Manager

Two secrets: the sheets JSON, and the geocoding API key.

### 3a. Upload `service-account.json`

From the project root (where the file lives):

```
gcloud secrets create sbm-sheets-sa \
  --data-file=service-account.json \
  --replication-policy=automatic
```

### 3b. Upload the Geocoding API key

Pipe it in from the shell so it never lands in a file:

```
printf "YOUR_API_KEY_HERE" | gcloud secrets create sbm-geocoding-key \
  --data-file=- \
  --replication-policy=automatic
```

### 3c. Grant Cloud Run access to read the secrets

Cloud Run runs as the "default compute service account" unless you configure otherwise. Grant it access to both secrets:

```
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for SECRET in sbm-sheets-sa sbm-geocoding-key; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor"
done
```

## Part 4 — Build and push the Docker image

Two options — pick one.

### Option A: Build locally with Docker (faster iteration)

On Apple Silicon (M1/M2/M3/M4), you **must** cross-compile to `linux/amd64` — Cloud Run does not run arm64 images.

```
PROJECT_ID=$(gcloud config get-value project)
IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/sbm-falls-map/app:latest"

docker buildx build --platform linux/amd64 -t $IMAGE --push .
```

The `--push` flag builds and pushes in one step.

### Option B: Build in the cloud with Cloud Build (no local Docker needed)

```
PROJECT_ID=$(gcloud config get-value project)
IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/sbm-falls-map/app:latest"

gcloud builds submit --tag $IMAGE .
```

Cloud Build zips your source, builds the image in a GCP VM, and pushes it to Artifact Registry. Slower per build, but no Docker install required and the architecture is always right.

## Part 5 — Deploy to Cloud Run

```
PROJECT_ID=$(gcloud config get-value project)
IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/sbm-falls-map/app:latest"

gcloud run deploy sbm-falls-map \
  --image=$IMAGE \
  --region=us-central1 \
  --port=5005 \
  --allow-unauthenticated \
  --set-secrets=/app/service-account.json=sbm-sheets-sa:latest \
  --set-secrets=GOOGLE_MAPS_API_KEY=sbm-geocoding-key:latest
```

Notes on each flag:
- `--port=5005` — matches the port the app listens on in [app.py:88](../app.py#L88)
- `--allow-unauthenticated` — makes the URL publicly accessible (needed for the WordPress iframe)
- `--set-secrets=/app/service-account.json=...` — mounts the secret **as a file** at `/app/service-account.json`, which is where the app expects it ([app.py:16](../app.py#L16), inside the container's `WORKDIR=/app`)
- `--set-secrets=GOOGLE_MAPS_API_KEY=...` — mounts the secret **as an environment variable**, so `os.getenv('GOOGLE_MAPS_API_KEY')` at [app.py:20](../app.py#L20) picks it up

The command prints the service URL when done. It looks like:
```
https://sbm-falls-map-<hash>-uc.a.run.app
```

## Part 6 — Verify

Open the URL in a browser. Type "hauppauge ny" and search. If markers render and nearby locations appear as cards, both secrets are wired correctly.

If something's off, check the logs:

```
gcloud run services logs read sbm-falls-map --region=us-central1 --limit=50
```

Common failures:
- **`FileNotFoundError: service-account.json`** → the `--set-secrets` mount path is wrong. It must be `/app/service-account.json` (the app runs from `WORKDIR=/app` in the container).
- **`SpreadsheetNotFound`** → the service account email hasn't been added as a Viewer to the Google Sheet. See Part 5c of [google-cloud-setup.md](google-cloud-setup.md).
- **`REQUEST_DENIED` from Google** → the API key restriction is wrong, or the key wasn't picked up from Secret Manager. Check `gcloud run services describe sbm-falls-map --region=us-central1 --format="value(spec.template.spec.containers[0].env)"`.
- **Container fails to start with "port 8080" error** → you forgot `--port=5005`. Cloud Run defaults to expecting port 8080 if you omit the flag.

## Part 7 — Redeploy after changes

For **code or Dockerfile changes**: rebuild and redeploy.

```
PROJECT_ID=$(gcloud config get-value project)
IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/sbm-falls-map/app:latest"

docker buildx build --platform linux/amd64 -t $IMAGE --push .
gcloud run deploy sbm-falls-map --image=$IMAGE --region=us-central1
```

The second command re-uses the flags from the previous deploy (secrets, port, etc.) — you don't need to re-specify them unless you're changing them.

For **rotating a secret** (e.g., new API key):

```
printf "NEW_KEY_VALUE" | gcloud secrets versions add sbm-geocoding-key --data-file=-
gcloud run services update sbm-falls-map --region=us-central1 \
  --update-secrets=GOOGLE_MAPS_API_KEY=sbm-geocoding-key:latest
```

Same pattern works for `sbm-sheets-sa` if you generate a new service account JSON.

## Part 8 — Cleanup (if you want to tear down)

Order matters — delete the service before the image, or you'll get orphaned resources:

```
gcloud run services delete sbm-falls-map --region=us-central1
gcloud artifacts repositories delete sbm-falls-map --location=us-central1
gcloud secrets delete sbm-sheets-sa
gcloud secrets delete sbm-geocoding-key
```

## Appendix: why not bake credentials into the image?

The old workflow was to copy `service-account.json` and `.env` into the Docker image at build time. Two problems:
1. Anyone with pull access to the registry has your credentials — every image layer is inspectable.
2. Rotating a credential means rebuilding + redeploying instead of a one-line `secrets versions add`.

The Secret Manager approach in Part 3 fixes both. The `.gitignore` and `.dockerignore` should ensure neither file ever enters the image in the first place — verify by running `docker run --rm YOUR_IMAGE ls /app` and confirming `service-account.json` is *not* listed. (It should only appear at runtime via the Cloud Run mount.)
