# Change Summary

## Overview

This project is a real estate sales and voice-agent backend for the
Pakistani property market. The codebase has been through several rounds
of updates to make it production-ready.

This document lists the major changes from the original version.

---

## Main updates

### Security hardening

The original codebase had no authentication, no rate limiting, and a
permissive CORS configuration. All of these have been addressed:

- API key authentication on sensitive endpoints (`X-API-Key` header)
- Separate admin API key for mutating endpoints
- Per-IP rate limiting (sliding window, in-memory)
- CORS allow-list (configurable via `TRUSTED_ORIGINS`)
- Strict Pydantic input validation (length limits, regex patterns, `EmailStr`)
- Email header injection prevention (CR/LF stripped from header fields)
- HTML email body uses `html.escape()` on every user-supplied value
- Path traversal defense on `/properties/{property_id}`
- Audit logging with PII redaction
- Optional recipient allow-list for outbound email
- Twilio webhook signature verification (when `TWILIO_AUTH_TOKEN` is set)
- UUID-based appointment IDs (not enumerable)

### Email service rewrite

The original `send_booking_email` function would return early if n8n
reported "published", which prevented the SMTP fallback from firing.
This was the root cause of confirmation emails never reaching customers.

The new email service:

- Always sends via SMTP in parallel with n8n publishing (SMTP is the
  source of truth for delivery)
- Includes the scheduled visit time in the email body
- Includes a call-history section listing every prior call where the
  visit time was discussed
- HTML email body with proper escaping
- Plain-text fallback for non-HTML clients

### Call history tracking

A new `call_history` service records every call where an appointment
time was discussed. When a booking is confirmed, the call history for
that lead is included in the confirmation email body so the customer
sees the full context of the conversation.

### Conversation learning

A retrieval-augmented memory module was added. Every chat is recorded
into a corpus and the agent retrieves the most similar past
conversations using TF-IDF + cosine similarity. The retrieved context
is injected into the response generation prompt.

Topic clustering (KMeans) groups past conversations into discoverable
themes. The model auto-retrains every 5 new chats.

### Realistic property dataset

The original synthetic dataset used fictional developer names. The new
dataset is generated from `scripts/generate_dataset.py` and contains:

- 42 properties across Lahore, Islamabad, Karachi, Faisalabad, Rawalpindi
- Real Pakistani developers (DHA, Bahria Town, Emaar, Capital Smart
  City, etc.)
- Real locations (DHA Phase 6, Sector F-11, Bahria Town Karachi, etc.)
- Land sizes in marla and kanal
- Prices in PKR reflecting late-2024 / 2025 market rates
- Real nearby hospitals and schools per location
- 1-3 payment plans per property

### Database fixes

- SQLAlchemy URL normalization (`postgres://` -> `postgresql://`)
- Timezone-aware datetime comparisons throughout
- CRLF line endings stripped from `.env` and all Python source files

### Frontend

A Next.js 16 + TypeScript website was added with four tabs:

- **Properties** — filterable grid of 42 listings
- **Assistant** — chat interface with suggested prompts
- **Book Visit** — appointment form + upcoming appointment list
- **Agent Memory** — corpus stats and learned topic clusters

The frontend communicates with the backend through a Next.js API proxy
route (`/api/proxy/[...path]`) to avoid CORS issues.

---

## File-level changes

### New files

- `app/services/security.py` — auth, rate limiting, sanitization
- `app/services/call_history.py` — call history store
- `app/services/conversation_learning.py` — retrieval + clustering
- `app/data/conversation_memory.json` — seeded corpus
- `app/data/conversation_model.pkl` — trained TF-IDF + KMeans model
- `data/properties.csv` — regenerated with real Pakistani data
- `data/developers.csv`, `locations.csv`, `amenities.csv`,
  `hospitals.csv`, `schools.csv`, `payment_plans.csv` — regenerated
- `documents/property_brochures/P001.txt` through `P042.txt` —
  one brochure per property
- `requirements.txt` — pinned Python dependencies
- `README.md` — project overview
- `SETUP.md` — complete setup guide
- `scripts/test_smtp.py`, `scripts/seed_conversations.py`,
  `scripts/generate_dataset.py`, `scripts/generate_brochures.py`

### Modified files

- `app/main.py` — added security dependencies, new endpoints, strict
  request models, call history integration
- `app/orchestrator_endpoints.py` — added admin auth, strict models
- `app/services/email_service.py` — SMTP always fires, HTML body,
  call history in email, sanitization
- `app/services/appointment_service.py` — UUIDs, lead linkage,
  timezone-aware datetimes, thread-safe mutations
- `app/services/db_store_enhanced.py` — postgres:// URL normalization
- `app/services/langgraph_agent.py` — conversation learner integration
- `app/services/property_matcher.py` — new CSV schema with marla sizes
- `.env.example` — added security and SMTP documentation

### Removed files

- Old property brochures (P001-P027) — replaced with new ones
  matching the new dataset
