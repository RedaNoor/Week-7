---
noteId: "c8903e10c07c11f19a7c936a61417884"
tags: []

---

# SETUP.md — Run this project locally in under 10 minutes

This guide gets all three parts running on your machine:
- **Backend** (FastAPI) on port 8000
- **Website** (Next.js) on port 3000
- **ML dashboard** (Streamlit) on port 8501

---

## Step 1 — Prerequisites

Make sure you have these installed:

| Tool | Minimum version | Download |
|---|---|---|
| Python | 3.11 | https://python.org/downloads |
| Node.js | 20 | https://nodejs.org |
| Git | any | https://git-scm.com |

You'll also need:
- A **PostgreSQL** database URL — [Neon](https://neon.tech) gives you a free one in 30 seconds
- An **OpenAI API key** — https://platform.openai.com/api-keys

---

## Step 2 — Get the code

```bash
git clone <your-repo-url>
cd "Week 7"
```

---

## Step 3 — Set up the backend

### 3a. Create a Python virtual environment

```bash
# Windows
python -m venv backend\venv
backend\venv\Scripts\activate

# Mac / Linux
python3 -m venv backend/venv
source backend/venv/bin/activate
```

### 3b. Install Python packages

```bash
pip install -r backend/requirements.txt
```

This installs FastAPI, LangGraph, scikit-learn, pandas, Streamlit, and everything else needed.

### 3c. Create the backend `.env` file

```bash
# Windows
copy backend\.env.example backend\.env

# Mac / Linux
cp backend/.env.example backend/.env
```

Open `backend/.env` and fill in:

```
# Required
OPENAI_API_KEY=sk-...your key here...
DATABASE_URL=postgresql://...your Neon connection string...
API_KEY=pick-any-long-random-string
ADMIN_API_KEY=pick-a-different-long-random-string
TRUSTED_ORIGINS=http://localhost:3000,http://localhost:5173

# Optional — for email confirmations
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your-gmail@gmail.com
SMTP_PASSWORD=your-gmail-app-password
SMTP_FROM=your-gmail@gmail.com
DEFAULT_RECIPIENT_EMAIL=your-gmail@gmail.com

# Optional — for voice calls
VAPI_API_KEY=your-vapi-key
VAPI_ASSISTANT_ID=your-assistant-id
```

> **Gmail app password**: Go to Google Account → Security → 2-Step Verification → App passwords. Generate a password for "Mail".

### 3d. Start the backend

From the **project root** (not inside `backend/`):

```bash
uvicorn backend.app.main:app --reload --port 8000
```

Wait for:
```
INFO: Application startup complete.
```

Test it: open http://localhost:8000/health in your browser. You should see `{"status": "ok", ...}`.

Full API docs: http://localhost:8000/docs

---

## Step 4 — Set up the frontend

Open a **new terminal** (keep the backend running).

### 4a. Install Node packages

```bash
npm install
```

### 4b. Create the frontend `.env.local` file

```bash
# Windows
copy .env.example .env.local

# Mac / Linux
cp .env.example .env.local
```

Open `.env.local` and set:

```
BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=pick-any-long-random-string
```

> `NEXT_PUBLIC_API_KEY` must be the **same value** as `API_KEY` in `backend/.env`.

### 4c. Start the frontend

```bash
npm run dev
```

Open http://localhost:3000 — the website is live!

---

## Step 5 — Start the ML dashboard (optional)

Open a **third terminal** with the virtual environment active.

```bash
# Windows
backend\venv\Scripts\activate

# Mac / Linux
source backend/venv/bin/activate

streamlit run dashboard_week8.py --server.port 8501
```

Open http://localhost:8501 — the ML analytics dashboard is live.

---

## All three running

| Service | URL | Purpose |
|---|---|---|
| Backend API | http://localhost:8000 | REST API + AI agent |
| API Docs | http://localhost:8000/docs | Interactive Swagger UI |
| Website | http://localhost:3000 | Customer-facing frontend |
| ML Dashboard | http://localhost:8501 | Analytics & ML monitoring |

---

## Common issues

### "ModuleNotFoundError: No module named 'app'"
Make sure you run uvicorn from the project root (not from inside `backend/`):
```bash
# Wrong
cd backend && uvicorn app.main:app

# Right (from project root)
uvicorn backend.app.main:app --reload --port 8000
```

### "psycopg2 not found" on Windows
Install the binary version:
```bash
pip install psycopg2-binary
```

### Backend starts but chat gives errors
Check that `OPENAI_API_KEY` is set correctly in `backend/.env`. The agent uses it for every conversation.

### "502 Backend unreachable" on the website
The frontend can't reach the backend. Make sure:
1. The backend is running on port 8000
2. `BACKEND_URL=http://localhost:8000` is in `.env.local`
3. You ran `npm run dev` (not `npm run build`)

### ML model takes a long time to first respond
On first request, the ML service trains on `dataset_properties.csv` (168k rows). This can take 30-60 seconds. Subsequent requests are instant. To skip training, place a pre-trained bundle at `backend/data/week8/models/model_bundle.joblib`.

---

## Useful scripts

```bash
# Seed the AI agent with sample conversations
python scripts/seed_conversations.py

# Prepare the Week 8 ML dataset (generates leads.csv)
python scripts/prepare_week8_data.py

# Evaluate ML model accuracy
python scripts/week8_evaluate.py

# Check for data/prediction drift
python scripts/week8_drift.py

# Retrain and save model bundle
python scripts/week8_retrain.py
```

---

## Stopping everything

Press `Ctrl+C` in each terminal window to stop the backend, frontend, and dashboard.
