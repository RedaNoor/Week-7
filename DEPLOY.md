# DEPLOY.md — Production Deployment Guide

Since Railway free trials expire, this guide provides **100% Free Forever** hosting options with no credit card required:

| Service | Best Free Host | Cost | Setup Time |
|---|---|---|---|
| **Website (Next.js)** | **[Vercel](https://vercel.com)** | Free Forever (Hobby tier) | 2 minutes |
| **Backend (FastAPI)** | **[Render](https://render.com)** | Free Forever (Web Service) | 4 minutes |
| **ML Dashboard (Streamlit)** | **[Streamlit Community Cloud](https://share.streamlit.io)** | Free Forever | 2 minutes |
| **Database (PostgreSQL)** | **[Neon](https://neon.tech)** | Free Forever | 1 minute |

---

## Prerequisites (Checklist)

- [ ] Code is pushed to your GitHub repository:
  ```bash
  git add .
  git commit -m "chore: ready for deployment"
  git push origin main
  ```
- [ ] You have created a free account on [Vercel](https://vercel.com/signup) (Sign up with GitHub).
- [ ] You have created a free account on [Render](https://render.com) (Sign up with GitHub).
- [ ] You have your Neon database connection string ready.

---

## Step 1 — Deploy the FastAPI Backend to Render (Free)

Render natively runs Python/FastAPI web services on its free tier.

### 1.1 Create the Web Service
1. Log in to your [Render Dashboard](https://dashboard.render.com).
2. Click **New +** → **Web Service**.
3. Connect your GitHub account and select your repository.
4. Fill in the service configuration:
   - **Name**: `real-estate-backend` (or your choice)
   - **Region**: Choose the closest region (e.g., Frankfurt or Oregon)
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install --no-cache-dir -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Select **Free** ($0/month)

### 1.2 Add Environment Variables
Scroll down to **Environment Variables** (or click the **Environment** tab) and add:

| Key | Value | Notes |
|---|---|---|
| `APP_ENV` | `production` | Enables production mode |
| `REQUIRE_AUTH` | `false` | Set `true` if requiring API keys |
| `OPENAI_API_KEY` | `sk-...` | Your OpenAI or OpenRouter key |
| `DATABASE_URL` | `postgresql://...` | Your Neon database connection URL |
| `VAPI_API_KEY` | `2041eb08-58e1...` | From your `.env` |
| `VAPI_ASSISTANT_ID` | `eb8a4d4b-9a92...` | From your `.env` |
| `VAPI_PUBLIC_KEY` | `2041eb08-58e1...` | From your `.env` |
| `LOG_LEVEL` | `INFO` | Standard logging |
| `ML_REQUIRE_ARTIFACT` | `false` | Allows auto-loading models |
| `TRUSTED_ORIGINS` | `*` | Or set to your Vercel URL once deployed |

*(Optional for email confirmations)*:
- `SMTP_HOST`: `smtp.gmail.com`
- `SMTP_PORT`: `465`
- `SMTP_USER`: `your-email@gmail.com`
- `SMTP_PASSWORD`: `your-gmail-app-password`

### 1.3 Deploy and Copy Backend URL
1. Click **Create Web Service**.
2. Wait 2–3 minutes for the build and deployment to finish.
3. Once live, Render displays your URL at the top:
   `https://real-estate-backend-xxxx.onrender.com`
4. Test it by opening `https://real-estate-backend-xxxx.onrender.com/health` in your browser. You should see `{"status":"ok"}`.
5. **Keep this URL handy for Step 2!**

---

## Step 2 — Deploy the Next.js Frontend to Vercel (Free)

Vercel was created by the authors of Next.js and provides instant, zero-config deployment.

### 2.1 Import the Repository
1. Log in to [Vercel](https://vercel.com/dashboard).
2. Click **Add New…** → **Project**.
3. Under **Import Git Repository**, click **Import** next to your repository.

### 2.2 Configure the Project
1. **Project Name**: `real-estate-hub` (or your choice).
2. **Framework Preset**: `Next.js` (automatically detected).
3. **Root Directory**: `./` (leave default).
4. **Build & Output Settings**: Leave default (`next build`).

### 2.3 Set Environment Variables
Expand the **Environment Variables** section and add:

| Name | Value |
|---|---|
| `BACKEND_URL` | `https://real-estate-backend-xxxx.onrender.com` *(from Step 1.3)* |
| `NODE_ENV` | `production` |
| `NEXT_PUBLIC_STREAMLIT_URL` | `http://localhost:8501` *(or your Streamlit link from Step 3)* |

### 2.4 Deploy
1. Click **Deploy**.
2. Vercel will build the Next.js website and deploy it in ~60 seconds.
3. You will get a live URL like: `https://real-estate-hub-xxxx.vercel.app`.
4. Open the website: your property catalog, search, AI chat (Zara), voice agent, and appointment booking are live!

### 2.5 (Recommended) Update Backend Trusted Origins
In your Render backend settings, update `TRUSTED_ORIGINS`:
```
TRUSTED_ORIGINS=https://real-estate-hub-xxxx.vercel.app
```

---

## Step 3 — Deploy the Streamlit ML Dashboard (Free)

Streamlit provides free cloud hosting specifically for Streamlit apps.

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Click **Create app**.
3. Configure:
   - **Repository**: Select your GitHub repo
   - **Branch**: `main`
   - **Main file path**: `dashboard_week8.py`
   - **App URL**: Choose a custom subdomain (e.g., `real-estate-hub-ml.streamlit.app`)
4. Click **Advanced settings…** and add the secret:
   ```toml
   WEEK8_API_URL = "https://real-estate-backend-xxxx.onrender.com"
   ```
5. Click **Deploy!**
6. Once deployed, copy your Streamlit URL (e.g., `https://real-estate-hub-ml.streamlit.app`) and add it to your Vercel frontend environment variables as `NEXT_PUBLIC_STREAMLIT_URL`.

---

## Alternative: Railway Deployment

If you have active Railway credits or a paid plan, Railway configuration files (`railway.json` and `nixpacks.toml`) are already included in this repository. Follow the instructions in the repository history or run `railway up`.
