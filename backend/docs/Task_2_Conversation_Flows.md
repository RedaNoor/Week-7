## Task 2: Conversation Flows

### Objective

This task is about designing the actual call flow for a real-estate conversation. The call should feel like a real property sales discussion, not like a generic chatbot script.

### Buyer flow

```text
Start
  ↓
Greeting
  ↓
Understand buyer intent
  ↓
Collect budget, area, type, and purpose
  ↓
Search the property catalog
  ↓
Match 2-3 relevant options
  ↓
Ask whether the customer wants to view one
  ↓
Book a visit or send more details
  ↓
End
```

### Rental flow

```text
Start
  ↓
Identify rental requirement
  ↓
Ask for location, budget, rooms, and move-in date
  ↓
Search relevant rentals
  ↓
Recommend options
  ↓
Offer a visit or follow-up
  ↓
End
```

### Commercial flow

```text
Start
  ↓
Identify commercial requirement
  ↓
Collect business type, location, budget, and size need
  ↓
Search matching commercial inventory
  ↓
Recommend likely options
  ↓
Schedule visit or discussion
  ↓
End
```

### Investment flow

This path should be careful. The assistant can present facts and historical trends, but it should not guarantee returns or make claims that cannot be verified.

### Guardrail

The conversation should never promise financial return or say a property is perfect without verified support. This is one of the easiest places for a sales bot to over-claim.

### Practical takeaway

The goal is to keep the conversation moving but still sound human. The caller should feel that the assistant understands the issue and is helping, not reading from a script.
