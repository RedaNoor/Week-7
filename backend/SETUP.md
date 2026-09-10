# Setup Guide — Real Estate Voice Agent

This guide walks you through getting the backend and frontend running
locally, configuring SMTP email, generating the property dataset, and
deploying to production.

---

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Backend setup](#2-backend-setup)
3. [Frontend setup](#3-frontend-setup)
4. [SMTP configuration](#4-smtp-configuration)
5. [Database setup](#5-database-setup)
6. [Generating the property dataset](#6-generating-the-property-dataset)
7. [Seeding the conversation learner](#7-seeding-the-conversation-learner)
8. [Running the test suite](#8-running-the-test-suite)
9. [Production deployment](#9-production-deployment)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.11+ | Tested on 3.12 |
| Node.js | 20+ | Tested on 22 LTS |
| npm or bun | npm 10+ / bun 1.1+ | Either works |
| PostgreSQL | 14+ | Or use a managed service like Neon, Supabase, or RDS |
| Gmail account | — | For SMTP (App Password required) |

You will also need accounts/keys for the optional integrations:

- **Vapi** or **Twilio** — telephony webhooks
- **Deepgram** — speech-to-text
- **OpenAI** or **OpenRouter** — LLM provider
- **n8n** — workflow automation (optional; the backend works fine without it)

---

## 2. Backend setup

```bash
cd backend

# Create a virtual environment
python -m venv venv
source venv/bin/activate         # on Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy the environment template and fill in your values
cp .env.example .env
nano .env                         # or your editor of choice
```

### Environment variables

Open `.env` and configure at least these values:

```ini
# Application
APP_ENV=development                # use 'production' when deploying
LOG_LEVEL=INFO

# Database — see section 5 for setup instructions
DATABASE_URL=postgresql://user:password@localhost:5432/real_estate_voice

# SMTP — see section 4 for Gmail App Password setup
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_char_app_password
SMTP_FROM=your_email@gmail.com
DEFAULT_RECIPIENT_EMAIL=your_email@gmail.com

# Security — generate with:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
API_KEY=replace_with_random_32_char_string
ADMIN_API_KEY=replace_with_different_random_32_char_string
REQUIRE_AUTH=false                 # set to true in production

# CORS — comma-separated list of allowed frontend origins
TRUSTED_ORIGINS=http://localhost:3000,http://localhost:5173
```

### Start the backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

You should see:

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Verify the healthcheck:

```bash
curl http://localhost:8000/
# {"status":"ok","app":"real_estate_voice_agent","version":"1.0.0","time":"..."}
```

---

## 3. Frontend setup

The frontend is a Next.js 16 app with TypeScript, Tailwind CSS, and
shadcn/ui. It lives at the repository root (not in a subfolder).

```bash
# From the repository root
npm install
# or
bun install

# Copy the environment template
cp .env.example .env.local

# Set the API key to match your backend's API_KEY
echo "NEXT_PUBLIC_API_KEY=your_backend_api_key_here" >> .env.local
echo "BACKEND_URL=http://localhost:8000" >> .env.local

# Start the dev server
npm run dev
# or
bun run dev
```

Open http://localhost:3000 in your browser. You should see the real
estate website with four tabs:

- **Properties** — browse 42 listings, filter by city and type
- **Assistant** — chat with the agent
- **Book Visit** — schedule a property visit
- **Agent Memory** — see what the agent has learned

---

## 4. SMTP configuration

The system sends booking confirmation emails via SMTP. The recommended
provider is Gmail with an App Password (NOT your regular Gmail password).

### Generate a Gmail App Password

1. Go to https://myaccount.google.com/apppasswords
2. Sign in with your Gmail account
3. Click "Select app" → "Other (custom name)" → type "Real Estate Agent"
4. Click "Generate"
5. Copy the 16-character password (format: `abcd efgh ijkl mnop`)
6. Paste it into your `.env` as `SMTP_PASSWORD` (keep the spaces or
   remove them — both work)

### Test SMTP

```bash
cd backend
source venv/bin/activate
python ../scripts/test_smtp.py
```

This script:
- Verifies your SMTP credentials are valid
- Tests TCP connectivity to the SMTP server
- Sends a real test email to your `DEFAULT_RECIPIENT_EMAIL`
- Runs the production code path through `send_booking_email()`
- Simulates the full POST `/appointments` flow

If the test email arrives in your inbox (check spam if not), SMTP is
configured correctly.

### Email allow-list (recommended for production)

To prevent the booking endpoint from being abused as an open email
relay, set `ALLOWED_RECIPIENTS` to a comma-separated list of email
addresses that are allowed to receive outbound email:

```ini
ALLOWED_RECIPIENTS=founder@yourcompany.com,agent1@yourcompany.com,agent2@yourcompany.com
```

When set, the email service will silently skip any recipient not on
this list. Leave the variable unset to allow any recipient (development
mode only).

---

## 5. Database setup

The backend uses PostgreSQL for persistent storage of leads,
appointments, call history, and followups. The schema is defined in
`backend/database_schema.sql` and applied automatically on first startup
via `init_db()`.

### Option A: Local PostgreSQL

```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt install postgresql postgresql-contrib

# Create a database and user
sudo -u postgres psql
postgres=# CREATE DATABASE real_estate_voice;
postgres=# CREATE USER realestate WITH PASSWORD 'your_password';
postgres=# GRANT ALL PRIVILEGES ON DATABASE real_estate_voice TO realestate;
postgres=# \q

# Apply the schema
psql -U realestate -d real_estate_voice -f backend/database_schema.sql
```

Update your `.env`:

```ini
DATABASE_URL=postgresql://realestate:your_password@localhost:5432/real_estate_voice
```

### Option B: Managed PostgreSQL (Neon, Supabase, RDS)

Create a database on your provider of choice and copy the connection
string into `.env`. Neon's free tier works well for development:

```ini
DATABASE_URL=postgresql://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
```

### Verify the database connection

```bash
cd backend
source venv/bin/activate
python -c "
from app.config import settings
from sqlalchemy import create_engine, text
engine = create_engine(settings.database_url)
with engine.connect() as conn:
    result = conn.execute(text('SELECT version()'))
    print(result.fetchone()[0])
"
```

If you don't see the PostgreSQL version string, your `DATABASE_URL` is
wrong or the database isn't reachable.

### Running without a database (development)

If you just want to test the API without setting up Postgres, leave
`DATABASE_URL` empty. The backend will fall back to in-memory storage
and JSON file persistence. Data will be lost on restart.

---

## 6. Generating the property dataset

The property catalog is generated from `scripts/generate_dataset.py`.
The generator produces 7 CSV files in `backend/data/`:

```bash
python scripts/generate_dataset.py
```

Output:

```
Writing dataset to /home/.../backend/data
  wrote developers.csv: 15 rows
  wrote locations.csv: 37 rows
  wrote properties.csv: 42 rows
  wrote amenities.csv: 172 rows
  wrote hospitals.csv: 25 rows
  wrote schools.csv: 25 rows
  wrote payment_plans.csv: 125 rows
```

After generating the CSVs, generate the property brochure text files:

```bash
python scripts/generate_brochures.py
```

This creates one TXT file per property in
`backend/documents/property_brochures/`, containing the property's
overview, amenities, payment plans, and nearby facilities.

### Editing the dataset

To add or modify properties, edit the `PROPERTIES_TEMPLATE` list in
`scripts/generate_dataset.py` and re-run both scripts. The CSVs and
brochures will be regenerated.

To add a new developer, add a tuple to the `DEVELOPERS` list and use
its `developer_id` in `PROPERTIES_TEMPLATE`.

---

## 7. Seeding the conversation learner

The sales agent retrieves context from past conversations. To bootstrap
its memory with realistic sample chats, run:

```bash
cd backend
source venv/bin/activate
python ../scripts/seed_conversations.py
```

This seeds 35 sample conversations covering booking, pricing, location,
investment, and FAQ intents. The script then trains the TF-IDF + KMeans
model and prints a topic summary.

To reset the learner's memory (e.g. before re-seeding):

```bash
rm backend/app/data/conversation_memory.json
rm backend/app/data/conversation_model.pkl
python ../scripts/seed_conversations.py
```

---

## 8. Running the test suite

### SMTP test

```bash
cd backend
source venv/bin/activate
python ../scripts/test_smtp.py
```

Verifies SMTP credentials, sends a test email, and exercises the full
booking flow.

### API endpoint tests

Once the backend is running, you can test the endpoints with curl:

```bash
# Health check
curl http://localhost:8000/

# List properties (public)
curl http://localhost:8000/properties?limit=5

# Get a single property
curl http://localhost:8000/properties/P001

# Chat with the agent (requires API key in production)
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"session_id":"test1","message":"Hi, I want to book a visit for P001"}'

# Book an appointment (requires API key)
curl -X POST http://localhost:8000/appointments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "client_name":"Test Client",
    "client_phone":"+923001234567",
    "property_id":"P001",
    "property_title":"5 Marla House in DHA Phase 6",
    "scheduled_at":"2099-01-01T10:00:00+00:00",
    "employee_email":"your_email@gmail.com"
  }'

# View agent memory stats
curl http://localhost:8000/agent/memory/stats

# View learned topic clusters
curl http://localhost:8000/agent/memory/topics
```

---

## 9. Production deployment

### Backend

Recommended: deploy as a Docker container behind a reverse proxy
(nginx, Caddy, or AWS ALB).

```bash
# Build the image
docker build -t real-estate-agent:latest .

# Run it
docker run -d \
  --name real-estate-agent \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/backend/data:/app/backend/data \
  -v $(pwd)/backend/documents:/app/backend/documents \
  real-estate-agent:latest
```

Production `.env` overrides:

```ini
APP_ENV=production
LOG_LEVEL=WARNING
REQUIRE_AUTH=true                 # CRITICAL: enable API key auth
ALLOWED_RECIPIENTS=founder@yourcompany.com,agent1@yourcompany.com
TRUSTED_ORIGINS=https://yourdomain.com
```

### Frontend

The Next.js frontend can be deployed to Vercel, Netlify, or any static
host with SSR support. Set the environment variables in your hosting
provider's dashboard:

- `NEXT_PUBLIC_API_KEY` — your backend's `API_KEY`
- `NEXT_PUBLIC_BACKEND_URL` — your backend's public URL

### Reverse proxy example (nginx)

```nginx
server {
    listen 443 ssl;
    server_name api.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Database

Use a managed PostgreSQL service (Neon, Supabase, AWS RDS, Google Cloud SQL)
for automated backups and failover. Run `database_schema.sql` against the
production database once:

```bash
psql "$DATABASE_URL" -f backend/database_schema.sql
```

---

## 10. Troubleshooting

### SMTP errors

**Error**: `SMTPAuthenticationError: 535 Username and Password not accepted`

You're using your regular Gmail password instead of an App Password.
Generate one at https://myaccount.google.com/apppasswords.

**Error**: `ssl.SSLError: [SSL: WRONG_VERSION_NUMBER]`

Your `SMTP_PORT` is wrong. Port 465 uses SSL (set `SMTP_PORT=465`).
Port 587 uses STARTTLS (set `SMTP_PORT=587`).

**Email never arrives**: Check the spam folder. Add your `SMTP_FROM`
address to your contacts. Verify `ALLOWED_RECIPIENTS` (if set) includes
the recipient address.

### Database errors

**Error**: `sqlalchemy.exc.OperationalError: could not connect to server`

- Check your `DATABASE_URL` syntax
- Verify the database server is running and accepting connections
- Check your firewall / security group rules
- For Neon/Supabase: verify your IP is allowed

**Error**: `Could not parse SQLAlchemy URL from given URL string`

Your `DATABASE_URL` uses the wrong scheme. It must start with
`postgresql://` or `postgresql+psycopg2://` — NOT `postgres://`.

### Frontend errors

**Error**: `Failed to fetch` in browser console

The frontend can't reach the backend. Check:

- The backend is running on port 8000
- Your `.env.local` has the correct `NEXT_PUBLIC_BACKEND_URL`
- CORS: the backend's `TRUSTED_ORIGINS` includes the frontend's origin

**Error**: `401 Unauthorized` from API calls

`REQUIRE_AUTH=true` is set but the frontend isn't sending the
`X-API-Key` header. Check `NEXT_PUBLIC_API_KEY` in your `.env.local`.

### Backend errors

**Error**: `email_validator not found`

```bash
pip install email-validator
```

**Error**: `ModuleNotFoundError: No module named 'sqlalchemy'`

You didn't install dependencies:

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

**Error**: `429 Too Many Requests`

You've hit a rate limit. Wait 60 seconds, or set
`REQUIRE_AUTH=false` and use the admin reset endpoint:

```bash
curl -X DELETE -H "X-API-Key: $ADMIN_API_KEY" \
  http://localhost:8000/admin/rate-limit/127.0.0.1
```

### Still stuck?

Check the backend logs:

```bash
tail -f /tmp/uvicorn.log
```

The audit log middleware logs every request with method, path, status,
duration, and PII-redacted query parameters. Look for the `AUDIT`
prefix lines.
