"""
╔══════════════════════════════════════════════════════════════════╗
║   O A S I S  B O T  —  Kalshi Prediction Market Trader          ║
║   Developed by: OasisWebAndAI  |  Seattle, Washington           ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, json, time, logging, requests, base64
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

CONFIDENCE_THRESHOLD = 90
UNIT_SIZE            = 10
MAX_DAILY_SPEND      = 100
MAX_PER_CONTRACT     = 40
KALSHI_BASE          = "https://trading-api.kalshi.com/trade-api/v2"

# ── Gemini AI ────────────────────────────────────────────────────────────────
ai_client = genai.Client(api_key=GEMINI_API_KEY)

def research_market(market: dict) -> dict:
    title      = market.get("title", "")
    subtitle   = market.get("subtitle", "")
    yes_price  = market.get("yes_ask", 50)
    ticker     = market.get("ticker", "")
    close_time = market.get("close_time", "")

    prompt = f"""You are OASIS, an elite autonomous prediction market analyst.
Analyze this Kalshi market:
MARKET: {title}
DETAIL: {subtitle}
TICKER: {ticker}
CLOSE:  {close_time}
YES:    {yes_price}¢
RESPOND JSON ONLY:
If trading: {{"skip":false,"side":"YES","confidence":93,"market_price":{yes_price},"edge":23,"units":2,"reasoning":"...","ticker":"{ticker}"}}
If skipping: {{"skip":true,"reason":"..."}}"""

    try:
        r = ai_client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        text = r.text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        result["market"] = market
        return result
    except Exception as e:
        log.error(f"AI error on {ticker}: {e}")
        return {"skip": True, "reason": f"AI error: {e}", "market": market}

# ── Kalshi Authenticated Client (RSA V2) ─────────────────────────────────────
class KalshiClient:
    def __init__(self):
        self.session = requests.Session()
        # Load the RSA Private Key from your GitHub Secret
        self.private_key = serialization.load_pem_private_key(
            KALSHI_PRIVATE_KEY.encode(), 
            password=None
        )

    def sign_request(self, timestamp, method, path):
        """Generates the KALSHI-ACCESS-SIGNATURE for V2 API"""
        # Ensure query parameters are stripped for the signature message
        path_without_query = path.split('?')[0]
        msg = f"{timestamp}{method}{path_without_query}"
        
        # REST API requires PKCS1v15 padding
        signature = self.private_key.sign(
            msg.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')

    def request(self, method, endpoint, params=None, json_data=None):
        """Helper to inject required RSA auth headers into every request"""
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

    def get_sports_markets(self) -> list:
        KEYWORDS = ["NFL","NBA","NHL","MLB","NCAA","SOCCER","UFC","MMA","TENNIS","GOLF"]
        all_markets = []
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=48)

        r = self.request("GET", "/markets", params={"status": "open", "limit": 200})
        if r.status_code == 200:
            data = r.json()
            for m in data.get("markets", []):
                title = m.get("title", "").upper()
                is_sports = any(k in title for k in KEYWORDS) or m.get("category", "").upper() == "SPORTS"
                try:
                    close_dt = datetime.fromisoformat(m.get("close_time", "").replace("Z", "+00:00"))
                    if is_sports and now < close_dt <= cutoff:
                        all_markets.append(m)
                except: pass
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

    markets = kalshi.get_sports_markets()
    if not markets:
        telegram("🔍 <b>OASIS</b>: No qualifying sports markets")
        return

    for market in markets:
        pick = research_market(market)
        if not pick.get("skip") and pick.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
            ticker = pick["ticker"]
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
                telegram(f"🟢 <b>OASIS Trade Placed</b>\n{ticker}\nSide: {pick['side']} | ${actual}")
            else:
                log.error(f"Trade failed: {result}")
    
    save_daily(daily)

if __name__ == "__main__":
    run()
