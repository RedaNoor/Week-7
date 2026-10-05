# Week 8 Completion Matrix

This matrix compares the current repository with the Week 8 assignment. It
intentionally distinguishes a working baseline from requirements that still
need production-grade implementation.

Legend: **Complete** means implemented and locally validated. **Partial** means
there is a working baseline but important assignment scope is missing.

## Day 1: Data Understanding, EDA, and Features

| Requirement | Status | Evidence / gap |
| --- | --- | --- |
| Property dataset with 5,000+ rows | Complete | `dataset_properties.csv` has 168,446 raw rows; 168,443 valid rows are served |
| Lead dataset with 3,000+ rows | Complete | `scripts/prepare_week8_data.py` generates 3,000 deterministic leads |
| Data dictionary | Complete | `backend/data/week8/DATA_DICTIONARY.md` |
| Missing-value and unit normalization | Partial | Size normalization and numeric coercion exist; full cleaning report is missing |
| Duplicate and outlier handling | Missing | No reproducible duplicate removal or IQR/Z-score pipeline yet |
| EDA charts and business insights | Partial | Dashboard has city/type market charts; price distribution, correlation heatmap, and lead EDA are missing |
| Ten engineered features | Complete | Enrichment creates amenity, distance, age, tier, size, floor, corner, and facing features |
| Encoding, scaling, reusable pipeline | Partial | One-hot encoding and scaling exist; target-encoding comparison is missing; evaluation script documents 70/15/15 |

## Day 2: Property Valuation

| Requirement | Status | Evidence / gap |
| --- | --- | --- |
| Baseline model comparison | Complete | `scripts/week8_evaluate.py` compares median, linear, Ridge, Lasso, and Random Forest |
| Linear, Ridge, Lasso, Random Forest, XGBoost, LightGBM, CatBoost comparison | Partial | Linear/Ridge/Lasso/Random Forest exist; optional boosting model comparison is missing |
| MAE, RMSE, R2, MAPE and error slices | Partial | Evaluation script produces MAE/RMSE/R2/MAPE; city and price-range error slices are missing |
| Optuna tuning and MLflow tracking | Missing | No Optuna or MLflow integration exists |
| Prediction range and listed-price verdict | Complete | `/predict/price` and the dashboard return both |

## Day 3: Lead Scoring and Explainability

| Requirement | Status | Evidence / gap |
| --- | --- | --- |
| Lead classifier | Partial | Balanced logistic regression and Random Forest comparison exists over deterministic leads |
| Class weights, SMOTE, threshold comparison | Partial | Class weights exist; SMOTE and threshold experiments are missing |
| Precision, recall, F1, ROC-AUC, PR-AUC, calibration, Precision@Top-20% | Partial | Evaluation script produces precision/recall/F1/ROC-AUC/PR-AUC/Top-20%; calibration is missing |
| Hot / Warm / Cold segmentation | Complete | API and Streamlit dashboard support all three segments |
| SHAP global and local explanations | Partial | Local SHAP contributions are attempted; global plots and bias analysis are missing |

## Day 4: Serving, Assistant, and Dashboard

| Requirement | Status | Evidence / gap |
| --- | --- | --- |
| FastAPI price, lead, explain, batch, health, and model-info endpoints | Complete | `backend/app/ml_endpoints.py` |
| Pydantic validation and OOD rejection | Complete | Request bounds, supported-city checks, and training-range checks exist |
| Streamlit/Gradio dashboard | Complete | `dashboard_week8.py`, run on port 8501 |
| Lead list, badges, valuation, insights, SHAP, assistant panel | Partial | All views exist; lead scoring reviews a responsive sample rather than all 3,000 rows |
| LangGraph model tools and no-invented-price guardrail | Complete | `predict_fair_property_price` and `score_sales_lead` are registered tools |
| Voice-agent and hot-lead email integration | Partial | Vapi end-of-call scoring and Hot notification are wired; production SMTP credentials are still required |
| Prompt-injection tests for the ML assistant | Partial | Week 7 guardrail tests exist; Week 8-specific assistant tests are missing |

## Day 5: MLOps and Handover

| Requirement | Status | Evidence / gap |
| --- | --- | --- |
| Data and prediction drift detection | Complete | `scripts/week8_drift.py` emits PSI report and retrain thresholds |
| Retraining and rollback pipeline | Partial | `scripts/week8_retrain.py` serializes/promotes/rolls back; automated holdout promotion is still missing |
| Dockerized backend and dashboard | Complete | `Dockerfile` and `docker-compose.week8.yml` |
| CI tests on every push | Complete | `.github/workflows/ci.yml` |
| Model cards and data documentation | Complete | `backend/data/week8/MODEL_CARD.md` and `DATA_DICTIONARY.md` |
| API and sales-agent user guide | Partial | `WEEK8_SETUP.md` documents local use; production handover guide is incomplete |

## Overall assessment

The repository now has a working Week 8 baseline plus evaluation reports,
drift monitoring, model-tool integration, Docker, CI, and a Streamlit
dashboard. The capstone is **not yet fully production-complete** because
boosting-model comparison, duplicate/outlier cleaning, calibration, global
SHAP/bias analysis, automated holdout promotion, and production credentials
remain for handover.

Use this matrix as the handover checklist before calling the capstone production-ready.