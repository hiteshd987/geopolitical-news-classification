import os
from dotenv import load_dotenv

# Load variables from the .env file into the system environment
load_dotenv(override=True)

# Configuration for OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Check key presence and print status
if not OPENAI_API_KEY:
    raise EnvironmentError(
        "OPENAI_API_KEY not found. Add it to your .env file."
    )
print("API Key Loaded.")

MODEL_NAME = "gpt-4o-mini"

EMBEDDING_MODEL = "text-embedding-3-small"
MAX_CONTENT_TOKENS = 700
NEGATIVE_SIM_THRESHOLD = 0.30
TRIAGE_POSITIVE_THRESHOLD = 0.25

# Stage 1 Triage keywords derived directly from SPEC.md
EVENT_TAXONOMY = {
    "Hormuz Closure": [
        "hormuz", "strait of hormuz", "mine", "naval mine", "mining", 
        "tanker attack", "vessel attack", "ship attack", "shipping halt", 
        "transit halt", "blockade", "war risk insurance", "insurance spike", 
        "naval incident", "irgc navy"
    ],
    "Kharg/Khark Attack or Seizure": [
        "kharg", "khark", "oil terminal", "export terminal", "landing", 
        "amphibious landing", "seize", "takeover", "capture", "export halt", 
        "loading stop", "offshore facilities", "loading jetty"
    ],
    "Critical Gulf Infrastructure Attacks": [
        "refinery", "oil facility", "processing plant", "gas plant", 
        "lng terminal", "desalination", "water plant", "pipeline", 
        "pumping station", "saudi", "uae", "fujairah", "abqaiq", 
        "ras tanura", "drone strike", "missile strike", "sabotage"
    ],
    "Direct Entry of Saudi/UAE/Coalition Forces": [
        "coalition", "multinational force", "ground forces", "troop deployment", 
        "amphibious operation", "saudi intervention", "uae intervention", 
        "joint operation", "allied response", "escalation", "regional war"
    ],
    "Red Sea / Bab el-Mandeb Escalation": [
        "houthis", "houthi attacks", "red sea", "bab el-mandeb", 
        "merchant vessels", "cargo ships", "shipping reroute", 
        "diversion", "naval escort", "convoy"
    ]
}