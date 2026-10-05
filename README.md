# Real Estate Hub — AI Voice Agent & Property Platform

A full-stack real estate platform for the Pakistani property market. It combines a customer-facing website with a conversational AI agent, a REST API backend, and an ML analytics dashboard — all wired together and deployable to Railway in minutes.

---

## What this project does

| Feature | What you get |
|---|---|
| **Property catalog** | 42 verified listings across Lahore, Karachi, Islamabad, Rawalpindi, and Faisalabad with prices, developer details, and payment plans |
| **AI Chat agent (Zara)** | A bilingual (English / Roman Urdu) sales agent powered by LangGraph + OpenAI that recommends properties, books site visits, and learns from every conversation |
| **Voice call** | Browser-based voice call via Vapi.ai — same AI agent, now you can speak to it |
| **Appointment booking** | Book property visits, get confirmation emails, reschedule or cancel — all from the website |
| **Property valuation** | ML model (Random Forest) that predicts a fair price range for any property given its location, size, type, and amenities |
| **Lead scoring** | Classifier that ranks incoming leads (Hot / Warm / Cold) based on call history, budget, and engagement signals |
| **ML dashboard** | Streamlit dashboard showing market analytics, lead scores, SHAP explanations, and model health |
| **n8n integration** | Webhook-based automation for lead sync, follow-up emails, and appointment confirmations |
| **Security** | API key auth, per-IP rate limiting, CORS allow-list, Pydantic input validation, PII-redacting audit logs |

---

## Project structure

```
.
├── src/                    Next.js 16 + TypeScript website (customer-facing)
│   ├── app/
│   │   ├── page.tsx        Main page — properties, chat, voice, appointments
│   │   ├── layout.tsx      App shell, fonts, metadata
│   │   └── api/proxy/      Server-side API proxy to the FastAPI backend
│   └── components/
│       ├── voice-call-tab  Vapi voice call UI
│       ├── login-modal     Register / login form
│       └── auth-context    User session state
│
├── backend/                Python FastAPI backend
│   ├── app/
│   │   ├── main.py         All REST endpoints (~950 lines)
│   │   ├── ml_endpoints.py /predict/price, /predict/lead-score, /explain/*
│   │   ├── config.py       Settings loaded from .env
│   │   └── services/
│   │       ├── langgraph_agent.py   The AI conversation graph
│   │       ├── ml_service.py        Valuation & lead-scoring models
│   │       ├── property_matcher.py  TF-IDF property search
│   │       ├── conversation_learning.py  KMeans topic clustering + retraining
│   │       ├── email_service.py     SMTP confirmation emails
│   │       ├── appointment_service.py
│   │       ├── vapi_service.py      Voice webhook handler
│   │       ├── security.py          API key auth, rate limiting, audit logs
│   │       └── auth_service.py      User register / login / JWT
│   ├── data/               Property CSVs, ML logs
│   └── requirements.txt
│
├── dashboard_week8.py      Streamlit ML dashboard (run separately on port 8501)
├── dataset_properties.csv  168 k-row Zameen property export (source of truth)
├── scripts/                Utility scripts (seed, evaluate, retrain, drift)
├── prisma/                 Database schema (PostgreSQL via Neon)
├── Dockerfile              Backend Docker image
├── docker-compose.week8.yml  Backend + dashboard together
├── package.json            Frontend dependencies
├── railway.json            Railway frontend deployment config
├── backend/railway.json    Railway backend deployment config
└── .env.example            Template — copy to .env and .env.local
```

---

## Requirements

