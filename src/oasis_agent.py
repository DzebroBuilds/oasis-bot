"""
╔══════════════════════════════════════════════════════════════════╗
║   O A S I S  B O T  —  Kalshi Prediction Market Trader          ║
║   Developed by: OasisWebAndAI  |  Seattle, Washington           ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, json, time, logging, requests, base64, sys
from datetime import datetime, timezone, timedelta
from google import genai
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# ── Load secrets ──────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s | OASIS | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("oasis")

# ── Validate secrets ──────────────────────────────────────────────────────────
REQUIRED = ["GEMINI_API_KEY", "KALSHI_API_KEY", "KALSHI_PRIVATE_KEY", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]
missing = [k for k in REQUIRED if not os.environ.get(k)]
if missing:
    raise SystemExit(f"OASIS: Missing secrets: {', '.join(missing)}\n  GitHub: add in Settings → Secrets → Actions")

GEMINI_API_KEY     = os.environ["GEMINI_API_KEY"]
KALSHI_API_KEY     = os.environ["KALSHI_API_KEY"]
KALSHI_PRIVATE_KEY = os.environ["KALSHI_PRIVATE_KEY"]
TELEGRAM_TOKEN     = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
PAPER_MODE         = os.environ.get("PAPER_MODE", "true").lower() == "true"

# MACRO TRADING THRESHOLDS
CONFIDENCE_THRESHOLD = 93  
UNIT_SIZE            = 15  
MAX_DAILY_SPEND      = 150
MAX_PER_CONTRACT     = 60

# EXHAUSTION SAFEGUARDS
MAX_AI_RESEARCH_COUNT = 15 # Only ask Gemini about the top 15 most active markets

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"

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
        r = ai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text = r.text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        result["market"] = market
        return result
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            log.error("🛑 Gemini Free Tier exhausted. Shutting down research loop.")
            return {"skip": True, "exhausted": True, "market": market}
        if "404" in err or "NOT_FOUND" in err:
            log.error(f"🛑 Model not found: {e}. Check model name in code.")
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
        full_path = f"/trade-api/v2{endpoint}"
        headers = {
            "KALSHI-ACCESS-KEY": KALSHI_API_KEY,
            "KALSHI-ACCESS-SIGNATURE": self.sign_request(timestamp, method, full_path),
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }
        url = f"{KALSHI_BASE}{endpoint}"
        return self.session.request(method, url, headers=headers, params=params, json=json_data, timeout=15)

    def login(self) -> bool:
        r = self.request("GET", "/portfolio/balance")
        return r.status_code == 200

    def get_balance(self) -> float:
        r = self.request("GET", "/portfolio/balance")
        return r.json().get("balance", 0) / 100 if r.status_code == 200 else 0.0

    def get_target_markets(self) -> list:
        KEYWORDS = ["BTC", "ETH", "CRYPTO", "BITCOIN", "ETHEREUM", "ELECTION", "POLITICS", "ECONOMICS", "FED"]
        all_markets = []
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=7) 
        cursor = None

        log.info("Scanning Kalshi order book...")
        while True:
            params = {"status": "open", "limit": 1000}
            if cursor: params["cursor"] = cursor
            r = self.request("GET", "/markets", params=params)
            if r.status_code != 200: break
            
            data = r.json()
            for m in data.get("markets", []):
                title = m.get("title", "").upper()
                cat = m.get("category", "").upper()
                is_target = any(k in title for k in KEYWORDS) or cat in ["CRYPTO", "POLITICS", "ECONOMICS"]
                
                try:
                    close_dt = datetime.fromisoformat(m.get("close_time", "").replace("Z", "+00:00"))
                    if is_target and now < close_dt <= cutoff:
                        # Prioritize Volume for 'Hottest' markets
                        m["_sort_score"] = m.get("volume", 0)
                        all_markets.append(m)
                except: pass
            
            cursor = data.get("cursor")
            if not cursor: break
            time.sleep(0.1)

        # SORT BY VOLUME (Hottest First)
        all_markets.sort(key=lambda x: x["_sort_score"], reverse=True)
        
        log.info(f"Filtered {len(all_markets)} total macro targets.")
        log.info(f"Snipping top {MAX_AI_RESEARCH_COUNT} highest-volume markets for research.")
        return all_markets[:MAX_AI_RESEARCH_COUNT]

    def place_trade(self, ticker: str, side: str, count: int, price_cents: int) -> dict:
        if PAPER_MODE:
            log.info(f"[PAPER] {side.upper()} {count}x {ticker} @ {price_cents}¢")
            return {"paper": True}
        payload = {
            "action": "buy",
            "client_order_id": f"oasis_{ticker}_{int(time.time())}",
            "count": count,
            "side": side.lower(),
            "ticker": ticker,
            "type": "limit",
            "yes_price": price_cents if side.lower() == "yes" else (100 - price_cents),
            "no_price":  price_cents if side.lower() == "no"  else (100 - price_cents),
        }
        r = self.request("POST", "/portfolio/orders", json_data=payload)
        return r.json() if r.status_code in (200, 201) else {"error": r.text}

# ── Utility ──────────────────────────────────────────────────────────────────
def telegram(msg: str):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=8)
    except: pass

def load_daily() -> dict:
    return {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "spent": 0.0}

def run():
    log.info(f"OASIS active — {'PAPER' if PAPER_MODE else 'LIVE'}")
    kalshi = KalshiClient()
    if not kalshi.login():
        log.error("Auth failed")
        return

    balance = kalshi.get_balance()
    log.info(f"Balance: ${balance:.2f}")

    markets = kalshi.get_target_markets()
    daily = load_daily()

    for market in markets:
        ticker = market.get("ticker", "Unknown")
        log.info(f"🧠 Researching {ticker} (Vol: {market.get('volume', 0)})")
        
        pick = research_market(market)
        
        if pick.get("exhausted"):
            log.warning("Exiting loop: Gemini limit reached.")
            break
            
        if not pick.get("skip") and pick.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
            price = pick["market_price"]
            contracts = max(1, int((UNIT_SIZE * 100) / price))
            actual = round((contracts * price) / 100, 2)

            if daily["spent"] + actual > MAX_DAILY_SPEND: continue

            result = kalshi.place_trade(ticker, pick["side"], contracts, price)
            if "error" not in result:
                daily["spent"] += actual
                telegram(f"🟢 <b>OASIS PICK</b>\n{ticker}\nSide: {pick['side']} | Conf: {pick['confidence']}%\nReason: {pick.get('reasoning')}")
        
        time.sleep(6) # Stay under Gemini RPM limits

if __name__ == "__main__":
    run()
