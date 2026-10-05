---
noteId: "9a782180bc9111f198be6f29d21f3021"
tags: []

---

# Week 8 Complete Setup and Testing Guide

This guide is for the current Windows project at `C:\Users\ridan\Documents\Week 7`.
It tests the Week 8 valuation and lead-scoring features without replacing the
working Week 7 property catalog.

## 1. Prerequisites

Install:

- Python 3.11 or newer
- Node.js 20 or newer, only if you want to run the website
- Git, optional

PostgreSQL, SMTP, OpenAI, Vapi, and Twilio are **not required** for the local
ML smoke test. The backend starts without a database connection in development.

Open PowerShell in the project root:

```powershell
Set-Location "C:\Users\ridan\Documents\Week 7"
```

## 2. Create the Python environment

Run once:

```powershell
py -3.11 -m venv backend\venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& .\backend\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

For later sessions, only run:

```powershell
& .\backend\venv\Scripts\Activate.ps1
```

If `py -3.11` is unavailable, use `python -m venv backend\venv` instead.

## 3. Configure local environment

The backend reads `.env` relative to its working directory. Create it once:

```powershell
if (-not (Test-Path backend\.env)) {
    Copy-Item backend\.env.example backend\.env
}
```

For local testing, these values are sufficient:

```ini
APP_ENV=development
LOG_LEVEL=INFO
DATABASE_URL=
REQUIRE_AUTH=false
API_KEY=local-development-key
ADMIN_API_KEY=local-development-admin-key
TRUSTED_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000
ML_MODEL_BUNDLE_PATH=backend/data/week8/models/model_bundle.joblib
ML_REQUIRE_ARTIFACT=false
ML_MAX_BATCH_ROWS=1000
```

Do not commit `backend\.env`. Do not put real passwords or API keys in this
guide or in source control.

## 4. Prepare the Week 8 datasets

The downloaded [dataset_properties.csv](dataset_properties.csv) is preserved.
The preparation script creates derived files only:

```powershell
python scripts\prepare_week8_data.py
```

Expected output:

```text
wrote 168446 enriched properties and 3000 leads to ...\backend\data\week8
```

Generated files:

- [properties_enriched.csv](backend/data/week8/properties_enriched.csv)
- [leads.csv](backend/data/week8/leads.csv)

The enrichment adds normalized marla size, amenity score, society tier,
approximate distances, property age, floors, corner, and park-facing fields.
Area amenities are deterministic assumptions, documented in
[DATA_DICTIONARY.md](backend/data/week8/DATA_DICTIONARY.md). They must be
replaced with verified GIS or listing data before commercial use.

## 5. Run automated tests

Run the focused Week 8 test:

```powershell
$env:PYTHONPATH = "backend"
python -m pytest -q backend\tests_week8_ml.py
```

Expected result:

```text
1 passed
```

Also compile the changed Python files:

```powershell
python -m compileall -q backend\app\ml_endpoints.py backend\app\services\ml_service.py scripts\prepare_week8_data.py
```

## 6. Start the backend API

Use a new PowerShell window, then run:

```powershell
Set-Location "C:\Users\ridan\Documents\Week 7\backend"
& .\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --port 8001
```

Keep this window open. The API is available at:

- <http://localhost:8001/docs>
- <http://localhost:8001/health>
- <http://localhost:8001/model/info>

The first valuation or model-info request trains the deterministic baseline
model and may take several seconds. Later requests reuse it in that process.

## 7. Test API health

In another PowerShell window:

```powershell
Invoke-RestMethod http://localhost:8001/health | ConvertTo-Json
Invoke-RestMethod http://localhost:8001/model/info | ConvertTo-Json -Depth 6
```

The health response should contain `"status": "ok"`. The model-info response
contains valuation MAE/R², lead ROC-AUC, model version, and source dataset.

## 8. Test price prediction

Use a property shape represented in the supplied dataset:

```powershell
$priceBody = @{
    city = "Islamabad"
    location = "G-10"
    property_type = "Flat"
    area_marla = 4
    bedrooms = 2
    bathrooms = 2
    listed_price = 10000000
    province_name = "Islamabad Capital"
    purpose = "For Sale"
    area_type = "Marla"
    latitude = 33.67989
    longitude = 73.01264
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri http://localhost:8001/predict/price `
    -Method Post `
    -ContentType "application/json" `
    -Body $priceBody | ConvertTo-Json -Depth 6
```

The response includes:

- predicted price in PKR
- lower and upper estimate range
- listed price
- `Fair`, `Underpriced`, or `Overpriced` verdict
- model version
- valuation disclaimer

Test the explanation endpoint:

```powershell
Invoke-RestMethod `
    -Uri http://localhost:8001/explain/price `
    -Method Post `
    -ContentType "application/json" `
    -Body $priceBody | ConvertTo-Json -Depth 8
```

If SHAP is installed successfully, the response also contains
`shap_features`. Otherwise it still returns the documented plain-language
explanation.

## 9. Test lead scoring

```powershell
$leadBody = @{
    source = "call"
    budget_pkr = 10000000
    preferred_city = "Islamabad"
    purpose = "buy"
    number_of_calls = 3
    call_duration_seconds = 300
    response_time_minutes = 20
    visit_booked = 1
    days_since_first_contact = 2
    objection_raised = "none"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri http://localhost:8001/predict/lead-score `
    -Method Post `
    -ContentType "application/json" `
    -Body $leadBody | ConvertTo-Json -Depth 6

Invoke-RestMethod `
    -Uri http://localhost:8001/explain/lead `
    -Method Post `
    -ContentType "application/json" `
    -Body $leadBody | ConvertTo-Json -Depth 8
```

The segment is one of `Hot`, `Warm`, or `Cold`, with a recommended response
time and conversion probability.

## 10. Test validation and guardrails

Unknown cities must be rejected:

```powershell
$badBody = $priceBody -replace 'Islamabad', 'NotARealCity'
try {
    Invoke-RestMethod -Uri http://localhost:8001/predict/price -Method Post -ContentType "application/json" -Body $badBody
} catch {
    $_.ErrorDetails.Message
}
```

Negative areas are rejected by Pydantic:

```powershell
$invalidBody = $priceBody -replace '"area_marla": 4', '"area_marla": -4'
try {
    Invoke-RestMethod -Uri http://localhost:8001/predict/price -Method Post -ContentType "application/json" -Body $invalidBody
} catch {
    $_.ErrorDetails.Message
}
```

The service also rejects area, bedroom, and bathroom values far outside the
training distribution.

## 11. Test CSV batch prediction

Create a small input file:

```powershell
@"
city,location,property_type,area_marla,bedrooms,bathrooms,listed_price,province_name,purpose,area_type
Islamabad,G-10,Flat,4,2,2,10000000,Islamabad Capital,For Sale,Marla
"@ | Set-Content week8_batch.csv
```

Upload it:

```powershell
curl.exe -X POST -F "file=@week8_batch.csv" http://localhost:8001/predict/batch
```

Delete the temporary file afterward:

```powershell
Remove-Item week8_batch.csv
```

## 12. Start the website (optional)

In a third PowerShell window:

```powershell
Set-Location "C:\Users\ridan\Documents\Week 7"
npm install
Copy-Item .env.example .env.local
npm run dev
```

Open <http://localhost:3000>.

## 13. Start the Week 8 Streamlit dashboard

Keep the FastAPI backend running on port `8001`. In another PowerShell
window, from the repository root, run:

```powershell
Set-Location "C:\Users\ridan\Documents\Week 7"
& .\backend\venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
streamlit run dashboard_week8.py --server.port 8501
```

Open <http://localhost:8501>.

The dashboard includes:

- Lead list with model-generated Hot, Warm, and Cold segments
- Lead conversion probability and local explanation
- Property valuation range and Fair / Underpriced / Overpriced verdict
- Optional SHAP contributions when SHAP is available
- City and property-type market insights
- AI assistant panel connected to the existing Week 7 agent

The dashboard reads `dataset_properties.csv` directly. It uses the generated
3,000-lead file when available and otherwise creates the documented
deterministic demonstration leads in memory.

## 14. Run evaluation and MLOps scripts

From the repository root with the backend environment active:

```powershell
$env:PYTHONPATH = "backend"
python scripts\week8_evaluate.py --sample 20000
python scripts\week8_drift.py --price-shift 0.15
python scripts\week8_retrain.py
```

Reports are written under `backend\data\week8\evaluation` and
`backend\data\week8\monitoring`. The current model bundle is written under
`backend\data\week8\models`; use `python scripts\week8_retrain.py --rollback`
to restore the previous bundle.

To run both services with Docker:

```powershell
docker compose -f docker-compose.week8.yml up --build
```

Then open <http://localhost:8501> for Streamlit and
<http://localhost:8001/docs> for FastAPI.
For this production Compose profile, export `API_KEY` before starting; it
requires the prebuilt model bundle and authenticates prediction endpoints.

## 15. Runtime prediction log

Successful predictions are appended to:

[ml_prediction_log.jsonl](backend/data/ml_prediction_log.jsonl)

This file is generated at runtime and should not be committed if it contains
real customer data. Add it to `.gitignore` for a production deployment.

## 16. Common problems

### PowerShell blocks activation

Run this only in the current PowerShell process:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### `No module named app`

Start Uvicorn from `backend`, not the repository root:

```powershell
Set-Location backend
python -m uvicorn app.main:app --reload --port 8001
```

### `No module named pandas` or `sklearn`

Activate the backend environment and reinstall:

```powershell
& .\backend\venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

### Port 8000 is busy

Use another port:

```powershell
python -m uvicorn app.main:app --reload --port 8002
```

Then replace `8001` with `8002` in the test commands.

### Database warning on startup

For Week 8 model testing, a PostgreSQL warning can be ignored if the API
continues to start. Configure a valid `DATABASE_URL` when testing persistent
leads, appointments, and call history.
