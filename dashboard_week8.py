"""Streamlit dashboard for the Week 8 valuation and lead-scoring capstone."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATASET_PATH = ROOT / "dataset_properties.csv"
LEADS_PATH = ROOT / "backend" / "data" / "week8" / "leads.csv"
DEFAULT_API_URL = os.getenv("WEEK8_API_URL", os.getenv("BACKEND_URL", "http://127.0.0.1:8000"))
API_KEY = os.getenv("WEEK8_API_KEY", "")

st.set_page_config(
    page_title="Real Estate Hub — ML Dashboard",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Real Estate Hub — AI Property Valuation & Lead Scoring Dashboard"}
)

# Premium CSS theme matching the Next.js website (emerald/teal brand)
st.markdown("""
<style>
  /* Import Google Font */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  /* Sidebar */
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #064e3b 0%, #065f46 50%, #047857 100%) !important;
  }
  [data-testid="stSidebar"] * { color: #d1fae5 !important; }
  [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
  [data-testid="stSidebar"] h3 { color: #ffffff !important; }
  [data-testid="stSidebar"] input { background: rgba(255,255,255,0.1) !important; color: white !important; border: 1px solid rgba(255,255,255,0.2) !important; }

  /* Main content */
  .main .block-container { padding-top: 1.5rem; }

  /* Metric cards */
  [data-testid="stMetric"] {
    background: linear-gradient(135deg, #f0fdf4, #ecfdf5);
    border: 1px solid #a7f3d0;
    border-radius: 12px;
    padding: 1rem 1.25rem;
  }
  [data-testid="stMetricValue"] { font-size: 1.75rem !important; font-weight: 700 !important; color: #065f46 !important; }
  [data-testid="stMetricLabel"] { font-size: 0.75rem !important; color: #047857 !important; font-weight: 500 !important; }

  /* Tab styling */
  .stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    border-bottom: 2px solid #a7f3d0;
  }
  .stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    font-weight: 500;
    color: #047857;
    background: transparent;
    border: 1px solid transparent;
    padding: 0.6rem 1.2rem;
  }
  .stTabs [aria-selected="true"] {
    background: #ecfdf5 !important;
    border-color: #a7f3d0 !important;
    border-bottom-color: #ecfdf5 !important;
    color: #065f46 !important;
  }

  /* Primary buttons */
  .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #059669, #0d9488) !important;
    border: none !important;
    color: white !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.5rem !important;
    transition: opacity 0.2s;
  }
  .stButton > button[kind="primary"]:hover { opacity: 0.9 !important; }

  /* Dataframe */
  [data-testid="stDataFrame"] { border: 1px solid #a7f3d0; border-radius: 8px; overflow: hidden; }

  /* Page title */
  h1 { background: linear-gradient(135deg, #059669, #0d9488); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  h2, h3 { color: #065f46 !important; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner="Loading property market data...")
def load_properties() -> pd.DataFrame:
    frame = pd.read_csv(DATASET_PATH)
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame["bedrooms"] = pd.to_numeric(frame["bedrooms"], errors="coerce").fillna(0)
    frame["baths"] = pd.to_numeric(frame["baths"], errors="coerce").fillna(0)
    frame["area_marla"] = pd.to_numeric(frame["Area Size"], errors="coerce").fillna(0)
    kanal = frame["Area Type"].str.contains("kanal", case=False, na=False)
    square_feet = frame["Area Type"].str.contains("sq|feet", case=False, na=False)
    frame.loc[kanal, "area_marla"] *= 20
    frame.loc[square_feet, "area_marla"] /= 272.25
    return frame[frame["price"] > 0].copy()


@st.cache_data(show_spinner="Loading lead data...")
def load_leads() -> pd.DataFrame:
    if LEADS_PATH.exists():
        return pd.read_csv(LEADS_PATH)
    sys.path.insert(0, str(ROOT))
    from scripts.prepare_week8_data import make_leads

    return make_leads(load_properties(), count=3000)


def api_request(api_url: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    response = requests.post(f"{api_url}{path}", json=payload, headers=headers, timeout=120) if payload is not None else requests.get(f"{api_url}{path}", headers=headers, timeout=120)
    response.raise_for_status()
    return response.json()


def lead_payload(row: pd.Series) -> Dict[str, Any]:
    return {
        "source": str(row.get("source", "call")),
        "budget_pkr": float(row.get("budget_pkr", 0)),
        "preferred_city": str(row.get("preferred_city", "Lahore")),
        "purpose": str(row.get("purpose", "buy")),
        "number_of_calls": float(row.get("number_of_calls", 0)),
        "call_duration_seconds": float(row.get("call_duration_seconds", 0)),
        "response_time_minutes": float(row.get("response_time_minutes", 0)),
        "visit_booked": int(row.get("visit_booked", 0)),
        "days_since_first_contact": float(row.get("days_since_first_contact", 0)),
        "objection_raised": str(row.get("objection_raised", "none")),
    }


def price_payload(values: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "city": values["city"], "location": values["location"], "property_type": values["property_type"],
        "area_marla": values["area_marla"], "bedrooms": values["bedrooms"], "bathrooms": values["bathrooms"],
        "listed_price": values["listed_price"], "province_name": values["province_name"],
        "purpose": "For Sale", "area_type": "Marla", "latitude": values["latitude"],
        "longitude": values["longitude"], "amenity_score": values["amenity_score"], "listing_year": 2019,
    }


def render_leads(api_url: str) -> None:
    leads = load_leads().copy()
    st.subheader("Lead prioritization")
    st.caption("Scores are generated by the Week 8 classification API. The dashboard scores a review sample to keep the UI responsive.")
    sample_size = st.slider("Leads to score", 10, 100, 40, 10)
    sample = leads.head(sample_size).copy()
    scores = []
    with st.spinner("Scoring leads..."):
        for _, row in sample.iterrows():
            try:
                scores.append(api_request(api_url, "/predict/lead-score", lead_payload(row)))
            except requests.RequestException as error:
                st.error(f"Lead scoring API unavailable: {error}")
                return
    scored = pd.concat([sample.reset_index(drop=True), pd.DataFrame(scores)], axis=1)
    scored = scored.sort_values("conversion_probability", ascending=False)
    hot = int((scored["segment"] == "Hot").sum())
    warm = int((scored["segment"] == "Warm").sum())
    cold = int((scored["segment"] == "Cold").sum())
    first, second, third, fourth = st.columns(4)
    first.metric("Reviewed", len(scored))
    second.metric("Hot", hot)
    third.metric("Warm", warm)
    fourth.metric("Cold", cold)
    st.dataframe(
        scored[["lead_id", "source", "preferred_city", "purpose", "budget_pkr", "conversion_probability", "segment", "recommended_response_time"]],
        use_container_width=True,
        hide_index=True,
    )
    selected_id = st.selectbox("Explain a lead", scored["lead_id"].tolist())
    selected = scored[scored["lead_id"] == selected_id].iloc[0]
    if st.button("Explain selected lead", type="primary"):
        try:
            explanation = api_request(api_url, "/explain/lead", lead_payload(selected))
            st.json(explanation)
        except requests.RequestException as error:
            st.error(str(error))


def render_valuation(api_url: str, properties: pd.DataFrame) -> None:
    st.subheader("Property valuation")
    cities = sorted(properties["city"].dropna().unique())
    city = st.selectbox("City", cities)
    city_rows = properties[properties["city"] == city]
    location = st.selectbox("Area / society", sorted(city_rows["location"].dropna().unique()))
    property_type = st.selectbox("Property type", sorted(properties["property_type"].dropna().unique()))
    with st.form("valuation_form"):
        first, second, third = st.columns(3)
        area_marla = first.number_input("Area (marla)", min_value=0.1, value=5.0, step=0.5)
        bedrooms = second.number_input("Bedrooms", min_value=0, value=3, step=1)
        bathrooms = third.number_input("Bathrooms", min_value=0, value=2, step=1)
        listed_price = st.number_input("Listed price (PKR)", min_value=0, value=0, step=100000)
        latitude = float(city_rows["latitude"].median())
        longitude = float(city_rows["longitude"].median())
        submitted = st.form_submit_button("Predict fair value", type="primary")
    if submitted:
        payload = price_payload({"city": city, "location": location, "property_type": property_type, "area_marla": area_marla, "bedrooms": bedrooms, "bathrooms": bathrooms, "listed_price": listed_price or None, "province_name": str(city_rows["province_name"].iloc[0]), "latitude": latitude, "longitude": longitude, "amenity_score": 3})
        try:
            result = api_request(api_url, "/explain/price", payload)
            first, second, third = st.columns(3)
            first.metric("Predicted price", f"PKR {result['predicted_price_pkr']:,}")
            second.metric("Estimate range", f"PKR {result['lower_price_pkr']:,} - {result['upper_price_pkr']:,}")
            third.metric("Verdict", result["verdict"])
            st.warning(result["disclaimer"])
            if result.get("shap_features"):
                st.subheader("Local SHAP contributions")
                st.dataframe(pd.DataFrame(result["shap_features"]), use_container_width=True, hide_index=True)
            st.json(result)
        except requests.RequestException as error:
            st.error(f"Valuation API unavailable: {error}")


def render_market_insights(properties: pd.DataFrame) -> None:
    st.subheader("Market insights")
    by_city = properties.groupby("city", as_index=True)["price"].agg(["count", "mean"]).sort_values("mean", ascending=False)
    by_type = properties.groupby("property_type", as_index=True)["price"].mean().sort_values(ascending=False)
    first, second = st.columns(2)
    first.markdown("**Average listed price by city (PKR)**")
    first.bar_chart(by_city["mean"])
    second.markdown("**Average listed price by property type (PKR)**")
    second.bar_chart(by_type)
    st.dataframe(by_city.rename(columns={"count": "listings", "mean": "average_price_pkr"}), use_container_width=True)
    st.caption("These are descriptive listing statistics, not official market valuations.")


def render_assistant(api_url: str) -> None:
    st.subheader("Sales assistant")
    message = st.text_area("Ask about a valuation or lead", placeholder="DHA mein 10 marla ghar ki fair value kya ho sakti hai?")
    if st.button("Ask assistant", type="primary") and message.strip():
        try:
            answer = api_request(api_url, "/agent/chat", {"session_id": "streamlit_week8", "message": message.strip()})
            st.success(answer.get("reply", "No response returned."))
            if answer.get("recommendations"):
                st.dataframe(pd.DataFrame(answer["recommendations"]), use_container_width=True, hide_index=True)
        except requests.RequestException as error:
            st.error(f"Assistant API unavailable: {error}")


def main() -> None:
    st.title("🏠 Real Estate Hub — ML Command Center")
    st.caption("Property valuation · Lead scoring · Market insights · AI assistant powered by the FastAPI backend")

    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        st.markdown("---")
        api_url = st.text_input("Backend API URL", DEFAULT_API_URL, help="URL of the running FastAPI backend").rstrip("/")
        if st.button("🔄 Clear cache"):
            st.cache_data.clear()
            st.rerun()
        st.markdown("---")
        try:
            info = api_request(api_url, "/model/info")
            st.success(f"✅ Connected  |  {info['model_version']}")
            if info.get("metrics"):
                m = info["metrics"]
                st.caption(f"MAE: {m.get('mae_pkr', 'n/a'):,}  |  R²: {m.get('r2', 'n/a')}")
        except requests.RequestException:
            st.error("❌ Backend unavailable\nStart FastAPI on the configured URL.")
        st.markdown("---")
        st.markdown("**Links**")
        st.markdown("[📖 API Docs](http://localhost:8000/docs)")
        st.markdown("[🌐 Website](http://localhost:3000)")

    properties = load_properties()

    # Top-level KPI bar
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📦 Listings loaded", f"{len(properties):,}")
    col2.metric("🏙️ Cities", properties["city"].nunique())
    col3.metric("📊 Dataset", "Zameen export")
    col4.metric("🔢 Rows", f"{len(properties):,}")

    st.markdown("<br>", unsafe_allow_html=True)

    lead_tab, valuation_tab, market_tab, assistant_tab = st.tabs([
        "🎯 Lead Scoring",
        "💰 Property Valuation",
        "📈 Market Insights",
        "🤖 AI Assistant",
    ])
    with lead_tab:
        render_leads(api_url)
    with valuation_tab:
        render_valuation(api_url, properties)
    with market_tab:
        render_market_insights(properties)
    with assistant_tab:
        render_assistant(api_url)


if __name__ == "__main__":
    main()