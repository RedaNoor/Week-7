# Deployment Guide

## Setup checklist

Before you run this app, make sure the following are ready:

- Python environment for the project
- Postgres running locally or in a server
- the property data loaded into the database
- a .env file with the service credentials
- a tunnel or public URL if Vapi or Twilio needs to reach the backend

---

## Step 1: install dependencies

```bash
cd "c:\Users\ridan\Documents\Week 7"
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 2: configure environment

Create a .env file in the project root:

```bash
APP_ENV=production
APP_NAME=real_estate_voice_agent
LOG_LEVEL=INFO
DATABASE_URL=postgresql://real_estate_user:password@localhost:5432/real_estate_db
OPENAI_API_KEY=sk-your-key-here
VAPI_API_KEY=your-vapi-key
DEEPGRAM_API_KEY=your-deepgram-key
N8N_BASE_URL=http://localhost:5678/webhook
GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/google-service-account.json
GOOGLE_CALENDAR_ID=primary
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
```

---

## Step 3: create the database

```bash
createdb real_estate_db
psql -U postgres -d real_estate_db < database_schema.sql
psql -U postgres -d real_estate_db -c "\dt"
```

If the schema is not loaded correctly, the app will not be able to write lead memory or session data.

---

## Step 4: initialize the app

```bash
cd "c:\Users\ridan\Documents\Week 7"
python -c "from app.services.db_store_enhanced import init_db; init_db(); print('Database initialized')"
ls -la app/data/
```

---

## Step 5: run the project

Development mode:

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Production-style start:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Step 6: verify the app is alive

```bash
curl http://localhost:8000/
```

You should get a basic health response from the app.

---

## Step 7: test the main workflow

### Lead analysis
```bash
curl -X POST http://localhost:8000/lead/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Budget 3 crore hai. DHA mein family home chahiye.",
    "session_id": "test_session_1"
  }'
```

### Workflow turn processing
```bash
curl -X POST http://localhost:8000/orchestrator/process-turn \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_1",
    "lead_id": "lead_1",
    "transcript": "Budget 2 crore. Gulshan-e-Iqbal apartment."
  }'
```

### Postgres sync
```bash
curl -X POST http://localhost:8000/orchestrator/sync-lead-to-postgres \
  -H "Content-Type: application/json" \
  -d '{
    "lead_id": "lead_1",
    "phone_number": "+923001234567",
    "customer_name": "Ali Khan",
    "profile": {
      "budget": "2 crore",
      "city": "Karachi",
      "area": "Gulshan-e-Iqbal",
      "property_type": "Apartment",
      "purpose": "buy"
    }
  }'
```

---

## Service setup notes

### Google Calendar

1. create a service account in Google Cloud
2. download the JSON credentials
3. share the calendar with that service account
4. set GOOGLE_SERVICE_ACCOUNT_FILE to the correct file path

### Gmail / SMTP

1. enable 2-factor authentication on the Gmail account
2. generate an app password
3. add the SMTP values in .env

### Workflow automation

Set up your webhook listener so the app can push important events like lead creation, booking, email, or CRM updates.

---

## Troubleshooting

If something is not working, check these in order:

- .env values are present and correct
- Postgres is running and the schema is loaded
- the app is using the right Python environment
- the port is open and the tunnel is configured correctly
- the payload structure matches what the endpoint expects

This project is easiest to debug if you test the call flow in small steps instead of trying everything at once.
