# Week 7 Capstone Summary

## Project: Real-Estate AI Voice Agent

This project is a simplified but realistic production-style AI voice assistant for a real-estate company. The goal is to answer inbound calls, understand buyer intent, recommend properties from verified data, remember context, and help schedule property visits.

## Final architecture

- Twilio handles the actual phone call entry
- Vapi is the live conversational assistant layer
- Deepgram can be used for transcription when needed
- FastAPI manages backend webhooks and business logic
- Postgres stores leads, sessions, appointments, and logs
- Day 2 property knowledge base is the trusted source for recommendations
- Day 4 adds appointment booking, calendar sync, and email notifications

## Simplified stack

- FastAPI
- Twilio
- Vapi
- Deepgram
- PostgreSQL
- Python services
- Google Calendar API
- SMTP email service

## Day 3 objective
Day 3 focuses on building the voice agent logic and conversation flow.

The assistant should:
- greet the caller politely in UrduLish
- understand the customer intent
- collect details such as budget, area, city, property type, and purpose
- remember earlier details during the call
- recommend properties from verified data only
- answer price, location, trust, and investment objections calmly

## Day 4 objective
Day 4 turns the conversation into a working business workflow.

The assistant should:
- identify when the customer wants a visit
- validate the property and time slot
- create an appointment record
- create a Google Calendar event
- email the assigned employee
- log the interaction and follow up later if needed

## Setup order

1. Start with the Day 2 property knowledge base.
2. Set up Day 3 backend and your `.env` file.
3. Configure Twilio webhook for incoming calls.
4. Set up Vapi assistant and connect it to your FastAPI webhook.
5. Start the Day 4 appointment backend.
6. Test lead extraction and booking flow.

## How Vapi integrates

This is the recommended pattern:

- Twilio answers the incoming call
- Vapi runs the live voice conversation
- Vapi sends transcript and event data to your FastAPI backend
- your backend stores memory, logs, and intent data
- your backend returns structured results or triggers booking actions

### Vapi setup steps

1. Create a new Vapi assistant from the Vapi dashboard.
2. Choose a natural voice and set a clear system prompt for a Pakistani real-estate sales agent.
3. In the assistant settings, add your webhook URL:
   `https://your-ngrok-url/vapi/webhook`
4. In your backend, define a FastAPI route to accept the JSON payload that Vapi sends.
5. Parse the incoming JSON and extract the call ID, transcript, intent, and lead profile.
6. Save the collected information in memory or Postgres so the conversation can remember budget, city, area, property type, and purpose.
7. Use that data to suggest matching properties from the Day 2 knowledge base or trigger the appointment flow when the client shows interest.

### What you need to do manually

You do not need to write the whole Vapi integration by hand in code. You need to do these steps manually in the Vapi dashboard and in your backend:

- Create the assistant
- Add the webhook URL
- Set the system prompt
- Start the FastAPI server locally
- Expose it with ngrok
- Test the call
- Check whether the webhook receives the transcript and metadata

### Example backend webhook route

```python
from fastapi import FastAPI, Request
from app.services.call_intent import detect_intent
from app.services.lead_memory import lead_memory
from app.services.property_matcher import match_properties

app = FastAPI()

@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    payload = await request.json()

    call_id = payload.get("call_id") or payload.get("id") or "unknown"
    transcript = payload.get("transcript", "")
    intent = detect_intent(transcript)
    profile = lead_memory.build_profile(transcript)
    recommendations = match_properties(profile)

    lead_memory.upsert_lead(call_id, {
        "transcript": transcript,
        "intent": intent,
        "profile": profile,
        "recommendations": recommendations,
    })

    return {
        "status": "received",
        "call_id": call_id,
        "intent": intent,
        "profile": profile,
        "recommendations": recommendations,
    }
```

This is the part you need to implement in code manually if you want the integration to work.

### Example Vapi webhook payload

```json
{
  "call_id": "call_123",
  "transcript": "Budget 3 crore hai. DHA mein family home chahiye.",
  "status": "completed",
  "intent": "book_visit"
}
```

### Example FastAPI route

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    payload = await request.json()
    transcript = payload.get("transcript", "")
    call_id = payload.get("call_id", "unknown")

    print("Call ID:", call_id)
    print("Transcript:", transcript)

    return {"status": "received", "call_id": call_id}
```

## Environment variables

Copy the sample files from Day 3 and Day 4 and fill out your keys:

```env
VAPI_API_KEY=your_vapi_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+12345678901
BASE_URL=https://your-ngrok-domain.ngrok-free.app
DATABASE_URL=postgresql://username:password@localhost:5432/real_estate_voice
```

## Submission notes

This is intentionally simplified for student use. It demonstrates the right production pattern without requiring a full custom call-streaming pipeline from scratch. The objective is to show understanding of voice AI, lead qualification, memory, business workflows, and automation.

## Unified project layout

Week 7 is now one project. The root `app` combines the Vapi/Twilio webhook,
lead memory, property matching, appointment booking, calendar, email, and CRM
interfaces. `data`, `documents`, `knowledge_base`, and `evaluation` contain
the verified catalog and RAG pipeline. `docs` contains the Day 1 architecture,
conversation, UrduLish, Fish Audio, and system-prompt solutions.

### Run the unified agent

```powershell
cd "Week 7"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python apply_schema.py
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Test `http://127.0.0.1:8001/`. For Vapi, expose port `8001` with Cloudflare
Tunnel and configure `https://YOUR-TUNNEL/vapi/webhook`. Keep both terminals
running. The root API also exposes `/lead/analyze`, `/appointments`,
`/deepgram/webhook`, and the optional Twilio routes.

### Knowledge base and evaluation

Set a real `DATABASE_URL`, enable PostgreSQL `pgvector`, then run:

```powershell
python knowledge_base/data_loader.py
python knowledge_base/rag_pipeline.py
python knowledge_base/recommendation_engine.py
python evaluation/rag_evaluation.py
```

The agent must only recommend available properties returned by the structured
retriever or verified RAG context. It must not invent prices, availability,
amenities, legal claims, investment returns, or appointment confirmations.

## Core benefits

- real-world telephony flow
- natural conversation design
- memory and lead tracking
- grounded property recommendations
- business workflow automation
- realistic capstone submission quality
