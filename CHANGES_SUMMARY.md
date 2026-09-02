# Change Summary

## What changed

This project evolved from a basic demo into a more complete real-estate sales workflow. The main additions were the conversation flow, lead storage, workflow hooks, and the supporting pieces for email, calendar, and CRM tasks.

The goal was not to add abstraction just for the sake of it. It was to make the backend actually useful when a lead comes in and needs a real next step.

---

## Main updates

### Conversation flow and tools
The call logic was expanded so it can look at the transcript, extract the lead profile, and decide what action is needed next.

This includes:

- extracting budget and area from the conversation
- identifying the property intent
- matching the user to likely properties
- checking prior memory for the same lead
- triggering follow-up actions when the lead is interested

### Workflow endpoints
New HTTP endpoints were added to handle the operational side of the project. These endpoints let the app process a turn, sync a lead, fetch context, and manage the handoff to other systems.

### Postgres memory
The lead memory layer was hardened so the app can store data in a more consistent way. This helps when the system needs to remember who the lead is, what they asked for, and what happened earlier in the process.

### External service hooks
The app now has clearer contracts for email, calendar, and CRM actions. Even when the real service is down, the code keeps a local fallback so the project stays easy to test and debug.

---

## File-level notes

### app/services/langgraph_agent.py
This file was expanded to bind the conversation logic to tools and handle the flow from transcript to action.

### app/services/lead_memory.py
This module now does more than keep a JSON cache. It writes to Postgres in a more consistent way and keeps the lead profile in a form that is easier to query.

### app/services/n8n_webhook.py
The webhook layer was extended so events can be published to the workflow automation stack when important things happen.

### app/main.py
The FastAPI app now includes the workflow router so all of these endpoints are available in one place.

### app/orchestrator_endpoints.py
This is the main endpoint file for lead processing and workflow actions. It connects the conversation flow with the storage and automation pieces.

### app/services/service_contracts.py
This is the utility layer for email, calendar, and CRM actions. It adds structure so the app knows what to do if a service call fails.

---

## Why it matters

The real change is not the number of lines of code. It is the fact that the project now behaves more like a real sales workflow than a static demo. It can receive a call, understand the need, store the lead, and route the process toward an actual sales action.
