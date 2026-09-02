# Quick Reference

## What is in this project

This project already has a few working pieces:

1. conversation flow and lead extraction
2. property matching against the catalog
3. appointment and follow-up logic
4. Postgres-backed memory and session state
5. webhook integration for internal services and automation

---

## Quick start

### 1. Run the app
```bash
cd c:\Users\ridan\Documents\Week 7
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Test lead analysis
```bash
curl -X POST http://localhost:8000/lead/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Budget 3 crore hai. DHA mein family home chahiye. Visit karna chahata hoon.",
    "session_id": "test_1"
  }'
```

### 3. Test the workflow endpoint
```bash
curl -X POST http://localhost:8000/orchestrator/process-turn \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_123",
    "lead_id": "lead_456",
    "transcript": "Assalam o Alaikum. 3 crore budget hai."
  }'
```

---

## Main files

| File | Purpose |
|------|---------|
| app/orchestrator_endpoints.py | workflow API layer |
| app/services/langgraph_agent.py | call flow and tool logic |
| app/services/service_contracts.py | email, calendar, and CRM hooks |
| app/services/lead_memory.py | Postgres-backed lead memory |
| IMPLEMENTATION_SUMMARY.md | project overview |

---

## Basic flow

```text
Incoming call
   ↓
FastAPI app
   ↓
Conversation logic
   ↓
   ┌─────┴─────┬─────────┐
   ↓           ↓         ↓
Postgres    Workflow  Memory
   ↓           ↓         ↓
Database    External   Session
            Services   Context
```

---

## Main endpoints

### Process a conversation turn
```bash
POST /orchestrator/process-turn
{
  "session_id": "string",
  "lead_id": "string (optional)",
  "transcript": "string"
}
```

### Sync a lead to Postgres
```bash
POST /orchestrator/sync-lead-to-postgres
{
  "lead_id": "string",
  "phone_number": "string (optional)",
  "customer_name": "string (optional)",
  "profile": { "budget": "...", "city": "..." }
}
```

### Get session context
```bash
GET /orchestrator/session/{session_id}/context
```

### Get full lead profile
```bash
GET /orchestrator/lead/{lead_id}/full-profile
```

---

## Environment setup

Create a .env file:
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/real_estate
OPENAI_API_KEY=sk-xxx
VAPI_API_KEY=xxx
DEEPGRAM_API_KEY=xxx
N8N_BASE_URL=http://localhost:5678/webhook
SMTP_HOST=smtp.gmail.com
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=app-password
GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/service-account.json
```

---

## Testing flow

### Step 1: process a lead
```bash
curl -X POST http://localhost:8000/orchestrator/process-turn \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_001",
    "lead_id": "lead_001",
    "transcript": "Budget 2 crore. Gulshan-e-Iqbal mein apartment."
  }'
```

### Step 2: sync to the database
```bash
curl -X POST http://localhost:8000/orchestrator/sync-lead-to-postgres \
  -H "Content-Type: application/json" \
  -d '{
    "lead_id": "lead_001",
    "phone_number": "+923001234567",
    "customer_name": "Ahmed Khan",
    "profile": {
      "budget": "2 crore",
      "city": "Karachi",
      "area": "Gulshan-e-Iqbal",
      "property_type": "Apartment",
      "purpose": "buy"
    }
  }'
```

### Step 3: fetch the full lead context
```bash
curl -X GET http://localhost:8000/orchestrator/lead/lead_001/full-profile
```

---

## Built-in tools

The flow can trigger these tools when needed:

1. book_property_visit - schedule a site visit
2. match_properties_for_profile - look up likely matches
3. create_crm_lead_contact - add a lead to the CRM
4. publish_to_n8n - push events to the workflow system
5. get_lead_memory_context - pull prior conversation context

---

## Workflow events

The app can publish events like:

- lead_created / lead_updated
- appointment_scheduled / cancelled / rescheduled
- email_booking_sent / email_followup_sent
- calendar_event_created / calendar_event_cancelled
- crm_contact_created / crm_contact_updated

---

## Debugging

### Check if the app is running
```bash
curl http://localhost:8000/
```

### Check database connection
```bash
# Watch the startup logs for database initialization output
```

### Check local fallback files
```bash
# Emails: Week 7/app/data/email_log.json
# CRM: Week 7/app/data/crm_operations.json
# Lead memory: Week 7/app/data/lead_memory.json
```

---

## Common issues

| Issue | Fix |
|-------|-----|
| workflow webhook not firing | check the N8N_BASE_URL and verify the workflow service is running |
| Postgres connection error | verify the DATABASE_URL and credentials |
| emails not sending | check SMTP credentials and the workflow setup |
| calendar sync failing | check the Google service account path |
| appointment booking fails | make sure the request includes all required values |
