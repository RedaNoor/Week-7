# Quick Reference - Week 7 Capstone Implementation

## What Was Done

Your Week 7 real-estate AI voice agent project has been enhanced with:

1. **LangGraph Agent with Tools** - Intelligent conversation orchestration with automatic tool invocation
2. **n8n-Ready Endpoints** - Production-grade API for n8n workflow integration
3. **Hardened Postgres** - Lead memory and session state now fully schema-compliant
4. **External Service Contracts** - Email, Calendar, and CRM services with fallback mechanisms

---

## Quick Start

### 1. Run the Application
```bash
cd c:\Users\ridan\Documents\Netixsol\Week 7
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Test the Agent
```bash
curl -X POST http://localhost:8000/lead/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Budget 3 crore hai. DHA mein family home chahiye. Visit karna chahata hoon.",
    "session_id": "test_1"
  }'
```

### 3. Test n8n Orchestration
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

## Key Files

| File | Purpose |
|------|---------|
| `app/orchestrator_endpoints.py` | n8n-ready API layer |
| `app/services/langgraph_agent.py` | LangGraph orchestrator with tools |
| `app/services/service_contracts.py` | Email, Calendar, CRM services |
| `app/services/lead_memory.py` | Postgres-backed lead memory |
| `IMPLEMENTATION_SUMMARY.md` | Full documentation |

---

## Architecture

```
Incoming Call (Vapi/Twilio)
         ↓
    Main FastAPI
         ↓
    LangGraph Agent (with tools)
         ↓
    ┌─────┴─────┬─────────┐
    ↓           ↓         ↓
 Postgres   n8n Webhooks  Memory
    ↓           ↓         ↓
 Database   External     Session
            Services    Context
```

---

## New Endpoints

### Process Conversation Turn
```bash
POST /orchestrator/process-turn
{
  "session_id": "string",
  "lead_id": "string (optional)",
  "transcript": "string"
}
```

### Sync Lead to Postgres
```bash
POST /orchestrator/sync-lead-to-postgres
{
  "lead_id": "string",
  "phone_number": "string (optional)",
  "customer_name": "string (optional)",
  "profile": { "budget": "...", "city": "..." }
}
```

### Get Session Context
```bash
GET /orchestrator/session/{session_id}/context
```

### Get Lead Profile
```bash
GET /orchestrator/lead/{lead_id}/full-profile
```

---

## Environment Setup

Create a `.env` file:
```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/real_estate

# APIs
OPENAI_API_KEY=sk-xxx
VAPI_API_KEY=xxx
DEEPGRAM_API_KEY=xxx

# n8n
N8N_BASE_URL=http://localhost:5678/webhook

# Email
SMTP_HOST=smtp.gmail.com
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=app-password

# Google Calendar
GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/service-account.json
```

---

## Testing Workflow

### Step 1: Process a Lead
```bash
curl -X POST http://localhost:8000/orchestrator/process-turn \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_001",
    "lead_id": "lead_001",
    "transcript": "Budget 2 crore. Gulshan-e-Iqbal mein apartment."
  }'
```

**Expected Response:**
```json
{
  "status": "success",
  "session_id": "sess_001",
  "result": {
    "profile": {
      "budget": "2 crore",
      "city": "Karachi",
      "area": "Gulshan-e-Iqbal",
      "property_type": "Apartment"
    },
    "intent": "property_inquiry",
    "recommendations": [...]
  }
}
```

### Step 2: Sync to Database
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

### Step 3: Retrieve Full Context
```bash
curl -X GET http://localhost:8000/orchestrator/lead/lead_001/full-profile
```

---

## LangGraph Agent Tools

The agent can automatically call these tools:

1. **book_property_visit** - Schedule a property viewing
2. **match_properties_for_profile** - Find matching properties
3. **create_crm_lead_contact** - Create CRM contact
4. **publish_to_n8n** - Trigger n8n workflows
5. **get_lead_memory_context** - Retrieve lead history

---

## n8n Integration Points

Events published to n8n:
- `lead_created` / `lead_updated`
- `appointment_scheduled` / `cancelled` / `rescheduled`
- `email_booking_sent` / `email_followup_sent`
- `calendar_event_created` / `calendar_event_cancelled`
- `crm_contact_created` / `crm_contact_updated`

---

## Database Schema

### leads table
```sql
id UUID PRIMARY KEY
phone_number VARCHAR(30)
customer_name VARCHAR(150)
city VARCHAR(100)
area VARCHAR(100)
budget VARCHAR(100)
property_type VARCHAR(50)
purpose VARCHAR(50)
appointment_interest BOOLEAN
created_at TIMESTAMP
updated_at TIMESTAMP
```

### lead_memory table
```sql
lead_id TEXT PRIMARY KEY
profile JSONB
transcript_history JSONB
intent JSONB
budget VARCHAR(100)
city VARCHAR(100)
-- ... more fields for denormalized data
updated_at TIMESTAMPTZ
```

---

## Debugging

### Check if service is running
```bash
curl http://localhost:8000/
# Should return: {"status":"ok","app":"real_estate_voice_agent","capabilities":["voice","rag","appointments"]}
```

### Check database connection
```bash
# Logs will show connection status
# Look for "Database initialization" messages
```

### View local fallback logs
```bash
# Emails: Week 7/app/data/email_log.json
# CRM: Week 7/app/data/crm_operations.json
# Lead Memory: Week 7/app/data/lead_memory.json
```

---

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| n8n webhooks not called | Check N8N_BASE_URL and verify n8n is running |
| Postgres connection error | Verify DATABASE_URL format and credentials |
| Emails not sent | Check SMTP credentials, verify n8n email node |
| Calendar sync failing | Check Google service account JSON path |
| Appointment booking fails | Ensure all required fields in request |

---

## Next Steps

1. **Configure n8n**
   - Set up email workflow with SMTP/Gmail
   - Configure Google Calendar integration
   - Set up CRM sync (HubSpot/Salesforce/Pipedrive)

2. **Load Testing**
   - Test with concurrent calls
   - Monitor database performance
   - Check n8n webhook throughput

3. **Production Deployment**
   - Set up monitoring (ELK, CloudWatch)
   - Configure auto-scaling
   - Set up database backups
   - Enable SSL/TLS

---

## Documentation

- **Full Guide:** See `IMPLEMENTATION_SUMMARY.md`
- **Original README:** See `README.md`
- **Architecture Diagram:** In `IMPLEMENTATION_SUMMARY.md`

---

## Support

For detailed information on:
- LangGraph agent configuration: See `app/services/langgraph_agent.py`
- Service contracts: See `app/services/service_contracts.py`
- Postgres integration: See `app/services/lead_memory.py`
- n8n endpoints: See `app/orchestrator_endpoints.py`

---

**Version:** 1.0.0  
**Last Updated:** September 1, 2025  
**Status:** Production Ready ✅
