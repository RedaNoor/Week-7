"""
Generate a realistic Pakistan real-estate dataset.

Sources used as reference (informational only, no external data files copied):
- zameen.com property listings (publicly browsable)
- Knowledge of common Pakistani builders and developments

Output files written to /home/z/my-project/backend/data/:
- properties.csv        — main property catalog (P001..P040)
- developers.csv        — real Pakistani builders / developers
- locations.csv         — real sectors, phases, neighborhoods
- amenities.csv         — amenities per property
- hospitals.csv         — real hospitals near each location
- schools.csv           — real schools near each location
- payment_plans.csv     — payment plan options per property

All currency values are in Pakistani Rupees (PKR).
Land sizes are in marla (1 marla = 272.25 sqft) and kanal (1 kanal = 20 marla).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "backend" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================================
# Real Pakistani developers / builders
# =========================================================================
# Reference: publicly known developers in major Pakistani cities.
# Each tuple: (developer_id, name, city, projects, reputation)
DEVELOPERS = [
    ("D001", "Bahria Town (Pvt) Ltd", "Rawalpindi",
     "Bahria Town Phase 8; Bahria Town Phase 4; Bahria Orchard",
     "One of Pakistan's largest private developers, known for gated communities with schools, hospitals, and commercial areas"),
    ("D002", "Defence Housing Authority (DHA)", "Lahore",
     "DHA Phase 6; DHA Phase 7; DHA Phase 8; DHA Phase 9 Prism",
     "Premium defence-community developer with strong resale value and master-planned sectors"),
    ("D003", "Lahore Real Estate (Pvt) Ltd", "Lahore",
     "Lake City Lahore; Lake City Villas",
     "Lahore-based developer focused on modern gated residential communities"),
    ("D004", "Eden Housing (Pvt) Ltd", "Lahore",
     "Eden Land; Eden Cottage; Eden Avenue",
     "Established Lahore developer with mid-tier family housing"),
    ("D005", "Capital Development Authority (CDA)", "Islamabad",
     "Sector G-11; Sector F-11; Sector I-8; Sector D-12",
     "Islamabad's statutory civic authority, allocates developed residential sectors"),
    ("D006", "Capital Smart City", "Islamabad",
     "Capital Smart City Overseas Block; Capital Smart City Executive Block",
     "Joint venture with Habib Rafiq (Pvt) Ltd and Future Developments Holdings; investment-grade project on M-2 Motorway"),
    ("D007", "Bahria Town Karachi", "Karachi",
     "Bahria Town Karachi Precinct 1; Bahria Town Karachi Precinct 23; Bahria Greens",
     "Large-scale master-planned community on Karachi's M-9 Motorway"),
    ("D008", "DHA City Karachi (DCK)", "Karachi",
     "DHA City Sector 3; DHA City Sector 14",
     "Defence Housing Authority's Karachi super-development on M-9 Motorway"),
    ("D009", "Emaar Pakistan (Pvt) Ltd", "Karachi",
     "Crescent Bay; Emaar Pak Gulf",
     "Subsidiary of Emaar Properties (Dubai); premium seafront high-rises on Clifton beach"),
    ("D010", "Faisal Hills (Zem Builders)", "Islamabad",
     "Faisal Hills Block A; Faisal Hills Block B; Faisal Hills Commercial",
     "Modern gated community adjacent to Faisal Mosque and Margalla Hills"),
    ("D011", "Park View City (Urban City)", "Islamabad",
     "Park View City Block A; Park View City Block B; Park View Villas",
     "Master-planned community on Park Road, near Bahria Enclave and Chak Shahzad"),
    ("D012", "Sahasra Builders", "Faisalabad",
     "Sahasra Town; Eden Garden Faisalabad; Wapda City Faisalabad",
     "Established Faisalabad developer; mid-rise apartment and housing projects"),
    ("D013", "Sitara Hi-Tech City (Pvt) Ltd", "Faisalabad",
     "Sitara Valley; Sitara Heights",
     "Faisalabad-based developer; mid-budget residential and commercial"),
    ("D014", "Capital Smart City (Habib Rafiq)", "Rawalpindi",
     "Capital Smart City Rawalpindi; B-17 Multi Gardens",
     "Twin-city developer focusing on motorway-adjacent master-planned communities"),
    ("D015", "Gulberg Greens (MR Properties)", "Islamabad",
     "Gulberg Greens Farmhouses; Gulberg Residencia",
     "Premium Islamabad farmhouse and residential development on Islamabad Expressway"),
]

# =========================================================================
# Real locations (sector / phase / precinct / precinct)
# =========================================================================
# tuple: (location_id, name, city, area, area_type)
LOCATIONS = [
    # Lahore
    ("L001", "DHA Phase 6", "Lahore", "Lahore Cantonment", "Sector"),
    ("L002", "DHA Phase 7", "Lahore", "Lahore Cantonment", "Sector"),
    ("L003", "DHA Phase 9 Prism", "Lahore", "Lahore Cantonment", "Sector"),
    ("L004", "Bahria Town Lahore", "Lahore", "Lahore Ring Road", "Sector"),
    ("L005", "Lake City Lahore", "Lahore", "Raiwind Road", "Sector"),
    ("L006", "Eden Housing", "Lahore", "Ferozepur Road", "Sector"),
    ("L007", "Gulberg", "Lahore", "Central Lahore", "Sector"),
    ("L008", "Johar Town", "Lahore", "Lahore", "Sector"),
    ("L009", "Model Town", "Lahore", "Lahore", "Sector"),
    ("L010", "Wapda Town", "Lahore", "Lahore", "Sector"),
    # Islamabad
    ("L011", "Sector G-11", "Islamabad", "Islamabad", "Sector"),
    ("L012", "Sector F-11", "Islamabad", "Islamabad", "Sector"),
    ("L013", "Sector I-8", "Islamabad", "Islamabad", "Sector"),
    ("L014", "Sector D-12", "Islamabad", "Islamabad", "Sector"),
    ("L015", "Capital Smart City", "Islamabad", "M-2 Motorway", "Project"),
    ("L016", "Bahria Town Islamabad Phase 7", "Islamabad", "Islamabad Highway", "Sector"),
    ("L017", "Bahria Enclave", "Islamabad", "Kuri Road", "Sector"),
    ("L018", "Faisal Hills", "Islamabad", "Margalla Hills", "Sector"),
    ("L019", "Gulberg Greens", "Islamabad", "Islamabad Expressway", "Sector"),
    ("L020", "Park View City", "Islamabad", "Park Road", "Sector"),
    ("L021", "B-17 Multi Gardens", "Islamabad", "Margalla Avenue", "Sector"),
    # Karachi
    ("L022", "Bahria Town Karachi Precinct 23", "Karachi", "M-9 Motorway", "Precinct"),
    ("L023", "DHA City Karachi Sector 3", "Karachi", "M-9 Motorway", "Sector"),
    ("L024", "DHA Karachi Phase 6", "Karachi", "DHA Karachi", "Phase"),
    ("L025", "Crescent Bay", "Karachi", "Clifton", "Project"),
    ("L026", "Clifton", "Karachi", "Clifton Cantonment", "Sector"),
    ("L027", "Gulistan-e-Johar", "Karachi", "Karachi", "Sector"),
    ("L028", "Bahadurabad", "Karachi", "Karachi", "Sector"),
    # Faisalabad
    ("L029", "Wapda City Faisalabad", "Faisalabad", "Faisalabad", "Sector"),
    ("L030", "Sahasra Town", "Faisalabad", "Jhang Road", "Sector"),
    ("L031", "Sitara Valley", "Faisalabad", "Faisalabad", "Sector"),
    ("L032", "Eden Garden Faisalabad", "Faisalabad", "Faisalabad", "Sector"),
    # Rawalpindi
    ("L033", "Bahria Town Phase 8", "Rawalpindi", "Rawalpindi", "Phase"),
    ("L034", "Bahria Town Phase 4", "Rawalpindi", "Rawalpindi", "Phase"),
    ("L035", "DHA Rawalpindi Phase 2", "Rawalpindi", "Rawalpindi", "Phase"),
    ("L036", "PWD Housing Society", "Rawalpindi", "Rawalpindi", "Sector"),
    ("L037", "Capital Smart City Rawalpindi", "Rawalpindi", "M-2 Motorway", "Project"),
]

# =========================================================================
# Real hospitals near each location (for hospital.csv)
# =========================================================================
HOSPITALS = [
    # Lahore
    ("H001", "National Hospital & Medical Centre", "DHA Phase 6", "Lahore"),
    ("H002", "Doctors Hospital", "Johar Town", "Lahore"),
    ("H003", "Shaukat Khanum Memorial Cancer Hospital", "Johar Town", "Lahore"),
    ("H004", "Fatima Memorial Hospital", "Shadman", "Lahore"),
    ("H005", "Lahore General Hospital", "Township", "Lahore"),
    ("H006", "Ittefaq Hospital", "Model Town", "Lahore"),
    ("H007", "Hameed Latif Hospital", "Gulberg", "Lahore"),
    # Islamabad
    ("H008", "Shifa International Hospital", "Sector H-8/4", "Islamabad"),
    ("H009", "Pakistan Institute of Medical Sciences (PIMS)", "Sector G-8/3", "Islamabad"),
    ("H010", "Quaid-e-Azam International Hospital", "Bahria Town Phase 7", "Islamabad"),
    ("H011", "Ali Medical Centre", "F-8 Markaz", "Islamabad"),
    ("H012", "Maroof International Hospital", "F-11 Markaz", "Islamabad"),
    ("H013", "Nova Hospital", "G-10", "Islamabad"),
    # Karachi
    ("H014", "Aga Khan University Hospital", "Stadium Road", "Karachi"),
    ("H015", "Liaquat National Hospital", "National Stadium Road", "Karachi"),
    ("H016", "South City Hospital", "Shahrah-e-Faisal", "Karachi"),
    ("H017", "Patel Hospital", "Gulistan-e-Johar", "Karachi"),
    ("H018", "Dow University of Health Sciences", "Ojha Campus", "Karachi"),
    # Faisalabad
    ("H019", "Faisalabad Institute of Cardiology", "Susan Road", "Faisalabad"),
    ("H020", "Allied Hospital", "Airport Road", "Faisalabad"),
    ("H021", "National Hospital Faisalabad", "Jhang Road", "Faisalabad"),
    # Rawalpindi
    ("H022", "Holy Family Hospital", "Saidpur Road", "Rawalpindi"),
    ("H023", "Benazir Bhutto Hospital", "Murree Road", "Rawalpindi"),
    ("H024", "Heart International Hospital", "Bahria Town Phase 7", "Rawalpindi"),
    ("H025", "Militay Hospital (MH) Rawalpindi", "Garh Road", "Rawalpindi"),
]

# =========================================================================
# Real schools near each location (for schools.csv)
# =========================================================================
SCHOOLS = [
    # Lahore
    ("S001", "Lahore Grammar School (LGS)", "DHA Phase 6", "Lahore", "Private"),
    ("S002", "Beaconhouse School System", "Gulberg", "Lahore", "Private"),
    ("S003", "Aitchison College", "Lahore Cantonment", "Lahore", "Private Boarding"),
    ("S004", "Lahore American School", "Raiwind Road", "Lahore", "International"),
    ("S005", "LACAS", "Johar Town", "Lahore", "Private"),
    ("S006", "The City School", "Model Town", "Lahore", "Private"),
    ("S007", "Convent of Jesus and Mary", "Lahore Cantonment", "Lahore", "Private"),
    # Islamabad
    ("S008", "Roots Millennium Schools", "F-11 Markaz", "Islamabad", "Private"),
    ("S009", "Headstart School", "F-8 Markaz", "Islamabad", "Private"),
    ("S010", "International School of Islamabad (ISOI)", "Diplomatic Enclave", "Islamabad", "International"),
    ("S011", "Beaconhouse F-7/3", "F-7 Markaz", "Islamabad", "Private"),
    ("S012", "Schola Nova", "H-8", "Islamabad", "Private"),
    ("S013", "Froebel's International School", "F-11", "Islamabad", "Private"),
    # Karachi
    ("S014", "Karachi Grammar School", "Clifton", "Karachi", "Private"),
    ("S015", "Bay View Academy", "DHA Phase 6", "Karachi", "Private"),
    ("S016", "The Lyceum", "Clifton", "Karachi", "Private"),
    ("S017", "St. Patrick's High School", "Saddar", "Karachi", "Missionary"),
    ("S018", "Foundation Public School", "Clifton", "Karachi", "Private"),
    # Faisalabad
    ("S019", "Beaconhouse Faisalabad", "People's Colony", "Faisalabad", "Private"),
    ("S020", "LGS Faisalabad", "Wapda City", "Faisalabad", "Private"),
    ("S021", "The City School Faisalabad", "Sahiwal Road", "Faisalabad", "Private"),
    # Rawalpindi
    ("S022", "Bahria Foundation School", "Bahria Town Phase 8", "Rawalpindi", "Private"),
    ("S023", "Roots School International", "Bahria Town Phase 4", "Rawalpindi", "Private"),
    ("S024", "St. Mary's Cambridge School", "Murree Road", "Rawalpindi", "Missionary"),
    ("S025", "Anglican Cathedral School", "Liaquat Road", "Rawalpindi", "Private"),
]

# =========================================================================
# Amenities per property (will be assigned by property_id below)
# =========================================================================
# Tuple: (property_id, amenity)
AMENITIES_POOL = [
    "24/7 Security", "Backup Generator", "Underground Electricity",
    "Swimming Pool", "Gymnasium", "Tennis Court",
    "Mosque on Premises", "Community Centre", "Children's Playground",
    "Underground Parking", "Elevator", "CCTV Surveillance",
    "Gas Pipeline", "Water Filtration Plant", "Sewage Treatment Plant",
    "Underground Wiring", "Landscaped Gardens", "Jogging Track",
    "School Within Community", "Hospital Within Community",
    "Shopping Mall On-Site", "Cinema", "Restaurant Strip",
    "Gated Entrance", "Wide Roads (40ft+)", "Street Lights",
    "Fire Safety System", "Earthquake-Resistant Construction",
]


# =========================================================================
# Property catalog — 40 realistic listings
# =========================================================================
# Conversion: 1 marla = 272.25 sqft, 1 kanal = 20 marla = 5445 sqft
# Pricing trends (late-2024 / 2025 approximate) per marla:
#   DHA Lahore Phase 6:        PKR 8-12 lakh / marla
#   DHA Lahore Phase 9 Prism:  PKR 22-30 lakh / marla
#   Bahria Town Lahore:        PKR 5-9 lakh / marla
#   DHA Karachi Phase 6:       PKR 8-15 lakh / marla
#   Bahria Town Karachi:       PKR 3-6 lakh / marla
#   Sector G-11 Islamabad:     PKR 6-9 lakh / marla
#   Sector F-11 Islamabad:      PKR 9-14 lakh / marla
#   Capital Smart City:        PKR 3-7 lakh / marla
#   Wapda City Faisalabad:     PKR 1.5-3 lakh / marla
#   Bahria Town Rawalpindi:    PKR 4-8 lakh / marla

def marla_to_sqft(marla: float) -> int:
    return int(marla * 272.25)


# (property_id, name, developer_id, location_id, city, area, type,
#  bedrooms, size_marla, size_sqft, price, status, purpose)
PROPERTIES_TEMPLATE = [
    # ===== LAHORE — DHA =====
    ("P001", "5 Marla House in DHA Phase 6", "D002", "L001", "Lahore", "DHA Phase 6", "House", 3, 5.0, 0, 45000000, "Available", "Family"),
    ("P002", "10 Marla House in DHA Phase 6", "D002", "L001", "Lahore", "DHA Phase 6", "House", 4, 10.0, 0, 90000000, "Available", "Family"),
    ("P003", "1 Kanal House in DHA Phase 6", "D002", "L001", "Lahore", "DHA Phase 6", "House", 5, 20.0, 0, 175000000, "Available", "Family"),
    ("P004", "10 Marla House in DHA Phase 7", "D002", "L002", "Lahore", "DHA Phase 7", "House", 4, 10.0, 0, 75000000, "Reserved", "Family"),
    ("P005", "5 Marla Plot in DHA Phase 9 Prism", "D002", "L003", "Lahore", "DHA Phase 9 Prism", "Plot", 0, 5.0, 0, 14500000, "Available", "Investment"),
    ("P006", "1 Kanal House in DHA Phase 9 Prism", "D002", "L003", "Lahore", "DHA Phase 9 Prism", "House", 6, 20.0, 0, 220000000, "Available", "Family"),
    # ===== LAHORE — Bahria Town / Lake City / Eden =====
    ("P007", "5 Marla House in Bahria Town Lahore", "D001", "L004", "Lahore", "Bahria Town Lahore", "House", 3, 5.0, 0, 28000000, "Available", "Family"),
    ("P008", "8 Marla House in Bahria Town Lahore", "D001", "L004", "Lahore", "Bahria Town Lahore", "House", 4, 8.0, 0, 48000000, "Available", "Family"),
    ("P009", "3 Bed Apartment in Bahria Town Lahore", "D001", "L004", "Lahore", "Bahria Town Lahore", "Apartment", 3, 4.0, 0, 14500000, "Available", "Investment"),
    ("P010", "10 Marla Villa in Lake City Lahore", "D003", "L005", "Lahore", "Lake City Lahore", "House", 4, 10.0, 0, 65000000, "Available", "Family"),
    ("P011", "1 Kanal Farmhouse in Lake City Lahore", "D003", "L005", "Lahore", "Lake City Lahore", "Farmhouse", 6, 20.0, 0, 180000000, "Available", "Family"),
    ("P012", "5 Marla House in Eden Housing", "D004", "L006", "Lahore", "Eden Housing", "House", 3, 5.0, 0, 18500000, "Available", "Family"),
    # ===== LAHORE — Mid-tier / Central =====
    ("P013", "2 Bed Apartment in Gulberg", "D003", "L007", "Lahore", "Gulberg", "Apartment", 2, 3.0, 0, 12500000, "Available", "Investment"),
    ("P014", "10 Marla House in Johar Town", "D004", "L008", "Lahore", "Johar Town", "House", 4, 10.0, 0, 55000000, "Available", "Family"),
    ("P015", "1 Kanal House in Model Town", "D004", "L009", "Lahore", "Model Town", "House", 6, 20.0, 0, 240000000, "Available", "Family"),
    # ===== ISLAMABAD — Sectors =====
    ("P016", "5 Marla House in Sector G-11", "D005", "L011", "Islamabad", "Sector G-11", "House", 3, 5.0, 0, 35000000, "Available", "Family"),
    ("P017", "10 Marla House in Sector G-11", "D005", "L011", "Islamabad", "Sector G-11", "House", 4, 10.0, 0, 75000000, "Available", "Family"),
    ("P018", "1 Kanal House in Sector F-11", "D005", "L012", "Islamabad", "Sector F-11", "House", 6, 20.0, 0, 220000000, "Available", "Family"),
    ("P019", "2 Bed Apartment in Sector I-8", "D005", "L013", "Islamabad", "Sector I-8", "Apartment", 2, 3.0, 0, 16500000, "Available", "Investment"),
    ("P020", "10 Marla House in Sector D-12", "D005", "L014", "Islamabad", "Sector D-12", "House", 5, 10.0, 0, 95000000, "Available", "Family"),
    # ===== ISLAMABAD — Master-planned communities =====
    ("P021", "5 Marla Apartment in Capital Smart City", "D006", "L015", "Islamabad", "Capital Smart City", "Apartment", 3, 4.0, 0, 18500000, "Available", "Investment"),
    ("P022", "1 Kanal Villa in Capital Smart City", "D006", "L015", "Islamabad", "Capital Smart City", "House", 5, 20.0, 0, 120000000, "Available", "Family"),
    ("P023", "10 Marla House in Bahria Town Phase 7 Islamabad", "D005", "L016", "Islamabad", "Bahria Town Islamabad Phase 7", "House", 4, 10.0, 0, 85000000, "Available", "Family"),
    ("P024", "5 Marla House in Bahria Enclave", "D005", "L017", "Islamabad", "Bahria Enclave", "House", 3, 5.0, 0, 42500000, "Available", "Family"),
    ("P025", "1 Kanal Villa in Faisal Hills", "D010", "L018", "Islamabad", "Faisal Hills", "House", 5, 20.0, 0, 145000000, "Available", "Family"),
    ("P026", "2 Kanal Farmhouse in Gulberg Greens", "D015", "L019", "Islamabad", "Gulberg Greens", "Farmhouse", 7, 40.0, 0, 320000000, "Available", "Family"),
    ("P027", "10 Marla House in Park View City Islamabad", "D011", "L020", "Islamabad", "Park View City", "House", 4, 10.0, 0, 78000000, "Available", "Family"),
    ("P028", "5 Marla House in B-17 Multi Gardens", "D014", "L021", "Islamabad", "B-17 Multi Gardens", "House", 3, 5.0, 0, 28500000, "Available", "Family"),
    # ===== KARACHI =====
    ("P029", "120 sqyd Apartment in Bahria Town Karachi", "D007", "L022", "Karachi", "Bahria Town Karachi Precinct 23", "Apartment", 2, 4.0, 0, 9500000, "Available", "Family"),
    ("P030", "240 sqyd House in Bahria Town Karachi", "D007", "L022", "Karachi", "Bahria Town Karachi Precinct 23", "House", 4, 8.0, 0, 38000000, "Available", "Family"),
    ("P031", "5 Marla House in DHA City Karachi", "D008", "L023", "Karachi", "DHA City Karachi Sector 3", "House", 3, 5.0, 0, 18500000, "Available", "Investment"),
    ("P032", "1 Kanal House in DHA Karachi Phase 6", "D008", "L024", "Karachi", "DHA Karachi Phase 6", "House", 6, 20.0, 0, 195000000, "Available", "Family"),
    ("P033", "2 Bed Apartment in Crescent Bay", "D009", "L025", "Karachi", "Crescent Bay", "Apartment", 2, 3.0, 0, 28500000, "Available", "Investment"),
    ("P034", "3 Bed Apartment in Clifton Tower", "D009", "L026", "Karachi", "Clifton", "Apartment", 3, 5.0, 0, 42000000, "Available", "Family"),
    ("P035", "10 Marla House in Gulistan-e-Johar", "D007", "L027", "Karachi", "Gulistan-e-Johar", "House", 4, 10.0, 0, 35000000, "Available", "Family"),
    # ===== FAISALABAD =====
    ("P036", "5 Marla House in Wapda City Faisalabad", "D012", "L029", "Faisalabad", "Wapda City Faisalabad", "House", 3, 5.0, 0, 12500000, "Available", "Family"),
    ("P037", "10 Marla House in Sahasra Town", "D012", "L030", "Faisalabad", "Sahasra Town", "House", 4, 10.0, 0, 22500000, "Available", "Family"),
    ("P038", "3 Bed Apartment in Sitara Valley", "D013", "L031", "Faisalabad", "Sitara Valley", "Apartment", 3, 4.0, 0, 11500000, "Available", "Investment"),
    # ===== RAWALPINDI =====
    ("P039", "5 Marla House in Bahria Town Phase 8 Rawalpindi", "D001", "L033", "Rawalpindi", "Bahria Town Phase 8", "House", 3, 5.0, 0, 22500000, "Available", "Family"),
    ("P040", "10 Marla House in Bahria Town Phase 4 Rawalpindi", "D001", "L034", "Rawalpindi", "Bahria Town Phase 4", "House", 4, 10.0, 0, 38500000, "Available", "Family"),
    ("P041", "1 Kanal House in DHA Rawalpindi Phase 2", "D002", "L035", "Rawalpindi", "DHA Rawalpindi Phase 2", "House", 6, 20.0, 0, 165000000, "Available", "Family"),
    ("P042", "5 Marla House in PWD Housing Society", "D014", "L036", "Rawalpindi", "PWD Housing Society", "House", 3, 5.0, 0, 14500000, "Available", "Family"),
]


def write_csv(path: Path, headers: list[str], rows: list[tuple]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print(f"  wrote {path.name}: {len(rows)} rows")


def main() -> None:
    print(f"Writing dataset to {DATA_DIR}")

    # ------------------------------------------------------------------
    # developers.csv
    # ------------------------------------------------------------------
    write_csv(
        DATA_DIR / "developers.csv",
        ["developer_id", "name", "city", "projects", "reputation"],
        DEVELOPERS,
    )

    # ------------------------------------------------------------------
    # locations.csv
    # ------------------------------------------------------------------
    write_csv(
        DATA_DIR / "locations.csv",
        ["location_id", "name", "city", "area", "area_type"],
        LOCATIONS,
    )

    # ------------------------------------------------------------------
    # properties.csv
    # ------------------------------------------------------------------
    property_rows = []
    dev_lookup = {d[0]: d[1] for d in DEVELOPERS}
    for p in PROPERTIES_TEMPLATE:
        (pid, name, dev_id, loc_id, city, area, ptype,
         beds, marla, _sqft, price, status, purpose) = p
        sqft = marla_to_sqft(marla)
        property_rows.append((
            pid, name, dev_lookup[dev_id], city, area, ptype,
            beds, sqft, marla, price, status, purpose,
        ))
    write_csv(
        DATA_DIR / "properties.csv",
        ["property_id", "name", "developer", "city", "area", "type",
         "bedrooms", "size_sqft", "size_marla", "price", "status", "purpose"],
        property_rows,
    )

    # ------------------------------------------------------------------
    # amenities.csv (3-6 amenities per property, deterministic by property_id)
    # ------------------------------------------------------------------
    import hashlib
    amenity_rows = []
    for p in PROPERTIES_TEMPLATE:
        pid = p[0]
        # Hash property_id to deterministically pick amenities
        h = int(hashlib.md5(pid.encode()).hexdigest(), 16)
        count = 3 + (h % 4)  # 3 to 6 amenities
        picks = []
        for i in range(count):
            idx = (h >> (i * 5)) % len(AMENITIES_POOL)
            amenity = AMENITIES_POOL[idx]
            if amenity not in picks:
                picks.append(amenity)
        for amenity in picks:
            amenity_rows.append((pid, amenity))
    write_csv(
        DATA_DIR / "amenities.csv",
        ["property_id", "amenity"],
        amenity_rows,
    )

    # ------------------------------------------------------------------
    # hospitals.csv
    # ------------------------------------------------------------------
    write_csv(
        DATA_DIR / "hospitals.csv",
        ["hospital_id", "name", "near_location", "city"],
        HOSPITALS,
    )

    # ------------------------------------------------------------------
    # schools.csv
    # ------------------------------------------------------------------
    write_csv(
        DATA_DIR / "schools.csv",
        ["school_id", "name", "near_location", "city", "type"],
        SCHOOLS,
    )

    # ------------------------------------------------------------------
    # payment_plans.csv (one or more plan options per property)
    # ------------------------------------------------------------------
    payment_rows = []
    for p in PROPERTIES_TEMPLATE:
        pid = p[0]
        price = p[10]
        if p[6] == "Plot":
            # Plots typically have shorter payment plans
            plans = [
                (f"{pid}-PP-01", pid, "100% Lump Sum", "100", "0", int(price * 0.95), "5% discount on lump sum"),
                (f"{pid}-PP-02", pid, "12-Month Installment Plan", "25", "12", price, "25% down payment, balance over 12 months"),
            ]
        elif p[6] == "Apartment":
            plans = [
                (f"{pid}-PP-01", pid, "Spot Cash", "100", "0", int(price * 0.92), "8% discount on spot cash"),
                (f"{pid}-PP-02", pid, "24-Month Plan", "30", "24", price, "30% down payment, 24 monthly installments"),
                (f"{pid}-PP-03", pid, "36-Month Plan", "20", "36", int(price * 1.05), "5% premium, lower down payment"),
            ]
        else:  # House / Farmhouse
            plans = [
                (f"{pid}-PP-01", pid, "Spot Cash", "100", "0", int(price * 0.95), "5% discount on spot cash"),
                (f"{pid}-PP-02", pid, "24-Month Plan", "25", "24", price, "25% down payment, 24 monthly installments"),
                (f"{pid}-PP-03", pid, "60-Month Plan", "15", "60", int(price * 1.08), "8% premium, 5-year plan for family buyers"),
            ]
        payment_rows.extend(plans)
    write_csv(
        DATA_DIR / "payment_plans.csv",
        ["plan_id", "property_id", "plan_name", "down_payment_percent",
         "installment_months", "total_payable", "description"],
        payment_rows,
    )

    print("\nDataset generation complete.")
    print(f"  properties: {len(property_rows)}")
    print(f"  developers: {len(DEVELOPERS)}")
    print(f"  locations:  {len(LOCATIONS)}")
    print(f"  amenities:  {len(amenity_rows)}")
    print(f"  hospitals:  {len(HOSPITALS)}")
    print(f"  schools:    {len(SCHOOLS)}")
    print(f"  payment_plans: {len(payment_rows)}")


if __name__ == "__main__":
    main()
