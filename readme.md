# Basic Flask - Maps - Google Sheets Web Application

## Description
Flask web app that reads location data from a Google Sheet and displays it on an interactive map. Users can enter a location or zipcode, and the app returns nearby sites sorted by distance.

The map is rendered with [Folium](https://python-visualization.github.io/folium/) (which wraps Leaflet.js — **not** Google Maps). The only Google-billed service is the **Geocoding API**, used to turn the user's typed location into lat/lng.

## Local development (uv + Python 3.14)

This project uses [uv](https://docs.astral.sh/uv/) for environment and dependency management, and targets Python 3.14.

### 1. Install uv (once per machine)
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install Python 3.14 (uv manages it — no system install needed)
```
uv python install 3.14
```

### 3. Sync dependencies
From the project root:
```
uv sync
```
This creates `.venv/` and installs everything pinned in `uv.lock`. Commit `uv.lock` for reproducible builds.

### 4. Create your `.env`
```
GOOGLE_MAPS_API_KEY=your_key_here
```
Also drop the Google service-account JSON, renamed to `service-account.json`, in the project root. Both are gitignored.

### 5. Run the app
```
uv run python app.py
```
Then open http://localhost:5005.

### Adding / removing deps
```
uv add <package>
uv remove <package>
```
This updates `pyproject.toml` and `uv.lock` together.

## Google setup

**New to the project? Start here:** [docs/google-cloud-setup.md](docs/google-cloud-setup.md) — full walkthrough of creating the GCP project, enabling the Geocoding API, restricting the API key, and setting up the Sheets service account.

Quick reference:
- The app needs **two** Google credentials: a Geocoding API key (in `.env`) and a Sheets service account JSON (in the project root).
- Share your Google Sheet with the service account's `client_email` — otherwise `gspread` raises `SpreadsheetNotFound`.
- Current sheet (hantsawilliams@gmail.com): [link](https://docs.google.com/spreadsheets/d/1IQe_EHFO-LmR89WRVZDaTHfR4ybwL0DukCT4m3iN8Dk/edit?gid=0#gid=0)
- gspread docs: https://docs.gspread.org/en/latest/oauth2.html#enable-api-access-for-a-project

## Embedding into WordPress
Embed via iframe on any page (switch to the HTML editor):
```html
<iframe src="https://sbm-falls-map-714433739872.us-central1.run.app/" width="100%" height="800px"></iframe>
```

## Deployment
Full walkthrough: [docs/deploy-cloud-run.md](docs/deploy-cloud-run.md) — Artifact Registry, Secret Manager, and Cloud Run in ~30 minutes for a first deploy. The `Dockerfile` uses uv in a multi-stage build so production installs the exact versions from `uv.lock`.
