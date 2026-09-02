# Deployment & Setup Guide

## Prerequisites

- Python 3.10+
- PostgreSQL 13+
- n8n instance (local or cloud)
- Google Cloud account with Calendar API enabled
- SMTP server access (Gmail, SendGrid, Resend, etc.)

## Step 1: Update Dependencies

```bash
cd "c:\Users\ridan\Documents\Netixsol\Week 7"

# Upgrade pip
python -m pip install --upgrade pip

# Install/upgrade LangChain and related packages
pip install --upgrade -r requirements.txt

# The requirements.txt now has compatible versions:
# - langgraph==0.2.18
# - langchain==0.2.6
# - langchain-openai==0.1.8
# - langchain-community==0.2.6
```

## Step 2: Configure Environment

Create `.env` file in project root:

```bash
# App Configuration
APP_ENV=production
APP_NAME=real_estate_voice_agent
LOG_LEVEL=INFO

# Database Configuration
DATABASE_URL=postgresql://real_estate_user:password@localhost:5432/real_estate_db

# LLM Configuration
OPENAI_API_KEY=sk-your-key-here

# External APIs
VAPI_API_KEY=your-vapi-key
DEEPGRAM_API_KEY=your-deepgram-key

# n8n Configuration
N8N_BASE_URL=http://localhost:5678/webhook

# Google Calendar
GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/google-service-account.json
GOOGLE_CALENDAR_ID=primary

# Email/SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
```

## Step 3: Set Up PostgreSQL Database

```bash
# Create database
createdb real_estate_db

# Connect and create schema
psql -U postgres -d real_estate_db < database_schema.sql

# Verify tables created
psql -U postgres -d real_estate_db -c "\dt"
```

## Step 4: Initialize Application

```bash
cd "c:\Users\ridan\Documents\Netixsol\Week 7"

# Run database initialization
python -c "from app.services.db_store_enhanced import init_db; init_db(); print('Database initialized')"

# Verify data directories created
ls -la app/data/
```

## Step 5: Start the Application

```bash
# Development mode
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Step 6: Verify Installation

```bash
# Test health check
curl http://localhost:8000/

# Should return:
# {"status":"ok","app":"real_estate_voice_agent","capabilities":["voice","rag","appointments"]}
```

## Step 7: Configure n8n

### Create Webhooks in n8n

1. **Lead Created Webhook**
   - URL: `http://your-domain/orchestrator/n8n-webhook-confirmation`
   - Method: POST
   - Listen for: `lead-created` events from real estate app

2. **Appointment Created Webhook**
   - URL: `http://your-domain/orchestrator/n8n-webhook-confirmation`
   - Method: POST
   - Listen for: `appointment-scheduled` events

3. **Email Service Workflow**
   - Trigger: n8n webhook listening to `email-booking-sent`
   - Action: Send email via SMTP/Gmail/Resend
   - Template: Use variables from payload

4. **Calendar Service Workflow**
   - Trigger: n8n webhook listening to `calendar-event-created`
   - Action: Create Google Calendar event
   - Pass attendee email to Google Calendar API

5. **CRM Sync Workflow**
   - Trigger: n8n webhook listening to `crm-contact-created`
   - Action: Create contact in HubSpot/Salesforce/Pipedrive
   - Sync followup rules

## Step 8: Configure External Services

### Google Calendar Setup

1. Create service account in Google Cloud Console
2. Download JSON credentials
3. Share calendar with service account email
4. Set `GOOGLE_SERVICE_ACCOUNT_FILE` to JSON path

### Gmail/SMTP Setup

1. Enable 2-factor authentication on Gmail
2. Generate app password: https://myaccount.google.com/apppasswords
3. Set SMTP credentials in .env

### HubSpot/Salesforce Setup (Optional)

1. Get API key from CRM platform
2. Configure n8n CRM nodes with credentials
3. Map fields appropriately

## Step 9: Test Complete Workflow

### Test 1: Simple Lead Analysis
```bash
curl -X POST http://localhost:8000/lead/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Budget 3 crore hai. DHA mein family home chahiye.",
    "session_id": "test_session_1"
  }'
```

### Test 2: Agent Processing
```bash
curl -X POST http://localhost:8000/orchestrator/process-turn \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_1",
    "lead_id": "lead_1",
    "transcript": "Budget 2 crore. Gulshan-e-Iqbal apartment."
  }'
```

### Test 3: Postgres Sync
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

### Test 4: Appointment Creation
```bash
curl -X POST http://localhost:8000/appointments \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Ali Khan",
    "client_phone": "+923001234567",
    "property_id": "prop_001",
    "property_title": "Gulshan-e-Iqbal Apartment",
    "scheduled_at": "2025-09-15T14:00:00",
    "employee_email": "agent@realestate.com"
  }'
```

