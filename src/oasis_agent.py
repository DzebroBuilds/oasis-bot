"""
╔══════════════════════════════════════════════════════════════════╗
║   O A S I S  B O T  —  Kalshi Prediction Market Trader          ║
║   Developed by: OasisWebAndAI  |  Seattle, Washington           ║
║   Integration: OasisParlay Webapp Sync (The Winning Brain)      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, json, time, logging, requests, base64, sys
from datetime import datetime, timezone, timedelta
from google import genai
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# NEW: Firebase Admin for Webapp Sync
import firebase_admin
from firebase_admin import credentials, firestore

# ── Load secrets ──────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s | OASIS | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("oasis")

# ── Validate secrets ──────────────────────────────────────────────────────────
# Added FIREBASE_KEY to the required list for webapp sync
REQUIRED = ["GEMINI_API_KEY", "KALSHI_API_KEY", "KALSHI_PRIVATE_KEY", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "FIREBASE_KEY"]
missing = [k for k in REQUIRED if not os.environ.get(k)]
if missing:
    raise SystemExit(f"OASIS: Missing secrets: {', '.join(missing)}\n  GitHub: add in Settings → Secrets → Actions")

GEMINI_API_KEY     = os.environ["GEMINI_API_KEY"]
KALSHI_API_KEY     = os.environ["KALSHI_API_KEY"]
KALSHI_PRIVATE_KEY = os.environ["KALSHI_PRIVATE_KEY"]
TELEGRAM_TOKEN     = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
FIREBASE_KEY_JSON  = os.environ["FIREBASE_KEY"]
PAPER_MODE         = os.environ.get("PAPER_MODE", "true").lower() == "true"

# MACRO TRADING THRESHOLDS
CONFIDENCE_THRESHOLD = 93  
UNIT_SIZE            = 15  
MAX_DAILY_SPEND      = 150
MAX_PER_CONTRACT     = 60

# EXHAUSTION SAFEGUARDS
MAX_AI_RESEARCH_COUNT = 15 

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"

# ── Firebase Setup (Oasis App Connection) ────────────────────────────────────
db = None
if not firebase_admin._apps:
    try:
        fb_key_data = json.loads(FIREBASE_KEY_JSON)
        fb_cred = credentials.Certificate(fb_key_data)
        firebase_admin.initialize_app(fb_cred)
        db = firestore.client()
        log.info("🔥 Oasis App Sync: Connected to Firestore")
    except Exception as e:
        log.error(f"🔥 Oasis App Sync: Failed to connect: {e}")

# ── Gemini AI ────────────────────────────────────────────────────────────────
ai_client = genai.Client(api_key=GEMINI_API_KEY)

def research_market(market: dict) -> dict:
    title      = market.get("title", "")
    subtitle   = market.get("subtitle", "")
    yes_price  = market.get("yes_ask", 50)
    ticker     = market.get("ticker", "")
    close_time = market.get("close_time", "")

    prompt = f"""You are OASIS, an elite quantitative macro analyst and momentum trader.
Your goal is to extract small, high-probability wins from Crypto, Economic, and Political prediction markets. 

STRATEGY:
1. CRYPTO: Look for spot-price lag. If Bitcoin/Ethereum is currently surging but the Kalshi price is lagging, buy YES.
2. POLITICS/ECONOMICS: Look for "Mean Reversion" (irrational panic) or "Polling Arbitrage" (math vs sentiment).
3. No 50/50 gambles. Only trade when the edge is mathematically superior.

MARKET: {title}
DETAIL: {subtitle}
TICKER: {ticker}
CLOSE:  {close_time}
YES:    {yes_price}¢

Evaluate the probability.
RESPOND JSON ONLY:
If high-probability trade: {{"skip":false,"side":"YES","confidence":95,"market_price":{yes_price},"edge":12,"units":2,"reasoning":"<short rationale>","ticker":"{ticker}"}}
If no clear edge: {{"skip":true,"reason":"No edge"}}"""

    try:
        r = ai_client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        text = r.text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        result["market"] = market
        return result
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            log.error("🛑 Gemini Free Tier exhausted. Shutting down research loop.")
            return {"skip": True, "exhausted": True, "market": market}
        log.error(f"AI error on {ticker}: {e}")
        return {"skip": True, "reason": "AI Error", "market": market}

# ── Kalshi Client (RSA V2) ───────────────────────────────────────────────────
class KalshiClient:
    def __init__(self):
        self.session = requests.Session()
        self.private_key = serialization.load_pem_private_key(
            KALSHI_PRIVATE_KEY.encode(), 
            password=None
        )

    def sign_request(self, timestamp, method, path):
        path_without_query = path.split('?')[0]
        msg = f"{timestamp}{method}{path_without_query}"
        signature = self.private_key.sign(
            msg.encode('utf-8'),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')

    def request(self, method, endpoint, params=None, json_data=None):
        timestamp = str(int(time.time() * 1000))
        full_path =
