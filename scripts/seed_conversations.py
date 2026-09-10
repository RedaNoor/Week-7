"""
Seed the conversation learner with realistic past real-estate chats.

Each tuple is (user_query, assistant_response, intent, outcome).

All references match the updated Pakistani property catalog in
/home/z/my-project/backend/data/properties.csv — real developers
(DHA, Bahria Town, Capital Smart City, Emaar, etc.) and real cities
(Lahore, Islamabad, Karachi, Faisalabad, Rawalpindi).
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.services.conversation_learning import learner


SEED_CONVERSATIONS = [
    # --- Booking / appointment ---
    (
        "Hi, I want to book a visit to the 5 Marla House in DHA Phase 6 Lahore this weekend.",
        "Sure! Your visit to the 5 Marla House (P001) in DHA Phase 6, Lahore is confirmed for "
        "Saturday at 3 PM. You'll receive a confirmation email with the location pin and the "
        "agent's contact details shortly. Please bring your CNIC. Is there anything else I can "
        "help you with?",
        "book_visit", "booked",
    ),
    (
        "Can I schedule a tour of the 3 Bed Apartment in Bahria Town Lahore next Tuesday?",
        "Absolutely! Your tour of the 3 Bed Apartment (P009) in Bahria Town Lahore is confirmed "
        "for Tuesday at 11 AM. Our agent will meet you at the Bahria Town sales office. "
        "Please bring a copy of your CNIC. See you there!",
        "book_visit", "booked",
    ),
    (
        "I'd like to visit the 1 Kanal House in DHA Phase 9 Prism. What times are available?",
        "We have openings for the 1 Kanal House (P006) in DHA Phase 9 Prism on Friday at 4 PM "
        "or Saturday at 11 AM. Which slot works better for you? Also, would you like me to "
        "send the location pin to your phone?",
        "book_visit", "engaged",
    ),
    (
        "Book a visit for the 10 Marla House in Bahria Town Phase 4 Rawalpindi for tomorrow morning.",
        "Perfect! Your visit to the 10 Marla House (P040) in Bahria Town Phase 4 Rawalpindi is "
        "confirmed for tomorrow at 10:30 AM. Our agent Mr. Ahmed will meet you at the site office. "
        "You'll receive a calendar invite and confirmation email shortly. Safe travels!",
        "book_visit", "booked",
    ),
    (
        "Schedule tour for the 1 Kanal Villa in Capital Smart City this Saturday.",
        "Excellent choice! The 1 Kanal Villa (P022) visit in Capital Smart City is confirmed for "
        "Saturday at 2 PM. The sales team will have the model villa ready for viewing. Allow "
        "about 90 minutes for the full tour including amenities. Confirmation email sent.",
        "book_visit", "booked",
    ),
    (
        "Book appointment for the 1 Kanal House in Sector F-11 Islamabad.",
        "Your appointment for the 1 Kanal House (P018) in Sector F-11 Islamabad is confirmed. "
        "Our senior agent Ms. Sana will contact you to confirm the exact time. Please note this "
        "is a high-demand property. Email confirmation has been sent to your inbox.",
        "book_visit", "booked",
    ),
    (
        "I want to see the 5 Marla House in Bahria Enclave Islamabad. Can you arrange a visit?",
        "Absolutely! The 5 Marla House (P024) in Bahria Enclave Islamabad — your visit is being "
        "scheduled. Available slots: Friday 4 PM, Saturday 11 AM, or Saturday 4 PM. Which works "
        "best for you? Also, would you like a virtual tour link in the meantime?",
        "book_visit", "engaged",
    ),

    # --- Pricing inquiries ---
    (
        "What is the price of a 5 marla house in DHA Lahore?",
        "In DHA Lahore, a 5-marla house typically ranges from PKR 4 crore to 5 crore depending "
        "on the phase and finish. For example, the 5 Marla House (P001) in DHA Phase 6 is listed "
        "at PKR 4.50 crore for a 3-bed finished house. Would you like to schedule a visit?",
        "price_inquiry", "recommendation_made",
    ),
    (
        "How much does a 10 marla house cost in Bahria Town Lahore?",
        "A 10-marla house in Bahria Town Lahore starts around PKR 4.8 crore. The 8 Marla House "
        "(P008) is currently available at PKR 4.8 crore. Are you looking for investment or for "
        "your own family?",
        "price_inquiry", "engaged",
    ),
    (
        "What's the price range for properties in Islamabad Sector G-11?",
        "In Sector G-11 Islamabad, 5-marla houses start from PKR 3.5 crore and 10-marla from "
        "PKR 7.5 crore. The 5 Marla House (P016) is listed at PKR 3.5 crore and the 10 Marla "
        "House (P017) at PKR 7.5 crore. Would you like a detailed brochure?",
        "price_inquiry", "info_given",
    ),
    (
        "How much does an apartment in Crescent Bay Karachi cost?",
        "Crescent Bay is a premium Emaar development on Clifton beach. The 2 Bed Apartment "
        "(P033) is listed at PKR 2.85 crore. Sea-view units typically carry a 15-20% premium. "
        "Would you like me to share photos and a floor plan?",
        "price_inquiry", "engaged",
    ),

    # --- Location inquiries ---
    (
        "Which areas in Lahore have good family homes under 5 crore?",
        "For family homes under PKR 5 crore in Lahore, I'd recommend Bahria Town Lahore "
        "(P007 5 Marla at PKR 2.8 crore, P008 8 Marla at PKR 4.8 crore), Eden Housing "
        "(P012 5 Marla at PKR 1.85 crore), and Johar Town (P014 10 Marla at PKR 5.5 crore). "
        "All have schools, parks, and 24/7 security. Want me to send brochures?",
        "location_inquiry", "recommendation_made",
    ),
    (
        "Tell me about properties near DHA Phase 6 Lahore.",
        "DHA Phase 6 Lahore is a premium location with excellent amenities. We have the "
        "5 Marla House (P001) at PKR 4.5 crore, 10 Marla House (P002) at PKR 9 crore, and "
        "1 Kanal House (P003) at PKR 17.5 crore. The area has top schools (LGS, Beaconhouse), "
        "hospitals (National Hospital), and easy access to Allama Iqbal Airport.",
        "location_inquiry", "info_given",
    ),
    (
        "Are there properties available in Sector F-11 Islamabad?",
        "Yes! In F-11 Islamabad we have the 1 Kanal House (P018) at PKR 22 crore. F-11 is "
        "one of Islamabad's most sought-after sectors with Centaurus Mall, the F-11 Markaz, "
        "and top schools (Roots Millennium, Froebel's) nearby. Shall I schedule a visit?",
        "location_inquiry", "engaged",
    ),
    (
        "What are the best areas for families in Islamabad?",
        "For families in Islamabad, top areas are: (1) Sector F-11 — premium and central, "
        "(2) Bahria Town Phase 7 — gated with hospitals and schools on site, (3) Sector D-12 — "
        "near Margalla Hills, (4) Park View City — newer development with great amenities. "
        "Which fits your budget best?",
        "location_inquiry", "recommendation_made",
    ),
    (
        "I'm looking for a property in Karachi near the sea. What do you suggest?",
        "For sea-view properties in Karachi, the best options are Crescent Bay (P033, "
        "2 Bed Apartment at PKR 2.85 crore) on Clifton beach, and Clifton Tower (P034, "
        "3 Bed Apartment at PKR 4.2 crore). Both are Emaar-developed with sea-facing views. "
        "Want me to schedule a tour?",
        "location_inquiry", "engaged",
    ),

    # --- Investment inquiries ---
    (
        "I want to invest around 2 crore in Lahore for high ROI. What do you suggest?",
        "For PKR 2 crore investment in Lahore with high ROI, I'd suggest Bahria Town Lahore "
        "apartments (rental yield ~6-7%) or plots in DHA Phase 9 Prism. The 3 Bed Apartment "
        "(P009) at PKR 1.45 crore in Bahria Town has shown 12% appreciation YoY. "
        "Want me to send an investment analysis report?",
        "investment_inquiry", "recommendation_made",
    ),
    (
        "Is buying property in Capital Smart City Islamabad a good investment?",
        "Capital Smart City is among the fastest-appreciating projects in Islamabad. The "
        "5 Marla Apartment (P021) at PKR 1.85 crore has shown 18% YoY appreciation. With "
        "the M-2 Motorway access and the new Islamabad Airport nearby, ROI is projected "
        "at 25%+ over 3 years. I'd strongly recommend booking a visit this week.",
        "investment_inquiry", "engaged",
    ),
    (
        "Tell me about investment opportunities in DHA City Karachi.",
        "DHA City Karachi (DCK) on the M-9 Motorway is a solid long-term investment. The "
        "5 Marla House (P031) at PKR 1.85 crore is suitable for investors seeking 5-7% "
        "annual appreciation. The project has full DHA backing and is scheduled for "
        "handover in phases through 2026. Want me to share the master plan?",
        "investment_inquiry", "info_given",
    ),
    (
        "What's the best investment property under 3 crore in Islamabad?",
        "For under PKR 3 crore in Islamabad, Capital Smart City (P021 at PKR 1.85 crore) "
        "is the best investment — 18% YoY appreciation, projected 25% over 3 years, strong "
        "rental demand. Alternatively, Sector I-8 (P019 at PKR 1.65 crore) offers stable "
        "rental income. Want me to email a comparison sheet?",
        "investment_inquiry", "recommendation_made",
    ),

    # --- Property search (family homes) ---
    (
        "We are a family of 5 looking for a 4-bed house in Lahore with good schools nearby.",
        "For a family of 5 needing a 4-bed house in Lahore with good schools, I'd recommend: "
        "(1) 10 Marla House (P002) in DHA Phase 6 at PKR 9 crore (near LGS & Beaconhouse), "
        "(2) 10 Marla House (P014) in Johar Town at PKR 5.5 crore (near LACAS), "
        "(3) 8 Marla House (P008) in Bahria Town Lahore at PKR 4.8 crore (near Bloomfield Hall). "
        "Would you like to schedule visits to all three?",
        "property_search", "recommendation_made",
    ),
    (
        "Looking for a family apartment in Islamabad, 3 bed, budget around 2 crore.",
        "In Islamabad with PKR 2 crore budget for a 3-bed apartment, Capital Smart City "
        "(P021) at PKR 1.85 crore is an excellent fit. It has 3 beds, with schools, parks, "
        "and mosque within walking distance. The complex has a swimming pool, gym, and "
        "24/7 security. Shall I book a visit?",
        "property_search", "engaged",
    ),
    (
        "I need a 5 marla house in Faisalabad for my parents, budget around 1.5 crore.",
        "In Faisalabad within PKR 1.5 crore, the 5 Marla House (P036) in Wapda City "
        "Faisalabad at PKR 1.25 crore is a great fit. Wapda City is a peaceful, family-"
        "oriented sector with parks, mosque, and easy access to Susan Road. Would you "
        "like to schedule a visit?",
        "property_search", "recommendation_made",
    ),

    # --- FAQ-style ---
    (
        "What documents do I need to book a property in Pakistan?",
        "To book a property in Pakistan, you'll need: (1) CNIC copy, (2) 2 passport-size photos, "
        "(3) proof of income (salary slip or bank statement), (4) booking amount (usually 25% "
        "of total) via pay order or bank draft. For overseas Pakistanis, a NICOP and power of "
        "attorney are also acceptable. I can email you a complete checklist if you'd like.",
        "lead_inquiry", "info_given",
    ),
    (
        "What are the payment plan options for the 1 Kanal House in DHA Phase 6?",
        "The 1 Kanal House (P003) in DHA Phase 6 at PKR 17.5 crore offers three plans: "
        "(1) Spot Cash — 100% with 5% discount (PKR 16.6 crore), (2) 24-Month Plan — 25% "
        "down payment, balance over 24 months, (3) 60-Month Plan — 15% down with 8% premium "
        "for family buyers. Would you like a detailed payment schedule?",
        "lead_inquiry", "info_given",
    ),
    (
        "Are your prices negotiable?",
        "Pricing depends on the developer and property status. For available properties like "
        "the 5 Marla House (P001) in DHA Phase 6, there's typically 3-5% negotiation room on "
        "the booking amount. For ready-to-move-in houses, more negotiation is possible. Want "
        "me to discuss on a call?",
        "lead_inquiry", "engaged",
    ),
    (
        "What's the cheapest property you have?",
        "Our most affordable listed property is the 3 Bed Apartment (P038) in Sitara Valley "
        "Faisalabad at PKR 1.15 crore. For investors, the 2 Bed Apartment (P013) in Gulberg "
        "Lahore at PKR 1.25 crore is also affordable. Would you like details?",
        "price_inquiry", "engaged",
    ),
    (
        "Tell me about Bahria Town Karachi.",
        "Bahria Town Karachi is a large master-planned community on the M-9 Motorway. We have "
        "the 120 sqyd Apartment (P029) at PKR 95 lakh and the 240 sqyd House (P030) at "
        "PKR 3.8 crore. Amenities include 24/7 security, hospitals, schools, and a theme park. "
        "Want to schedule a visit?",
        "location_inquiry", "engaged",
    ),

    # --- Some negative / dropped outcomes for realistic learning ---
    (
        "Are you offering any rent-to-own options?",
        "We don't currently offer rent-to-own options on any of our listed properties. All "
        "purchases are on standard payment plans (spot cash, 24-month, or 60-month). Would "
        "you like me to share details on our most flexible 60-month plans instead?",
        "lead_inquiry", "dropped",
    ),
    (
        "Do you have any commercial properties available?",
        "Our current catalog is focused on residential properties (houses, apartments, "
        "farmhouses). For commercial listings, I'd recommend contacting our commercial desk "
        "at commercial@realestatehub.pk. Would you like me to forward your details?",
        "lead_inquiry", "dropped",
    ),

    # --- More booking successes for template learning ---
    (
        "Book a visit for the 5 Marla House in Sector G-11 Islamabad for tomorrow morning.",
        "Perfect! Your visit to the 5 Marla House (P016) in Sector G-11 Islamabad is confirmed "
        "for tomorrow at 10:30 AM. Our agent Mr. Ahmed will meet you at the site office. "
        "You'll receive a calendar invite and confirmation email at your registered address. "
        "Safe travels!",
        "book_visit", "booked",
    ),
    (
        "Schedule tour for the 1 Kanal Villa in Faisal Hills Islamabad this Saturday.",
        "Excellent choice! Faisal Hills (P025) visit confirmed for Saturday at 2 PM. The sales "
        "team will have the model villa ready for viewing. Allow about 90 minutes for the full "
        "tour including amenities. Confirmation email sent.",
        "book_visit", "booked",
    ),
    (
        "I want to see the 10 Marla House in Lake City Lahore. Can you arrange a visit?",
        "Absolutely! Lake City Lahore (P010) — your visit is being scheduled. Available slots: "
        "Friday 4 PM, Saturday 11 AM, or Saturday 4 PM. Which works best for you? Also, would "
        "you like a virtual tour link in the meantime?",
        "book_visit", "engaged",
    ),
    (
        "Book the 5 Marla House in Bahria Town Phase 8 Rawalpindi.",
        "Your appointment for the 5 Marla House (P039) in Bahria Town Phase 8 Rawalpindi is "
        "confirmed. Our agent Mr. Khan will contact you to confirm the exact time. Email "
        "confirmation sent to your inbox.",
        "book_visit", "booked",
    ),
    (
        "Can I visit the 2 Kanal Farmhouse in Gulberg Greens Islamabad?",
        "Yes! The 2 Kanal Farmhouse (P026) in Gulberg Greens is available for viewing. "
        "Available slots: Thursday 11 AM, Friday 4 PM, or Saturday 11 AM. Please bring "
        "your CNIC and a recent utility bill for verification. Shall I confirm a slot?",
        "book_visit", "engaged",
    ),
]


def seed():
    """Insert seed conversations into the learner and train the model."""
    print(f"Seeding {len(SEED_CONVERSATIONS)} conversations into learner...")
    # Clear any prior seed data so we can re-run idempotently
    learner.corpus = [
        c for c in learner.corpus
        if not (c.get("metadata") or {}).get("seed")
    ]
    learner._save_memory()

    inserted = 0
    for i, (query, response, intent, outcome) in enumerate(SEED_CONVERSATIONS):
        result = learner.record_conversation(
            session_id=f"seed_session_{i+1:03d}",
            user_query=query,
            assistant_response=response,
            intent=intent,
            outcome=outcome,
            profile={"source": "seed"},
            metadata={"seed": True},
        )
        inserted += 1

    print(f"Inserted {inserted} conversations. Training model...")
    train_result = learner.train()
    print(f"Training result: {json.dumps(train_result, indent=2)}")

    print("\nStats:")
    print(json.dumps(learner.stats(), indent=2))

    print("\nTopic Summary (clusters):")
    for cluster in learner.get_topic_summary():
        print(f"  Cluster {cluster['cluster_id']} (size={cluster['size']}, "
              f"avg_success={cluster['avg_success_score']:.2f})")
        print(f"    Top terms: {', '.join(cluster['top_terms'])}")
        for s in cluster["samples"]:
            print(f"    - [{s['intent']}/{s['outcome']}] {s['user_query'][:80]}...")


if __name__ == "__main__":
    seed()
