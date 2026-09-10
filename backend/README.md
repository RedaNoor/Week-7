# Real Estate Voice Agent

A production-grade real estate sales and voice-agent backend for the
Pakistani property market. Built with FastAPI, LangGraph orchestration,
scikit-learn retrieval, PostgreSQL persistence, and SMTP email
integration. Includes a Next.js + TypeScript website for browsing the
property catalog, chatting with the sales agent, and booking property
visits.

---

## What's in this repository

```
real-estate-voice-agent/
├── backend/                    Python FastAPI backend
│   ├── app/
│   │   ├── main.py             REST API entry point
│   │   ├── orchestrator_endpoints.py
│   │   │                       n8n / service-to-service endpoints
│   │   ├── config.py           Pydantic settings loader
│   │   ├── services/
│   │   │   ├── appointment_service.py
│   │   │   ├── call_history.py
│   │   │   ├── calendar_service.py
│   │   │   ├── call_intent.py
│   │   │   ├── conversation_learning.py
│   │   │   ├── crm_service.py
│   │   │   ├── db_store.py
│   │   │   ├── db_store_enhanced.py
│   │   │   ├── email_service.py
│   │   │   ├── langgraph_agent.py
│   │   │   ├── lead_memory.py
│   │   │   ├── n8n_webhook.py
│   │   │   ├── profile_extraction.py
│   │   │   ├── property_matcher.py
│   │   │   ├── security.py
│   │   │   ├── service_contracts.py
│   │   │   └── session_state.py
│   │   └── data/               Runtime data (lead memory, trained model)
│   ├── data/                   Static catalogs (CSV)
│   ├── documents/              Property brochures (TXT)
│   ├── docs/                   Design documents (architecture, flows, prompts)
│   ├── .env.example            Copy to .env and fill in
│   ├── requirements.txt        Python dependencies
│   └── dashboard.html          Minimal admin dashboard (HTML)
│
├── src/                        Next.js 16 + TypeScript website
│   ├── app/
│   │   ├── page.tsx            Main SPA (Properties, Assistant, Booking, Memory tabs)
│   │   ├── layout.tsx          Root layout + metadata
│   │   └── api/proxy/[...path]/route.ts
│   │                           Forwards /api/proxy/* to FastAPI
│   ├── components/ui/          shadcn/ui components
│   └── hooks/                  Custom React hooks
│
├── scripts/                    Maintenance scripts
│   ├── test_smtp.py            SMTP diagnostic
│   ├── seed_conversations.py   Seeds the learner with sample chats
│   ├── generate_dataset.py     Generates the property catalog CSVs
│   └── generate_brochures.py   Generates property brochure TXT files
│
├── package.json                Next.js + frontend dependencies
├── tailwind.config.ts          Tailwind CSS configuration
└── tsconfig.json               TypeScript configuration
```

---

## Features

### Property catalog
- 42 verified listings across Lahore, Islamabad, Karachi, Faisalabad,
  and Rawalpindi.
- Real developers (DHA, Bahria Town, Capital Smart City, Emaar, etc.).
- Land sizes in marla and kanal (1 marla = 272.25 sqft, 1 kanal = 20 marla).
- Prices in Pakistani Rupees (PKR), reflecting late-2024 / 2025 market rates.
- Per-property amenities, payment plans, nearby hospitals and schools.

### Conversational sales agent
- LangGraph orchestrator with intent detection, profile extraction,
  property matching, and appointment-booking flow.
- Retrieval-augmented responses: every chat is matched against a corpus
  of past conversations using TF-IDF + cosine similarity, so the agent's
  responses are grounded in what has worked previously.
- Topic clustering (KMeans) groups past conversations into discoverable
  themes so you can see what users ask about most.
- The agent records every conversation back into its memory and
  auto-retrains every 5 new chats.

### Appointment booking
- UUID-based appointment IDs (not enumerable).
- Confirmation email sent via SMTP in parallel with n8n publishing.
- Email body includes:
  - Customer name and contact phone
  - Property title
  - Scheduled visit date and time
  - Assigned agent email
  - A call-history section listing every prior call where the visit
    time was discussed, with a 1-line summary of each call
- HTML and plain-text email bodies (auto-fallback).

### Security
- CORS allow-list (configurable via `TRUSTED_ORIGINS`).
- API key authentication on sensitive endpoints (`X-API-Key` header).
- Separate admin API key for mutating endpoints (`/agent/learn`,
  `/agent/retrain`, `/orchestrator/*`, rate-limit reset).
- Per-IP rate limiting (sliding window, in-memory).
- Strict Pydantic input validation (length limits, regex patterns,
  `EmailStr` for emails).
- Email header injection prevention (CR/LF stripped from all header fields).
- HTML body uses `html.escape()` on every user-supplied value.
- Path traversal defense on `/properties/{property_id}` (regex + resolved
  path check).
- Audit logging with PII redaction (phone numbers, emails, CNICs).
- Optional recipient allow-list (`ALLOWED_RECIPIENTS`).
- Twilio webhook signature verification (when `TWILIO_AUTH_TOKEN` is set).
- Pickle model file is server-side written only.

---

## Quick start

See **SETUP.md** for the complete step-by-step guide. The short version:

```bash
# 1. Backend
cd backend
cp .env.example .env          # fill in SMTP + DB + API keys
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 2. Frontend (separate terminal)
cd ../frontend
cp .env.example .env.local    # set NEXT_PUBLIC_API_KEY to match backend
npm install
npm run dev
```

Open http://localhost:3000 to use the website.

---

## Dataset

The property catalog is generated from `scripts/generate_dataset.py`.
The generator produces:

| File | Rows | Description |
|------|------|-------------|
| `properties.csv` | 42 | Main catalog (property_id, name, developer, city, area, type, bedrooms, size_sqft, size_marla, price, status, purpose) |
| `developers.csv` | 15 | Real Pakistani developers (DHA, Bahria Town, Emaar, etc.) |
| `locations.csv` | 37 | Real sectors, phases, precincts |
| `amenities.csv` | 172 | Amenities per property (3-6 per property) |
| `hospitals.csv` | 25 | Real hospitals near each location |
| `schools.csv` | 25 | Real schools near each location |
| `payment_plans.csv` | 125 | 1-3 payment plans per property |

To regenerate the dataset (e.g. to add more properties or update prices):

```bash
python scripts/generate_dataset.py
python scripts/generate_brochures.py
```

The brochure generator reads the CSV files and writes a marketing-style
TXT file for each property in `backend/documents/property_brochures/`.

---

## Cities covered

- **Lahore** — DHA Phase 6, DHA Phase 7, DHA Phase 9 Prism, Bahria Town,
  Lake City, Eden Housing, Gulberg, Johar Town, Model Town
- **Islamabad** — Sectors G-11, F-11, I-8, D-12; Capital Smart City,
  Bahria Town Phase 7, Bahria Enclave, Faisal Hills, Gulberg Greens,
  Park View City, B-17 Multi Gardens
- **Karachi** — Bahria Town Karachi, DHA City Karachi, DHA Karachi Phase 6,
  Crescent Bay, Clifton, Gulistan-e-Johar
- **Faisalabad** — Wapda City, Sahasra Town, Sitara Valley, Eden Garden
- **Rawalpindi** — Bahria Town Phase 8, Bahria Town Phase 4,
  DHA Rawalpindi Phase 2, PWD Housing Society

---

## License

Proprietary. All rights reserved.
