# Files Manifest

## Overview

This project has a few main pieces: the app itself, the data files, the knowledge base, and the design notes. The code is separated enough that you can usually trace a lead from the transcript to the final follow-up.

---

## Main Python files

### app/orchestrator_endpoints.py
This is the main workflow API layer. It contains the HTTP endpoints used to process the lead and trigger the internal flow.

### app/services/service_contracts.py
This defines the interfaces for the email, calendar, and CRM steps. It keeps the external service logic organized and easier to replace.

### app/services/langgraph_agent.py
This is where the call logic and tool use live. It decides what should happen with the lead after the transcript is read.

### app/services/lead_memory.py
This stores lead profile and session state in Postgres so the app can remember context and keep data consistent.

### app/main.py
This is the FastAPI app entry point and router setup.

---

## Documentation files

### IMPLEMENTATION_SUMMARY.md
Project overview and architecture notes.

### QUICK_REFERENCE.md
Fast setup and testing guide.

### DEPLOYMENT_GUIDE.md
Local deployment and environment setup notes.

### CHANGES_SUMMARY.md
Short summary of the changes and what they were for.

### docs/
The design notes for architecture, conversation flow, UrduLish persona, evaluation, and prompt building.

---

## Data and knowledge files

- data/ contains the catalog and structured property data
- documents/ contains source text and brochures
- knowledge_base/ contains the retrieval and recommendation code
- evaluation/ contains the evaluation scripts and the test data

These are the pieces that feed the recommendation and verification logic.

---

## Practical takeaway

The project is built to be followed by someone who wants to understand how a lead actually moves through the system: transcript in, structured profile out, matching and memory on top, then follow-up actions after the call.