- **Python 3.11+**
- **Node.js 20+** (or Bun 1.1+)
- **PostgreSQL** — a free [Neon](https://neon.tech) database works perfectly
- An **OpenAI API key** (or an OpenRouter key that proxies it)
- A **Gmail app password** for SMTP emails (optional but recommended)
- A **Vapi.ai** account for voice calls (optional)

---

## Quick start (local)

See **[SETUP.md](SETUP.md)** for the full step-by-step guide.

Short version:

```bash
# 1. Clone and enter the repo
git clone <your-repo-url>
cd "Week 7"

# 2. Backend — open a terminal in the project root
python -m venv backend/venv
backend/venv/Scripts/activate     # Mac/Linux: source backend/venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env   # fill in OPENAI_API_KEY, DATABASE_URL, etc.
uvicorn backend.app.main:app --reload --port 8000

# 3. Frontend — open a second terminal
npm install
cp .env.example .env.local          # set BACKEND_URL=http://localhost:8000
npm run dev

# 4. ML dashboard — open a third terminal (optional)
streamlit run dashboard_week8.py --server.port 8501
```

- Website → http://localhost:3000
- API docs → http://localhost:8000/docs
- ML dashboard → http://localhost:8501

---

## Deployment (100% Free Forever)

See **[DEPLOY.md](DEPLOY.md)** for the complete deployment guide.

The recommended free production setup is:
1. **Frontend (Website)**: Deploy to **[Vercel](https://vercel.com)** (zero-config Next.js, 100% free Hobby tier).
2. **Backend (API)**: Deploy to **[Render](https://render.com)** (free Python Web Service using `render.yaml` or manual setup).
3. **ML Dashboard**: Deploy to **[Streamlit Community Cloud](https://share.streamlit.io)** (free hosting for `dashboard_week8.py`).
4. **Database**: Managed PostgreSQL on **[Neon](https://neon.tech)** (free tier).

*(Railway is also supported via included `railway.json` and `backend/railway.json` configs if you have active Railway credits).*

---

## Environment variables

### Backend service (set in Railway → Variables tab)

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | Powers the AI chat agent |
| `DATABASE_URL` | Yes | PostgreSQL connection string (Neon works great) |
| `API_KEY` | Yes | Secret key for protected API endpoints |
| `ADMIN_API_KEY` | Yes | Admin-only endpoints (retrain, rate-limit reset) |
| `TRUSTED_ORIGINS` | Yes | Comma-separated allowed CORS origins (your frontend URL) |
| `REQUIRE_AUTH` | Yes | Set to `true` in production |
| `VAPI_API_KEY` | No | Vapi.ai key for voice calls |
| `VAPI_ASSISTANT_ID` | No | Your Vapi assistant ID |
| `DEEPGRAM_API_KEY` | No | Deepgram speech-to-text key |
| `SMTP_HOST` | No | Email server (default: smtp.gmail.com) |
| `SMTP_USER` | No | Gmail address |
| `SMTP_PASSWORD` | No | Gmail app password |
| `N8N_BASE_URL` | No | n8n webhook URL for automation |

### Frontend service (set in Railway → Variables tab)

| Variable | Required | Description |
|---|---|---|
| `BACKEND_URL` | Yes | Your Railway backend URL (server-side only, no NEXT_PUBLIC) |
| `NEXT_PUBLIC_API_KEY` | Yes | Must match `API_KEY` on the backend |

---

## API endpoints

All endpoints are served from the FastAPI backend. Full interactive docs at `/docs`.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/properties` | API key | List property catalog |
| GET | `/properties/{id}` | API key | Get single property |
| POST | `/agent/chat` | API key | Send a message to the AI agent |
| POST | `/appointments` | API key | Book a site visit |
| GET | `/appointments` | API key | List all appointments |
| POST | `/predict/price` | API key | Predict fair property price |
| POST | `/predict/lead-score` | API key | Score a sales lead |
| POST | `/explain/price` | API key | SHAP explanation for price |
| POST | `/explain/lead` | API key | SHAP explanation for lead score |
| POST | `/predict/batch` | API key | Batch price prediction (CSV) |
| GET | `/health` | None | API health + ML model status |
| GET | `/model/info` | None | ML model version and metrics |
| POST | `/auth/register` | None | Register a new user |
| POST | `/auth/login` | None | Login and get a JWT token |

---

## ML models

### Property valuation
- **Algorithm**: Random Forest Regressor
- **Features**: city, location, property type, area (marla), bedrooms, bathrooms, amenity score, coordinates, listing year
- **Metrics**: MAE, RMSE, R², MAPE (reported at `/model/info`)
- **Output**: predicted price + confidence range + over/under-priced verdict

### Lead scoring
- **Algorithm**: Logistic Regression (class-balanced)
- **Features**: lead source, budget, city, call count, call duration, response time, visit booked, days since contact, objection type
- **Output**: Hot / Warm / Cold segment + conversion probability + SHAP feature contributions

Both models train lazily on first request. A pre-trained bundle can be placed at
`backend/data/week8/models/model_bundle.joblib` to skip training on startup.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, TypeScript, Tailwind CSS v4, ShadCN UI |
| Backend | FastAPI, Pydantic v2, LangGraph, LangChain |
| Database | PostgreSQL (Neon) + SQLAlchemy |
| ML | scikit-learn, pandas, numpy, SHAP, joblib |
| Voice | Vapi.ai (real-time voice), Deepgram (speech-to-text) |
| Email | SMTP (Gmail) |
| Automation | n8n webhooks |
| Deployment | Railway (Docker / Nixpacks) |
| CI | GitHub Actions |

---

## License

Proprietary — all rights reserved.