### Test 5: Followup Creation
```bash
curl -X POST http://localhost:8000/orchestrator/create-followup \
  -H "Content-Type: application/json" \
  -d '{
    "lead_id": "lead_1",
    "note": "Client interested, follow up tomorrow",
    "scheduled_for": "2025-09-02T10:00:00",
    "priority": "high"
  }'
```

## Step 10: Monitor & Debug

### Check Logs

```bash
# FastAPI logs will show in terminal
# Look for:
# - "Database initialization"
# - "n8n webhook" messages
# - Any error traces

# Application data stored in:
ls -la app/data/
# - lead_memory.json (in-memory lead profiles)
# - email_log.json (fallback emails)
# - crm_operations.json (CRM operations log)
# - crm_log.json (legacy CRM log)
```

### Database Debugging

```bash
# Connect to PostgreSQL
psql -U real_estate_user -d real_estate_db

# View leads
SELECT * FROM leads;

# View call sessions
SELECT * FROM call_sessions;

# View appointments
SELECT * FROM appointments;

# View lead memory
SELECT lead_id, budget, city, area FROM lead_memory;
```

### Check n8n Integration

```bash
# Verify n8n is running
curl http://localhost:5678/api/health

# Check webhook deliveries in n8n logs
# Look for POST requests to your webhook endpoints
```

## Troubleshooting

### Import Errors

**Error:** `ImportError: cannot import name 'convert_to_openai_data_block'`

**Solution:** Update LangChain dependencies:
```bash
pip install --upgrade langchain==0.2.6 langchain-openai==0.1.8 langgraph==0.2.18
```

### Database Connection Failed

**Error:** `could not translate host name "localhost" to address`

**Solution:** 
- Verify PostgreSQL is running
- Check DATABASE_URL format
- Ensure database exists: `createdb real_estate_db`

### n8n Webhooks Not Triggering

**Error:** Events published to n8n but no workflow execution

**Solution:**
- Verify n8n is running: `curl http://localhost:5678/api/health`
- Check N8N_BASE_URL in .env
- Verify webhook URLs in n8n match exactly
- Check n8n logs for POST request deliveries

### Email Not Sending

**Error:** Emails queued but not delivered

**Solution:**
- Check SMTP credentials in .env
- For Gmail: Use app password, not regular password
- Enable "Less secure apps" if using Gmail
- Check app/data/email_log.json for fallback entries
- Verify n8n email node configuration

## Performance Optimization

### Database Indexes

Already created:
```sql
CREATE INDEX idx_lead_memory_phone ON lead_memory(phone_number);
CREATE INDEX idx_lead_memory_city ON lead_memory(city);
CREATE INDEX idx_leads_phone ON leads(phone_number);
CREATE INDEX idx_sessions_lead ON call_sessions(lead_id);
CREATE INDEX idx_appointments_lead ON appointments(lead_id);
CREATE INDEX idx_followups_lead ON followups(lead_id);
```

### Connection Pooling

SQLAlchemy uses connection pooling by default:
```python
# From db_store_enhanced.py
engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,  # Verify connections before use
    pool_size=20,        # Number of connections to keep
    max_overflow=40      # Additional connections when needed
)
```

### Caching

Lead memory is cached in-memory:
```python
# Quick access without database query
profile = lead_memory.get_lead(lead_id)

# Syncs to Postgres asynchronously
```

## Production Deployment

### Using Gunicorn

```bash
pip install gunicorn

gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

### Using Docker

```dockerfile
FROM python:3.11

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/
COPY database_schema.sql .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

Set in production:
```bash
APP_ENV=production
LOG_LEVEL=WARNING
DATABASE_URL=<production-db-url>
OPENAI_API_KEY=<production-key>
N8N_BASE_URL=<production-n8n-url>
```

## Monitoring & Alerts

### Recommended Monitoring

1. **Application Metrics**
   - Request latency
   - Error rates
   - Database query time
   - n8n webhook latency

2. **Database Metrics**
   - Connection count
   - Query performance
   - Backup status
   - Disk space

3. **External Services**
   - n8n availability
   - Email delivery rate
   - Calendar sync status
   - CRM API responses

### Logging Setup

Configure centralized logging:
```python
# In app/services/service_contracts.py
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Send to CloudWatch, ELK, or similar
```

## Maintenance Tasks

### Daily
- Monitor error logs
- Check n8n webhook deliveries
- Verify email delivery

### Weekly
- Review database performance
- Check backup status
- Test failover mechanisms

### Monthly
- Clean up old session logs
- Archive old lead data
- Update dependencies
- Security review

## Support & Documentation

- **Quick Start:** See `QUICK_REFERENCE.md`
- **Full Implementation:** See `IMPLEMENTATION_SUMMARY.md`
- **Original README:** See `README.md`

---

**Last Updated:** September 1, 2025  
**Version:** 1.0.0 - Production Ready
