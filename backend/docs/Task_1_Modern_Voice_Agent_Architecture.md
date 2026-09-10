## Task 1: Voice Agent Architecture

### Objective

The goal here is to map out a practical architecture for a real-estate calling assistant. It should handle a phone call, understand what the customer wants, fetch the right property information, keep track of context, and respond in a natural Pakistani UrduLish style.

### Proposed setup

```text
Customer
  │
  ▼
Twilio
  │
  ▼
Deepgram / speech-to-text
  │
  ▼
FastAPI backend
  │
  ▼
Conversation logic
  ├─ memory
  ├─ property lookup
  └─ business tools
      ├─ Postgres
      ├─ calendar
      ├─ email
      └─ CRM
  │
  ▼
Voice response
```

### Speech-to-text flow

The call comes in through the phone platform. After that, the speech is turned into text and passed to the backend. At that point we can read the transcript and decide what it means.

### Conversation logic

The transcript is reviewed to decide:

1. what the customer wants
2. what details are missing
3. whether the system needs more questions
4. whether a property lookup is needed
5. whether an action like a visit or follow-up should trigger

### Knowledge lookup

The knowledge layer is meant to give verified answers about:

- property descriptions
- FAQs
- company policies
- local area information
- general sales info

The system should prefer the structured database for exact facts like price, area, and bedroom count. The retrieval layer is better for contextual text, brochures, and FAQs.

### Memory

Short-term memory keeps track of the current conversation. Long-term memory is useful for future calls when the same lead or context needs to be revisited.

This matters because a real sales call rarely follows a script. People change budget, location, or timeline mid-call.

### Practical takeaway

The architecture should be simple enough to debug and strong enough to handle a real inbound sales workflow. The important idea is that the system is not just replying to text. It is connecting the call to the actual business process behind it.
