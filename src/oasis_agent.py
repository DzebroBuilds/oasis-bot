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
MAX_MARKETS_PER_RUN = 30 # Never analyze more than 30 markets at a time

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

STRATEGY GUIDELINES:
1. CRYPTO: Look for spot-price lag. If Bitcoin/Ethereum is currently surging but the Kalshi contract price hasn't caught up, buy the momentum.
2. POLITICS/ECONOMICS: Look for "Mean Reversion" (irrational emotional sell-offs by retail traders) or "Polling Arbitrage" (where statistical math guarantees an outcome but the contract is underpriced).
3. Do NOT gamble on 50/50 coin tosses. You are looking for statistical certainty, irrational public fear, or mathematical edge.

MARKET: {title}
DETAIL: {subtitle}
TICKER: {ticker}
CLOSE:  {close_time}
YES:    {yes_price}¢

Evaluate the true probability of this outcome.
RESPOND JSON ONLY:
If a high-probability arbitrage/momentum trade exists: {{"skip":false,"side":"YES","confidence":95,"market_price":{yes_price},"edge":12,"units":2,"reasoning":"<short rationale>","ticker":"{ticker}"}}
If it lacks edge, is too volatile, or is a pure gamble: {{"skip":true,"reason":"Too volatile/No edge"}}"""

    try:
        r = ai_client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        text = r.text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        result["market"] = market
        return result
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            # If we hit the rate limit, return a specific "exhausted" flag so the bot knows to stop entirely.
            log.error(f"🛑 Gemini Free Tier exhausted! Safely shutting down AI analysis to prevent API lock.")
            return {"skip": True, "exhausted": True, "market": market}
        else:
            log.error(f"AI error on {ticker}: {e}")
            return {"skip": True, "reason": f"AI error: {e}", "market": market}

# ── Kalshi Authenticated Client (RSA V2) ─────────────────────────────────────
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
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
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
        if r.status_code == 200:
            log.info("Kalshi RSA Auth OK")
            return True
        log.error(f"Kalshi Auth Failed: {r.status_code} - {r.text}")
        return False

    def get_balance(self) -> float:
        r = self.request("GET", "/portfolio/balance")
        return r.json().get("balance", 0) / 100 if r.status_code == 200 else 0.0

    def get_target_markets(self) -> list:
        # HUNTING FOR CRYPTO, ECONOMICS, AND POLITICS
        KEYWORDS = ["BTC", "ETH", "CRYPTO", "BITCOIN", "ETHEREUM", "ELECTION", "POLITICS", "SENATE", "HOUSE", "ECONOMICS", "INFLATION", "CPI", "FED"]
        all_markets = []
        now = datetime.now(timezone.utc)
        
        cutoff = now + timedelta(days=7) 
        cursor = None

        log.info("Scanning Kalshi order book for Crypto & Political markets...")
        
        while True:
            params = {"status": "open", "limit": 1000}
            if cursor:
                params["cursor"] = cursor
                
            r = self.request("GET", "/markets", params=params)
            if r.status_code != 200:
                log.error(f"Market fetch failed: {r.text}")
                break
                
            data = r.json()
            markets_batch = data.get("markets", [])
            
            for m in markets_batch:
                title = m.get("title", "").upper()
                category = m.get("category", "").upper()
                
                is_target = any(k in title for k in KEYWORDS) or category in ["CRYPTO", "POLITICS", "ECONOMICS"]
                
                try:
                    close_dt = datetime.fromisoformat(m.get("close_time", "").replace("Z", "+00:00"))
                    if is_target and now < close_dt <= cutoff:
                        all_markets.append(m)
                except Exception:
                    pass
            
            cursor = data.get("cursor")
            if not cursor:
                break
                
            time.sleep(0.2) 

        log.info(f"Found {len(all_markets)} qualifying macro markets.")
        
        # Limit the number of markets returned to save Gemini API calls
        if len(all_markets) > MAX_MARKETS_PER_RUN:
             log.info(f"Trimming to top {MAX_MARKETS_PER_RUN} markets to protect API limits.")
             return all_markets[:MAX_MARKETS_PER_RUN]
             
        return all_markets

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

# ── Telegram alerts ───────────────────────────────────────────────────────────
def telegram(msg: str):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=8)
    except Exception as e: log.error(f"Telegram: {e}")

# ── Daily Tracking & Logic ────────────────────────────────────────────────────
LOG_PATH = "/tmp/oasis_daily.json"

def load_daily() -> dict:
    try:
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH) as f:
                d = json.load(f)
                if d.get("date") == datetime.now(timezone.utc).strftime("%Y-%m-%d"): return d
    except: pass
    return {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "spent": 0.0, "trades": [], "scanned": 0}

def save_daily(d: dict):
    with open(LOG_PATH, "w") as f: json.dump(d, f, indent=2)

def safe_to_trade(spend: float, daily: dict) -> tuple:
    if daily["spent"] >= MAX_DAILY_SPEND:
        return False, f"Daily cap hit (${MAX_DAILY_SPEND})"
    if daily["spent"] + spend > MAX_DAILY_SPEND:
        return False, "Would exceed daily cap"
    if spend > MAX_PER_CONTRACT:
        return False, f"Exceeds per-contract max (${MAX_PER_CONTRACT})"
    return True, "ok"

def run():
    mode = "PAPER MODE" if PAPER_MODE else "LIVE TRADING"
    log.info(f"OASIS starting — {mode}")
    daily = load_daily()
    kalshi = KalshiClient()

    if not kalshi.login():
        telegram("❌ <b>OASIS</b>: Kalshi auth failed — check RSA keys")
        return

    balance = kalshi.get_balance()
    log.info(f"Connected! Balance: ${balance:.2f}")

    markets = kalshi.get_target_markets()
    if not markets:
        telegram("🔍 <b>OASIS</b>: No qualifying macro markets found")
        return

    for market in markets:
        ticker = market.get("ticker", "Unknown")
        log.info(f"🧠 Asking Gemini to research {ticker}...")
        
        pick = research_market(market)
        
        # Check if the AI gracefully threw the exhaustion flag
        if pick.get("exhausted"):
            log.info("Ending run early to preserve API key.")
            break
        
        if not pick.get("skip") and pick.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
            price = pick["market_price"]
            contracts = max(1, int((UNIT_SIZE * 100) / price))
            actual = round((contracts * price) / 100, 2)

            ok, reason = safe_to_trade(actual, daily)
            if not ok:
                log.info(f"Blocked trade on {ticker}: {reason}")
                continue

            result = kalshi.place_trade(ticker, pick["side"], contracts, price)
            if "error" not in result:
                daily["spent"] += actual
                telegram(f"🟢 <b>OASIS Trade Placed</b>\n{ticker}\nSide: {pick['side']} | ${actual}\nReason: {pick.get('reasoning', 'No reason provided.')}")
            else:
                log.error(f"Trade failed: {result}")
        
        # Gentle pacing between requests
        time.sleep(6) 
    
    save_daily(daily)

if __name__ == "__main__":
    run()
