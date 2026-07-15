# Google Cloud Setup (for Students)

This guide walks you through everything you need in Google Cloud to run this app locally or deploy it. You'll set up **two separate credentials**, and it's important to understand they are different things:

| Credential | Format | Used for | Where it lives |
|---|---|---|---|
| **Geocoding API key** | short string, e.g. `AIzaSy...` | Converting typed locations/ZIPs to lat-lng | `.env` file, as `GOOGLE_MAPS_API_KEY` |
| **Sheets service account** | JSON file, ~2 KB | Reading location data from Google Sheets | `service-account.json` in the project root |

Total time: ~20 minutes. Requires a Google account and a credit card (Google requires one on file for the free tier, but you will not be charged for this app's usage).

---

## Part 1 — Create a Google Cloud project

1. Go to https://console.cloud.google.com/
2. Top bar → project dropdown → **New Project**
3. Give it a name (e.g. `sbm-falls-map-yourname`) and click **Create**
4. Wait ~30 seconds for provisioning, then make sure the new project is selected in the top bar

## Part 2 — Enable billing (required even for free tier)

Google requires a billing account attached to the project even to use the free tier. **You will not be charged** as long as you stay under the free quotas AND set the quota caps in Part 4.

1. Left nav → **Billing** → **Link a billing account**
2. If you don't have one: **Create billing account**, add a card
3. Link it to your project

## Part 3 — Enable the Geocoding, Google Sheets, and Google Drive APIs

1. Left nav → **APIs & Services** → **Library**
2. Search "Geocoding API"
3. Click it → **Enable**
   - When enable, you MAY be prompted with a API key - if so, save it 
   - Under the next step that follows it will ask if you want to restrict it - follow the instructions under 4b in this document (only enable geocoding API)
4. Then perform this same process for  **Google Sheets API** and **Google Drive API** (needed for Part 5) — same process

## Part 4 — Create and restrict the Geocoding API key

This is the string that goes in your `.env`. Restrictions matter here — a leaked, unrestricted key on GitHub can rack up thousands of dollars of Places/Directions API charges within hours.

### 4a. Create the key

1. **APIs & Services** → **Credentials** → **+ Create Credentials** → **API key**
2. A dialog shows the new key. **Copy it now** — you'll paste it into `.env` later.
3. Click **Edit API key** on the dialog (or find the key in the Credentials list and click its name)

### 4b. Restrict what the key can call (API restrictions)

Under **API restrictions**:

1. Select **Restrict key**
2. In the dropdown, check **only** these:
   - Geocoding API
3. Click **Save**

Now even if the key leaks, an attacker can only geocode — they can't hit expensive services like Places API ($17/1k) or Directions API.

### 4c. Application restrictions

Under **Application restrictions**, select **None**.

**Why not "HTTP referrers" or "IP addresses"?**

- **HTTP referrers** would be intuitive ("only allow calls from `sbm-falls-map-*.run.app`"), but they only work when the API is called *from a browser*. Our app calls Geocoding from Flask on the server, so there is no Referer header. Setting this restriction would make geocoding fail silently in production.
- **IP addresses** would work but requires setting up a static egress IP for Cloud Run (via Cloud NAT). More infrastructure to maintain. Not worth it for this app given the quota cap in the next step.

If we ever move geocoding to the browser (client-side JS), referrer restrictions become the right choice. Until then, `None` + API restriction + quota cap is the correct combo.

### 4d. Set a daily quota cap (belt-and-suspenders against surprise billing)

1. Left nav → **APIs & Services** → **Geocoding API** → **Quotas & System Limits** tab
2. Find **Requests per day**
3. Click the pencil icon, set to **500** (or whatever ceiling you're comfortable with)
4. Save

At $5/1,000 requests, 500/day is a hard ceiling of ~$2.50/day *if* you also blow through the 10,000/month free quota. In practice you'll almost certainly stay at $0.

Also recommended: **Billing → Budgets & alerts → Create Budget**, set a $1/month threshold to get an email if anything unexpected happens.

## Part 5 — Create the Google Sheets service account

This is a *different* credential from the API key. Service accounts are "robot user" accounts that your app impersonates to read the sheet.

### 5a. Create the service account

1. **IAM & Admin** → **Service Accounts** → **+ Create Service Account**
2. Name: `sheets-reader` (or similar). Description: "reads location data for falls map app"
3. Click **Create and Continue**
4. Skip the "Grant this service account access to project" step (leave role blank) — click **Continue** → **Done**

### 5b. Download the JSON key

1. In the Service Accounts list, click the new account
2. **Keys** tab → **Add Key** → **Create new key** → **JSON** → **Create**
3. A `.json` file downloads. **This is the only copy** — Google does not store it.
4. **Rename it to `service-account.json`** and move it into the project root (same folder as `app.py`). The app expects this exact filename.

### 5c. Share the Google Sheet with the service account

Open the downloaded JSON. Find the `client_email` field. It looks like:

```json
"client_email": "sheets-reader@your-project.iam.gserviceaccount.com"
```

1. Open your Google Sheet in the browser
2. Click **Share** (top right)
3. Paste the `client_email` value into the share box
4. Set to **Viewer** access, uncheck "Notify people", click **Share**

If you skip this step, the app will throw `gspread.exceptions.SpreadsheetNotFound` at startup — even though the sheet clearly exists.

## Part 6 — Wire it into the project

### 6a. Create your `.env` file

From the project root:

```
cp .env.template .env
```

Then open `.env` and paste your Geocoding API key from Part 4:

```
GOOGLE_MAPS_API_KEY=AIzaSy...
```

### 6b. Verify the JSON is in the right place

The app loads `service-account.json` from the project root ([app.py:16](../app.py#L16)). That filename is already in `.gitignore`, so it stays out of git.

If you skipped the rename in Part 5b step 4, rename the downloaded file to `service-account.json` now.

## Part 7 — Verify it works

```
uv sync
uv run python app.py
```

Open http://localhost:5005. Type a location like "hauppauge ny" and click Search. If you see markers on the map and cards below sorted by distance, both credentials are working.

Common failures:
- **`SpreadsheetNotFound`** → you skipped Part 5c (sharing the sheet)
- **`FileNotFoundError` for the .json** → the file isn't in the project root, or the filename in `app.py` doesn't match
- **`REQUEST_DENIED` from Google** → the API key restrictions from Part 4b are too tight, OR you forgot to enable the Geocoding API in Part 3
- **Everything geocodes to `None`** → the API key is missing from `.env`, or `.env` isn't being loaded (check you ran the app from the project root)

## Follow-up: locking down who can embed the app

The API-key restrictions above protect Google spend. They do *not* prevent someone from embedding your Cloud Run URL in *their* website via an iframe.

To restrict iframe embedding to specific parent pages (e.g. your WordPress site + your Cloud Run URL), add a `Content-Security-Policy: frame-ancestors` header in Flask. This isn't set up yet — it's tracked as a future enhancement.
