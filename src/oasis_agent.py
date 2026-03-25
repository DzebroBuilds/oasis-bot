"""
╔══════════════════════════════════════════════════════════════════╗
║   O A S I S  B O T  —  Kalshi Prediction Market Trader          ║
║   Developed by: OasisWebAndAI  |  Seattle, Washington           ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, json, time, logging, requests
from datetime import datetime, timezone, timedelta
import google.generativeai as genai

# ── Load secrets ──────────────────────────────────────────────────────────────
# Local dev:  reads from .env file (never uploaded to GitHub — in .gitignore)
# Production: reads from encrypted GitHub Actions Secrets automatically
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s | OASIS | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("oasis")

# ── Validate secrets present ──────────────────────────────────────────────────
REQUIRED = ["GEMINI_API_KEY","KALSHI_EMAIL","KALSHI_PASSWORD","TELEGRAM_TOKEN","TELEGRAM_CHAT_ID"]
missing = [k for k in REQUIRED if not os.environ.get(k)]
if missing:
    raise SystemExit(f"OASIS: Missing secrets: {', '.join(missing)}\n  Local: add to .env file\n  GitHub: add in Settings → Secrets → Actions")

GEMINI_API_KEY   = os.environ["GEMINI_API_KEY"]
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
PAPER_MODE       = os.environ.get("PAPER_MODE","true").lower() == "true"

CONFIDENCE_THRESHOLD = 90
UNIT_SIZE            = 10
MAX_DAILY_SPEND      = 100
MAX_PER_CONTRACT     = 40
KALSHI_BASE          = "https://trading-api.kalshi.com/trade-api/v2"

# ── Gemini AI (free 1,500 req/day) ────────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)
ai = genai.GenerativeModel("gemini-1.5-flash", generation_config={"temperature":0.1,"max_output_tokens":900})

def research_market(market: dict) -> dict:
    title, subtitle  = market.get("title",""), market.get("subtitle","")
    yes_price, no_price = market.get("yes_ask",50), market.get("no_ask",50)
    ticker           = market.get("ticker","")
    close_time       = market.get("close_time","")

    prompt = f"""You are OASIS, elite autonomous prediction market analyst by OasisWebAndAI, Seattle WA.

Analyze this Kalshi market:
MARKET: {title}
DETAIL: {subtitle}
TICKER: {ticker}
CLOSE:  {close_time}
YES:    {yes_price}¢ (implies {yes_price}% YES wins)
NO:     {no_price}¢  (implies {no_price}% NO wins)

Research: recent form, H2H, home advantage, injuries, motivation, market edge, line movement.

Only trade if confidence >= 90 AND your estimate beats market by 10+ points.

