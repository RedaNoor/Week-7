"""Simple demo script for class presentation.

Run:
    python demo_script.py

This script shows the core end-to-end flow for the simplified project:
1. lead profile extraction
2. intent detection
3. property matching
4. appointment creation
"""

from app.services.call_intent import detect_intent
from app.services.lead_memory import lead_memory
from app.services.property_matcher import match_properties

sample_transcript = (
    "Assalam-o-Alaikum. Budget 3 crore hai. DHA mein family home chahiye, "
    "buy karna hai. Agar option milta hai to visit karna chahata hoon."
)

profile = lead_memory.build_profile(sample_transcript)
intent = detect_intent(sample_transcript)
recommendations = match_properties(profile)

print("=== Lead Profile ===")
print(profile)
print("\n=== Intent ===")
print(intent)
print("\n=== Recommended Properties ===")
for item in recommendations:
    print(item)
