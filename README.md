# Meal Planning Assistant — Cloud Run (Python / Flask)

[![Google OAuth Verified](https://img.shields.io/badge/Google%20OAuth-Verified%20(General%20Use)-4285F4?logo=google&logoColor=white)](https://console.cloud.google.com/apis/credentials/consent?project=meal-planning-app-507921)
[![Cloud Run](https://img.shields.io/badge/Google%20Cloud%20Run-Deployed-34A853?logo=googlecloud&logoColor=white)](https://cloud.google.com/run)

A containerized Python / Flask web application refactored from Google Apps Script, deployed on **Google Cloud Run** (`meal-planning-app-507921`). Features AI meal planning with Google Gemini, calendar scheduling, aisle-categorized shopping lists, on-demand recipe Google Docs, and persistent favorite recipe management.

---

## Key Features

- **Google Cloud Run Deployment**: Serverless, autoscaling, containerized with Gunicorn and Python 3.12-slim.
- **Google OAuth 2.0 Web Sign-In (Verified for General Use)**: Officially verified by Google for production & general use. Users can seamlessly sign in without unverified app warnings to sync dinner events and morning **🛒 Groceries** shopping lists with personal Google Calendars, generate on-demand recipe Docs in Google Drive, and connect to `Automated_Meal_Planner_DB.json`.
- **Gemini AI Generation**: Resilient model cascade (`gemini-3.6-flash` ➔ `gemini-3.5-flash` ➔ `gemini-1.5-flash`) with structured JSON schema enforcement, automatic retry with exponential backoff on transient errors, and quick style presets (`quick`, `one_pot`, `kid_friendly`, `slow_cooker`, `high_veggie`, `comfort`).
- **Aisle-Categorized Groceries**: Automatically categorizes ingredients into 5 store departments (`🥬 Produce`, `🥩 Meat & Seafood`, `🧀 Dairy & Refrigerated`, `🥫 Pantry & Canned`, `🧂 Spices & Baking`) and consolidates duplicate items with unit math.
- **On-Demand Google Docs**: Generates formatted Google Docs for individual recipes directly from the History or Favorites tab without cluttering Google Drive.
- **Rich Matte Aesthetics**: Premium organic olive-black dark mode, glassmorphism, Outfit typography, and mobile-responsive layout.

---

## Documentation

- [Executive Summary](docs/EXECUTIVE_SUMMARY.md) — Architectural overview, code footprint, and migration milestones.
- [Executive Product Review](docs/PRODUCT_REVIEW.md) — Formal review scorecard (5.0/5) and Cloud Run ship verdict.
- [Prompt Evaluation Protocol](docs/PROMPT_EVALUATION_PROTOCOL.md) — Gemini prompt architecture, parameter flow, and safety test rubrics.
- [Refactoring Specification](spec/cloud_run_refactoring_spec.md) — Technical blueprint for the Cloud Run refactoring.

---

## File Structure

```
Google Cloud Project/Meal Planning/
├── Dockerfile                      # Production container image (Python 3.12-slim + Gunicorn)
├── .dockerignore                   # Build exclusion rules
├── .env.example                    # Template for environment configuration
├── .gitignore                      # Git ignore rules
├── README.md                       # Documentation & operational guide
├── requirements.txt                # Production Python dependencies
├── app.py                          # Flask application entry point
├── config.py                       # App settings, environment loading, constants
├── deploy.sh                       # Single-command Bash Cloud Run deployment script
├── deploy.ps1                      # Single-command PowerShell Cloud Run deployment script
├── docs/                           # Architecture and product documentation
│   ├── EXECUTIVE_SUMMARY.md        # Migration summary & milestones
│   ├── PRODUCT_REVIEW.md           # Product scorecard & ship decision
│   └── PROMPT_EVALUATION_PROTOCOL.md # AI evaluation rubric & pipeline
├── spec/                           # Architecture specifications
│   └── cloud_run_refactoring_spec.md
├── core/
│   ├── auth.py                     # Google OAuth 2.0 session manager & token refresh
│   ├── config_keys.py              # Aisle categories, tag directives, and default DB schema
│   └── exceptions.py               # Custom error classes
├── services/
│   ├── gemini_service.py           # Gemini prompt builder, structured schema & cascade
│   ├── calendar_service.py         # Google Calendar dinner and grocery event creator
│   ├── docs_service.py             # Google Docs on-demand recipe generation
│   ├── drive_service.py            # Drive folder discovery & DB file operations
│   ├── shopping_service.py         # 5-aisle categorization & ingredient consolidation
│   └── storage_service.py          # Google Drive JSON persistence & local provider
├── routes/
│   ├── views.py                    # Serves SPA index.html and auth routes (/auth/*)
│   └── api.py                      # Flask Blueprint for all 14 REST endpoints (/api/*)
├── static/
│   ├── css/styles.css              # Dark mode styling & micro-animations
│   └── js/
│       ├── api_client.js           # REST fetch client + google.script.run compatibility shim
│       └── app.js                  # State machine & DOM handlers
├── templates/
│   └── index.html                  # Jinja2 layout with Google Sign-In header
└── tests/
    ├── conftest.py                 # Pytest fixtures and sample data
    ├── test_api_routes.py          # Integration tests for /api endpoints
    ├── test_gemini_service.py      # Prompt formatting & directives tests
    ├── test_shopping_service.py    # 5-aisle categorization & deduplication tests
    └── test_storage_service.py     # Schema migration & persistence tests
```

---

## Local Development & Testing

### 1. Setup Virtual Environment
```bash
py -m venv .venv
.\.venv\Scripts\activate     # Windows PowerShell
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and populate your credentials:
```bash
cp .env.example .env
```
Key configuration items:
- `GEMINI_API_KEY`: Starter API key from Google AI Studio.
- `GOOGLE_CLIENT_ID` & `GOOGLE_CLIENT_SECRET`: OAuth 2.0 Client credentials from Google Cloud Console.
- `STORAGE_MODE`: `drive` for personal Drive persistence, or `local` for headless development.

### 3. Run Automated Tests
```bash
pytest -v
```

### 4. Run Development Server
```bash
python app.py
```
Visit `http://localhost:8080` in your browser.

---

## Google Cloud Setup & Deployment

### 1. Google Cloud OAuth Consent Screen & Verification Status
- **Verification Status**: ✅ **Google OAuth Verified (Production / In Use)** — Scopes approved for general access without unverified app warnings.
- **Publishing Status**: In production (General Availability for any Google account).
- **Console Reference**: **[GCP Console -> APIs & Services -> OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent?project=meal-planning-app-507921)**.
- **Approved OAuth Scopes**:
  - `https://www.googleapis.com/auth/calendar` (Google Calendar dinners & grocery events)
  - `https://www.googleapis.com/auth/drive.file` (App data file storage in Google Drive)
  - `https://www.googleapis.com/auth/documents` (On-demand recipe Google Docs creation)
  - `openid`, `https://www.googleapis.com/auth/userinfo.email`, `https://www.googleapis.com/auth/userinfo.profile` (User authentication)
- **Authorized Redirect URIs**:
  - Local Dev: `http://localhost:8080/auth/callback`
  - Cloud Run: `https://<YOUR-CLOUD-RUN-URL>/auth/callback`

### 2. Deploy to Cloud Run
Run the deployment script:
```bash
# PowerShell (Windows)
.\deploy.ps1

# Or Bash (Linux/macOS)
./deploy.sh
```

Or deploy directly via `gcloud`:
```bash
gcloud run deploy meal-planning-app \
    --source . \
    --project meal-planning-app-507921 \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars "PROJECT_ID=meal-planning-app-507921,STORAGE_MODE=drive"
```
