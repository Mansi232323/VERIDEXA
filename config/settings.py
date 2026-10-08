"""
VERIDEXA central configuration.
Reads environment variables (via .env) and exposes app-wide constants.
Nothing in here talks to the network; it's pure config.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

APP_NAME = "VERIDEXA"
APP_TAGLINE = "See the truth in your data."

# --- Storage locations -----------------------------------------------
DB_PATH = BASE_DIR / "veridexa.db"
LOG_PATH = BASE_DIR / "logs" / "app.log"
UPLOAD_MAX_MB = int(os.getenv("UPLOAD_MAX_MB", "5120"))  # 5 GB default (> 1 GB)

# --- Auth / security ---------------------------------------------------
SESSION_TIMEOUT_MINUTES = 120
PASSWORD_MIN_LENGTH = 8
PBKDF2_ITERATIONS = 260_000
MAX_LOGIN_ATTEMPTS = 5          # failed attempts allowed...
LOGIN_LOCKOUT_MINUTES = 15      # ...before a temporary lockout kicks in

# --- LLM abstraction (optional; app works fully without it) -----------
# The AI Analyst runs on a validated rule-based query engine by default,
# so the app is fully functional with NO API key at all. If you want
# richer natural-language phrasing of results, set these and flip
# USE_LLM_PHRASING to True in modules/ai_analyzer.py.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
# Only used by the "ollama" provider (a local server), which needs no key.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")

# --- Feature flags -------------------------------------------------
ENABLE_KMEANS_SEGMENTATION = True
ENABLE_FORECASTING = True
ENABLE_ANOMALY_DETECTION = True