RESPOND JSON ONLY:
If trading: {{"skip":false,"side":"YES","confidence":93,"true_probability":93,"market_price":{yes_price},"edge":23,"units":2,"reasoning":"2-sentence reason","risk":"1 sentence risk","ticker":"{ticker}"}}
Units: 90-94%=1 | 95-97%=2 | 98%+=3
If skipping: {{"skip":true,"reason":"brief explanation"}}"""

    try:
        r = ai.generate_content(prompt)
        text = r.text.strip().replace("```json","").replace("```","").strip()
        result = json.loads(text)
        result["market"] = market
        return result
    except Exception as e:
        return {"skip":True,"reason":f"AI error: {e}","market":market}

# ── Kalshi client ─────────────────────────────────────────────────────────────
class KalshiClient:
    def __init__(self):
        self.session = requests.Session()

    def login(self):
        r = self.session.post(f"{KALSHI_BASE}/login", json={"email":KALSHI_EMAIL,"password":KALSHI_PASSWORD}, timeout=15)
        if r.status_code == 200:
            token = r.json().get("token")
            self.session.headers.update({"Authorization":f"Bearer {token}","Content-Type":"application/json"})
            log.info("Kalshi login OK")
            return True
        log.error(f"Kalshi login failed: {r.status_code}")
        return False

    def get_balance(self):
        r = self.session.get(f"{KALSHI_BASE}/portfolio/balance", timeout=10)
        return r.json().get("balance",0)/100 if r.status_code==200 else 0.0

    def get_sports_markets(self):
        KEYWORDS = ["NFL","NBA","NHL","MLB","NCAA","SOCCER","UFC","MMA","TENNIS","GOLF","EPL","CHAMPIONS","WNBA","MLS"]
        all_markets, cursor = [], None
        now, cutoff = datetime.now(timezone.utc), datetime.now(timezone.utc)+timedelta(hours=48)
        while True:
            params = {"status":"open","limit":200}
            if cursor: params["cursor"] = cursor
            r = self.session.get(f"{KALSHI_BASE}/markets", params=params, timeout=15)
            if r.status_code != 200: break
            data = r.json()
            for m in data.get("markets",[]):
                title = m.get("title","").upper()
                is_sports = any(k in title for k in KEYWORDS) or m.get("category","").upper() == "SPORTS"
                try:
                    close_dt = datetime.fromisoformat(m.get("close_time","").replace("Z","+00:00"))
                    closing_soon = now < close_dt <= cutoff
                except:
                    closing_soon = True
                if is_sports and closing_soon:
                    all_markets.append(m)
            cursor = data.get("cursor")
            if not cursor or not data.get("markets"): break
            time.sleep(0.3)
        log.info(f"Found {len(all_markets)} Kalshi sports markets")
        return all_markets

    def place_trade(self, ticker, side, count, price_cents):
        if PAPER_MODE:
            log.info(f"[PAPER] {side.upper()} {count}x {ticker} @ {price_cents}¢")
            return {"paper":True}
        payload = {
            "action":"buy","client_order_id":f"oasis_{ticker}_{int(time.time())}",
            "count":count,"side":side.lower(),"ticker":ticker,"type":"limit",
            "yes_price": price_cents if side.lower()=="yes" else (100-price_cents),
            "no_price":  price_cents if side.lower()=="no"  else (100-price_cents),
        }
        r = self.session.post(f"{KALSHI_BASE}/portfolio/orders", json=payload, timeout=15)
        return r.json() if r.status_code in (200,201) else {"error":r.text}

# ── Telegram ──────────────────────────────────────────────────────────────────
def telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id":TELEGRAM_CHAT_ID,"text":msg,"parse_mode":"HTML"}, timeout=8)
    except Exception as e:
        log.error(f"Telegram: {e}")

# ── Daily spend tracker ───────────────────────────────────────────────────────
LOG_PATH = "/tmp/oasis_daily.json"

def load_daily():
    try:
        with open(LOG_PATH) as f:
            d = json.load(f)
        if d.get("date") == datetime.now(timezone.utc).strftime("%Y-%m-%d"):
            return d
    except: pass
    return {"date":datetime.now(timezone.utc).strftime("%Y-%m-%d"),"spent":0.0,"trades":[],"scanned":0}

def save_daily(d):
    with open(LOG_PATH,"w") as f: json.dump(d,f,indent=2)

def safe_to_trade(spend, daily):
    if daily["spent"] >= MAX_DAILY_SPEND: return False, f"Daily cap hit (${MAX_DAILY_SPEND})"
    if daily["spent"]+spend > MAX_DAILY_SPEND: return False, "Would exceed daily cap"
    if spend > MAX_PER_CONTRACT: return False, f"Exceeds per-contract max"
    return True, "ok"

# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    mode = "PAPER MODE" if PAPER_MODE else "LIVE TRADING"
    log.info(f"OASIS starting — {mode}")
    telegram(f"🌴 <b>OASIS — Starting</b>\nMode: {mode}\nMin confidence: {CONFIDENCE_THRESHOLD}%\nBudget: ${MAX_DAILY_SPEND}/day\n<i>OasisWebAndAI · Seattle, WA</i>")

    daily = load_daily()
    kalshi = KalshiClient()
    if not kalshi.login():
        telegram("❌ <b>OASIS</b>: Kalshi login failed — check credentials"); return

    balance = kalshi.get_balance()
    if balance < UNIT_SIZE and not PAPER_MODE:
        telegram(f"⚠️ <b>OASIS</b>: Low Kalshi balance (${balance:.2f})"); return

    markets = kalshi.get_sports_markets()
    daily["scanned"] += len(markets)
    if not markets:
        telegram("🔍 <b>OASIS</b>: No qualifying markets right now"); return

    telegram(f"🔍 Researching <b>{len(markets)}</b> Kalshi markets...")

    qualified, skipped = [], 0
    for i, market in enumerate(markets):
        log.info(f"[{i+1}/{len(markets)}] {market.get('title','')}")
        pick = research_market(market)
        time.sleep(1.2)
        if pick.get("skip"): skipped += 1
        else:
            log.info(f"  PICK {pick['side']} {pick['confidence']}% edge+{pick['edge']}")
            qualified.append(pick)

    if not qualified:
        telegram(f"🌴 <b>OASIS</b>: No qualifying picks\nScanned: {len(markets)} markets\n<i>Staying patient is a strategy.</i>")
        save_daily(daily); return

    placed = 0
    for pick in sorted(qualified, key=lambda x: x["confidence"], reverse=True):
        ticker    = pick["ticker"]
        side      = pick["side"].lower()
        price     = pick["market_price"]
        spend     = min(pick.get("units",1)*UNIT_SIZE, MAX_PER_CONTRACT)
        contracts = max(1, int((spend*100)/price))
        actual    = round((contracts*price)/100, 2)
        pick["contracts"] = contracts

        ok, reason = safe_to_trade(actual, daily)
        if not ok:
            telegram(f"⛔ <b>OASIS</b>: Blocked — {reason}"); continue

        result = kalshi.place_trade(ticker, side, contracts, price)
        if "error" not in result:
            placed += 1
            daily["spent"] += actual
            daily["trades"].append({
                "time":datetime.now(timezone.utc).isoformat(), "ticker":ticker,
                "title":pick["market"].get("title",""), "side":side,
                "contracts":contracts, "price":price, "spend":actual,
                "confidence":pick["confidence"], "edge":pick["edge"],
                "outcome":"open", "pnl":None
            })
            save_daily(daily)
            icon = "📄" if PAPER_MODE else "🟢"
            action = "Simulated" if PAPER_MODE else "Placed"
            telegram(f"""{icon} <b>OASIS — Trade {action}</b>
<b>{pick['market'].get('title','')}</b>
Side: {side.upper()} · {contracts} contracts @ {price}¢
Spent: ${actual:.2f} · Confidence: {pick['confidence']}% · Edge: +{pick['edge']}pts
{pick.get('reasoning','')}
<i>OasisWebAndAI · Seattle, WA</i>""")
        else:
            telegram(f"❌ <b>OASIS</b>: Trade failed — {ticker}")

    telegram(f"""📊 <b>OASIS — Session Summary</b>
Scanned: {len(markets)} · Picks: {len(qualified)} · Placed: {placed}
Spent: ${daily['spent']:.2f} / ${MAX_DAILY_SPEND}
<i>OasisWebAndAI · Seattle, WA</i>""")
    save_daily(daily)

if __name__ == "__main__":
    run()
