---
noteId: "dadeaca0c07c11f19a7c936a61417884"
tags: []

---

# DEPLOY.md — Deploy to Railway (free hosting)

Railway is a cloud platform similar to Heroku. The free Starter plan gives you $5/month of compute — enough to run both services continuously.

This project deploys as two services:
1. **Backend** (FastAPI) — Python app in `backend/`
2. **Frontend** (Next.js) — Node.js app in the repo root

---

## Before you start

- [ ] Code is pushed to a GitHub repository
- [ ] You have a [Railway account](https://railway.app) (sign up free with GitHub)
- [ ] You have your environment variable values ready (see README.md)
- [ ] Your Neon database URL is ready

---

## Part 1 — Deploy the Backend

### 1.1 Create a new Railway project

1. Go to https://railway.app/new
2. Click **"Deploy from GitHub repo"**
3. Select your repository
4. Railway will auto-detect the project. **Don't click Deploy yet.**

### 1.2 Configure the backend service

1. Click on the service Railway created.
2. Go to **Settings** → **Root Directory** → type `backend`
3. Railway will now only look at the `backend/` folder.

### 1.3 Set environment variables

Click **Variables** → **Add** and enter these one by one:

```
APP_ENV=production
REQUIRE_AUTH=true
OPENAI_API_KEY=<your key>
DATABASE_URL=<your Neon connection string>
API_KEY=<generate: python -c "import secrets; print(secrets.token_urlsafe(32))">
ADMIN_API_KEY=<generate another one>
TRUSTED_ORIGINS=https://your-frontend.up.railway.app   ← update after step 2
LOG_LEVEL=INFO
ML_REQUIRE_ARTIFACT=false
```

Optional (for email):
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your-gmail@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-gmail@gmail.com
DEFAULT_RECIPIENT_EMAIL=your-gmail@gmail.com
```

Optional (for voice):
```
VAPI_API_KEY=<your key>
VAPI_ASSISTANT_ID=<your assistant id>
DEEPGRAM_API_KEY=<your key>
```

### 1.4 Deploy the backend

Click **Deploy**. Railway will:
1. Build a Docker image using `Dockerfile`
2. Start uvicorn on the assigned `$PORT`

Wait for the green "Active" status. Note your backend URL — it looks like:
```
https://backend-production-xxxx.up.railway.app
```

Test it: `https://your-backend.up.railway.app/health` should return `{"status": "ok"}`.

---

## Part 2 — Deploy the Frontend

### 2.1 Add a second service

In your Railway project, click **+ New** → **GitHub Repo** → same repo.

### 2.2 Configure the frontend service

1. Root Directory: leave empty (or set to `/`)
2. Railway detects Node.js and runs `npm run build` automatically via `nixpacks.toml`.

### 2.3 Set environment variables

```
BACKEND_URL=https://your-backend.up.railway.app   ← your backend URL from Part 1
NEXT_PUBLIC_API_KEY=<same value as API_KEY on the backend>
```

### 2.4 Deploy the frontend

Click **Deploy**. Your frontend URL will be something like:
```
https://frontend-production-xxxx.up.railway.app
```

---

## Part 3 — Wire them together

### 3.1 Update TRUSTED_ORIGINS on the backend

Go to your **backend service** → Variables → update:
```
TRUSTED_ORIGINS=https://your-frontend.up.railway.app
```

Railway auto-redeploys when variables change.

### 3.2 Verify

1. Open your frontend URL in a browser
2. The Properties tab should load your listings
3. Try the Chat — it should respond
4. Try booking an appointment — you should get an email

---

## Part 4 — Custom domain (optional)

1. Go to your service → Settings → Domains
2. Click **Generate Domain** for a free `*.up.railway.app` subdomain, or
3. Add your own domain and follow the DNS instructions

---

## Troubleshooting

### Build fails: "No module named psycopg2"
The Dockerfile installs `libpq-dev` which provides psycopg2 support. If you see this error, make sure `psycopg2-binary` is in `requirements.txt` (it is — version 2.9.10).

### Frontend shows "Backend unreachable"
Check that `BACKEND_URL` is set to your Railway backend URL (no trailing slash).

### Chat works locally but not on Railway
Make sure `TRUSTED_ORIGINS` on the backend includes your frontend Railway URL exactly.

### ML model trains on every startup
The model bundle is not persisted across Railway deployments by default. Either:
- Accept the ~60s cold start (safe — it just trains on startup)
- Or use Railway Volumes to persist `backend/data/week8/models/`

### Database connection errors
Make sure `DATABASE_URL` uses `sslmode=require` for Neon:
```
postgresql://neondb_owner:password@host/dbname?sslmode=require
```

---

## Cost estimate

Railway Starter plan:
- **$5/month free credit** — enough for 2 small services running 24/7
- Backend (512 MB RAM): ~$3-4/month
- Frontend (256 MB RAM): ~$1-2/month
- Total: within free credit most months

Neon database: free tier (0.5 GB) is plenty for this project.
