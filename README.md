# Real Estate Voice Agent

A production-grade real estate sales and voice-agent platform for the
Pakistani property market. Built with FastAPI, LangGraph orchestration,
scikit-learn retrieval, PostgreSQL persistence, and SMTP email
integration. Includes a Next.js + TypeScript website for browsing the
property catalog, chatting with the sales agent, and booking property
visits.

---

## Repository structure

```
.
├── backend/              Python FastAPI backend (see backend/README.md)
├── src/                  Next.js 16 + TypeScript website
├── scripts/              Maintenance scripts (test, seed, generate)
├── package.json          Frontend dependencies
├── tailwind.config.ts    Tailwind CSS configuration
├── tsconfig.json         TypeScript configuration
└── .env.example         Frontend env template
```

For the complete setup guide, see **[backend/SETUP.md](backend/SETUP.md)**.

For the deployment guide, see **[backend/DEPLOYMENT_GUIDE.md](backend/DEPLOYMENT_GUIDE.md)**.

For the change log, see **[backend/CHANGES_SUMMARY.md](backend/CHANGES_SUMMARY.md)**.

---

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 20+ (or Bun 1.1+)
- PostgreSQL 14+ (optional — the backend can run without it for testing)
- A Gmail account with an App Password for SMTP

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and fill in SMTP, DB, and API_KEY values
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend (separate terminal)

```bash
# From the repository root
npm install
cp .env.example .env.local
# Edit .env.local and set NEXT_PUBLIC_API_KEY to match backend
npm run dev
```

Open http://localhost:3000 to use the website.

### 3. Generate the property dataset (optional)

The dataset is pre-generated and committed in `backend/data/`. To
regenerate it (e.g. to add more properties):

```bash
python scripts/generate_dataset.py
python scripts/generate_brochures.py
```

### 4. Seed the conversation learner (optional)

The learner comes pre-seeded with 35 sample conversations. To re-seed:

```bash
cd backend
source venv/bin/activate
python ../scripts/seed_conversations.py
```

---

## Features

### Property catalog

- 42 verified listings across Lahore, Islamabad, Karachi, Faisalabad,
  and Rawalpindi
- Real Pakistani developers (DHA, Bahria Town, Emaar, Capital Smart
  City, etc.)
- Real locations (DHA Phase 6, Sector F-11, Bahria Town Karachi, etc.)
- Land sizes in marla and kanal (1 marla = 272.25 sqft)
- Prices in PKR reflecting late-2024 / 2025 market rates
- Real nearby hospitals and schools per location
- 1-3 payment plans per property

### Conversational sales agent

- LangGraph orchestrator with intent detection, profile extraction,
  property matching, and appointment-booking flow
- Retrieval-augmented responses (TF-IDF + cosine similarity over a
  corpus of past conversations)
- Topic clustering (KMeans) groups past conversations into discoverable
  themes
- Auto-retrains every 5 new conversations

### Appointment booking

- UUID-based appointment IDs (not enumerable)
- Confirmation email sent via SMTP in parallel with n8n publishing
- Email body includes the scheduled visit time and a call-history
  section listing every prior call where the visit time was discussed
- HTML and plain-text email bodies (auto-fallback)

### Security

- API key authentication on sensitive endpoints
- Separate admin API key for mutating endpoints
- Per-IP rate limiting (sliding window)
- CORS allow-list (configurable via `TRUSTED_ORIGINS`)
- Strict Pydantic input validation
- Email header injection prevention
- HTML body uses `html.escape()` on every user-supplied value
- Path traversal defense on property lookup
- Audit logging with PII redaction
- Optional recipient allow-list for outbound email
- Twilio webhook signature verification

---

## License

Proprietary. All rights reserved.
