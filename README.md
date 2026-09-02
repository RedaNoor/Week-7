# Week 7 Capstone Summary

## What this project is doing

This project is a real-estate calling assistant for a property company. It takes inbound calls, reads what the caller wants, matches that against the property catalog, and helps move the lead toward a visit or a follow-up.

The core idea is simple: a call comes in, the backend reads the transcript, extracts the actual requirement, and then uses that data to recommend properties or trigger the next step.

## The stack in plain English

- Twilio handles the phone call
- Vapi runs the live voice conversation
- Deepgram can transcribe the audio if needed
- FastAPI handles the webhook and app logic
- PostgreSQL stores leads, sessions, appointments, and memory
- the property data is the source of truth for property recommendations
- email, calendar, and CRM actions sit on top of the main flow

## What the assistant is meant to do

The call flow is designed to:

- greet the caller politely in UrduLish
- understand the buyer intent
- collect budget, area, city, property type, and purpose
- remember what was said earlier in the call
- recommend only properties that exist in the catalog
- answer the basic objections without guessing
- help book a visit when the user is interested

## How the project grows beyond the basic bot

Once the basic voice flow is working, the project adds the business side of the process:

- detect when a buyer wants to see a property
- validate the time slot
- create an appointment record
- create a calendar event
- email the assigned person
- log the interaction and carry it forward for follow-up

## Set it up in order

1. Start with the property knowledge base.
2. Set up the backend and the environment values.
3. Configure the Twilio webhook.
4. Set up the Vapi assistant and connect it to your FastAPI webhook.
5. Start the appointment flow.
6. Test the lead extraction and booking process.

## How the voice flow fits together

The usual pattern is:

- Twilio answers the call
- Vapi runs the live conversation
- Vapi sends transcript and event data to FastAPI
- the backend stores memory, logs, and intent data
- the backend returns structured results or triggers the booking flow

### Example webhook route

```python
from fastapi import FastAPI, Request
from app.services.call_intent import detect_intent
from app.services.lead_memory import lead_memory
from app.services.property_matcher import match_properties

app = FastAPI()

@app.post('/vapi/webhook')
async def vapi_webhook(request: Request):
    payload = await request.json()

    call_id = payload.get('call_id') or payload.get('id') or 'unknown'
    transcript = payload.get('transcript', '')
    intent = detect_intent(transcript)
    profile = lead_memory.build_profile(transcript)
    recommendations = match_properties(profile)

    lead_memory.upsert_lead(call_id, {
        'transcript': transcript,
        'intent': intent,
        'profile': profile,
        'recommendations': recommendations,
    })

    return {
        'status': 'received',
        'call_id': call_id,
        'intent': intent,
        'profile': profile,
        'recommendations': recommendations,
    }
```

### Example payload

```json
{
  "call_id": "call_123",
  "transcript": "Budget 3 crore hai. DHA mein family home chahiye.",
  "status": "completed",
  "intent": "book_visit"
}
```

## Environment variables

Copy the sample config and fill in your values:

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

## Project layout

The main project is one app. The root app folder handles the call webhook, lead memory, property matching, appointment booking, calendar, email, and CRM hooks. The data, documents, knowledge_base, and evaluation folders hold the catalog and retrieval logic. The docs folder contains the design notes and conversation-flow thinking.

### Run the app

```powershell
cd "Week 7"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python apply_schema.py
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### Knowledge base and evaluation

Set a real DATABASE_URL, enable PostgreSQL pgvector, then run:

```powershell
python knowledge_base/data_loader.py
python knowledge_base/rag_pipeline.py
python knowledge_base/recommendation_engine.py
python evaluation/rag_evaluation.py
```

The system should only recommend properties that come from the structured data or verified retrieval results. It should not invent prices, availability, amenities, legal claims, or appointment confirmations.
