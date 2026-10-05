# Week 8 Data Dictionary

Run `python scripts/prepare_week8_data.py` to create the derived CSVs in this
folder. The downloaded `dataset_properties.csv` remains unchanged.

## Property listings

| Field | Type / unit | Meaning | Source and known issue |
|---|---|---|---|
| `property_id` | integer | Listing identifier | Source CSV; may not be globally unique across exports |
| `city`, `location`, `province_name` | category | Market and neighborhood | Source CSV; names are retained for traceability |
| `property_type` | category | Flat, House, Plot, etc. | Source CSV |
| `price` | PKR | Listed price and regression target | Source CSV; not an official valuation |
| `area_marla` | marla | Normalized area; 1 kanal = 20 marla and 1 marla = 272.25 sq ft | Derived from `Area Type` and `Area Size` |
| `bedrooms`, `baths` | count | Room and bathroom counts | Source CSV |
| `amenities` | pipe-separated text | Assumed nearby facilities | Deterministic area profile; verify before production |
| `amenity_score` | 1-5 | Count-based proxy for amenity access | Derived assumption, not a measured rating |
| `distance_main_road_km`, `distance_school_km`, `distance_hospital_km` | km | Approximate accessibility features | Area-profile assumptions; replace with GIS distances |
| `property_age_years`, `floors`, `corner`, `park_facing` | mixed | Additional valuation features | Age/floors are conservative proxies; corner/facing inferred from listing URL |

## Leads

`leads.csv` contains 3,000 deterministic, synthetic records based on the Week
7 CRM scenario. `converted` is the classification target. It is suitable for
pipeline demonstration and testing, not for estimating real conversion rates.

## Cleaning and leakage policy

Prices must be positive, area must be normalized before modeling, and duplicate
rows should be removed using `property_id` plus listing URL. The URL, agency,
agent, and `date_added` are excluded from the model when they identify the
listing or expose collection-time information. Numeric features use training
statistics only; categorical values use one-hot encoding with unknown values
ignored.