"""
╔══════════════════════════════════════════════════════════════════╗
║   O A S I S  B O T  —  Kalshi Prediction Market Trader          ║
║   Developed by: OasisWebAndAI  |  Seattle, Washington           ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, json, time, logging, requests
from datetime import datetime, timezone, timedelta
from google import genai

# ── Load secrets ──────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s | OASIS | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("oasis")

# ── Validate secrets ──────────────────────────────────────────────────────────
# Updated to require KALSHI_API_KEY as per your new setup
REQUIRED = ["GEMINI_API_KEY", "KALSHI_API_KEY", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]
missing = [k for k in REQUIRED if not os.environ.get(k)]
if missing:
    raise SystemExit(f"OASIS: Missing secrets: {', '.join(missing)}\n  Local: add to .env file\n  GitHub: add in Settings → Secrets → Actions")

GEMINI_API_KEY   = os.environ["GEMINI_API_KEY"]
KALSHI_API_KEY   = os.environ["KALSHI_API_KEY"]
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
PAPER_MODE       = os.environ.get("PAPER_MODE", "true").lower() == "true"

CONFIDENCE_THRESHOLD = 90
UNIT_SIZE            = 10
MAX_DAILY_SPEND      = 100
MAX_PER_CONTRACT     = 40
KALSHI_BASE          = "https://trading-api.kalshi.com/trade-api/v2"

# ── Gemini AI (new SDK) ───────────────────────────────────────────────────────
ai_client = genai.Client(api_key=GEMINI_API_KEY)

def research_market(market: dict) -> dict:
    title      = market.get("title", "")
    subtitle   = market.get("subtitle", "")
    yes_price  = market.get("yes_ask", 50)
    no_price   = market.get("no_ask", 50)
    ticker     = market.get("ticker", "")
    close_time = market.get("close_time", "")

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

RESPOND JSON ONLY — no markdown, no explanation outside the JSON:
If trading: {{"skip":false,"side":"YES","confidence":93,"true_probability":93,"market_price":{yes_price},"edge":23,"units":2,"reasoning":"2-sentence reason","risk":"1 sentence risk","ticker":"{ticker}"}}
Units: 90-94%=1 | 95-97%=2 | 98%+=3
If skipping: {{"skip":true,"reason":"brief explanation"}}"""

    try:
        r = ai_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        text = r.text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        result["market"] = market
        return result
    except Exception as e:
        log.error(f"AI error on {ticker}: {e}")
        return {"skip": True, "reason": f"AI error: {e}", "market": market}


# ── Kalshi client (API key auth — no MFA needed) ──────────────────────────────
class KalshiClient:
    def __init__(self):
        self.session = requests.Session()

    def login(self) -> bool:
        self.session.headers.update({
            "KALSHI-ACCESS-KEY": KALSHI_API_KEY,
            "Content-Type": "application/json"
        })
        r = self.session.get(f"{KALSHI_BASE}/portfolio/balance", timeout=10)
        if r.status_code == 200:
            log.info("Kalshi API key auth OK")
            return True
        log.error(f"Kalshi API key auth failed: {r.status_code} — {r.text}")
        return False

    def get_balance(self) -> float:
        r = self.session.get(f"{KALSHI_BASE}/portfolio/balance", timeout=10)
        return r.json().get("balance", 0) / 100 if r.status_code == 200 else 0.0

    def get_sports_markets(self) -> list:
        KEYWORDS = ["NFL","NBA","NHL","MLB","NCAA","SOCCER","UFC","MMA","TENNIS","GOLF","EPL","CHAMPIONS","WNBA","MLS"]
        all_markets, cursor = [], None
        now    = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=48)

        while True:
            params = {"status": "open", "limit": 200}
            if cursor:
                params["cursor"] = cursor
            r = self.session.get(f"{KALSHI_BASE}/markets", params=params, timeout=15)
            if r.status_code != 200:
                log.error(f"Markets fetch failed: {r.status_code}")
                break
            data = r.json()
            for m in data.get("markets", []):
                title = m.get("title", "").upper()
                is_sports = any(k in title for k in KEYWORDS) or m.get("category", "").upper() == "SPORTS"
                try:
                    close_dt = datetime.fromisoformat(m.get("close_time", "").replace("Z", "+00:00"))
                    closing_soon = now < close_dt <= cutoff
                except:
                    closing_soon = True
                if is_sports and closing_soon:
                    all_markets.append(m)
            cursor = data.get("cursor")
            if not cursor or not data.get("markets"):
                break
            time.sleep(0.3)

        log.info(f"Found {len(all_markets)} Kalshi sports markets")
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
        r = self.session.post(f"{KALSHI_BASE}/portfolio/orders", json=payload, timeout=15)
        return r.json() if r.status_code in (200, 201) else {"error": r.text}


# ── Telegram alerts ───────────────────────────────────────────────────────────
def telegram(msg: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=8
        )
    except Exception as e:
        log.error(f"Telegram: {e}")


# ── Daily spend tracker ───────────────────────────────────────────────────────
LOG_PATH = "/tmp/oasis_daily.json"

def load_daily() -> dict:
    try:
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH) as f:
                d = json.load(f)
            if d.get("date") == datetime.now(timezone.utc).strftime("%Y-%m-%d"):
                return d
    except Exception:
        pass
    return {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "spent": 0.0, "trades": [], "scanned": 0}

def save_daily(d: dict):
    try:
        with open(LOG_PATH, "w") as f:
            json.dump(d, f, indent=2)
    except Exception as e:
        log.error(f"Failed to save daily log: {e}")

def safe_to_trade(spend: float, daily: dict) -> tuple:
    if daily["spent"] >= MAX_DAILY_SPEND:
        return False, f"Daily cap hit (${MAX_DAILY_SPEND})"
    if daily["spent"] + spend > MAX_DAILY_SPEND:
        return False, "Would exceed daily cap"
    if spend > MAX_PER_CONTRACT:
        return False, f"Exceeds per-contract max (${MAX_PER_CONTRACT})"
    return True, "ok"


# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    mode = "PAPER MODE" if PAPER_MODE else "LIVE TRADING"
    log.info(f"OASIS starting — {mode}")
    telegram(f"🌴 <b>OASIS — Starting</b>\nMode: {mode}\nMin confidence: {CONFIDENCE_THRESHOLD}%\nBudget: ${MAX_DAILY_SPEND}/day\n<i>OasisWebAndAI · Seattle, WA</i>")

    daily  = load_daily()
    kalshi = KalshiClient()

    if not kalshi.login():
        telegram("❌ <b>OASIS</b>: Kalshi auth failed — check KALSHI_API_KEY secret")
        return

    balance = kalshi.get_balance()
    log.info(f"Kalshi balance: ${balance:.2f}")
    if balance < UNIT_SIZE and not PAPER_MODE:
        telegram(f"⚠️ <b>OASIS</b>: Low Kalshi balance (${balance:.2f}) — top up your account")
        return

    markets = kalshi.get_sports_markets()
    daily["scanned"] += len(markets)

    if not markets:
        telegram("🔍 <b>OASIS</b>: No qualifying sports markets right now")
        save_daily(daily)
        return

    telegram(f"🔍 Researching <b>{len(markets)}</b> Kalshi markets...")

    qualified, skipped = [], 0
    for i, market in enumerate(markets):
        log.info(f"[{i+1}/{len(markets)}] {market.get('title', '')}")
        pick = research_market(market)
        time.sleep(1.2)
        if pick.get("skip"):
            skipped += 1
        else:
            log.info(f"  PICK {pick['side']} {pick['confidence']}% edge+{pick['edge']}")
            qualified.append(pick)

    if not qualified:
        telegram(f"🌴 <b>OASIS</b>: No qualifying picks today\nScanned: {len(markets)} markets\n<i>Staying patient is a strategy.</i>")
        save_daily(daily)
        return

    placed = 0
    for pick in sorted(qualified, key=lambda x: x["confidence"], reverse=True):
        ticker    = pick["ticker"]
        side      = pick["side"].lower()
        price     = pick["market_price"]
        spend     = min(pick.get("units", 1) * UNIT_SIZE, MAX_PER_CONTRACT)
        contracts = max(1, int((spend * 100) / price))
        actual    = round((contracts * price) / 100, 2)
        pick["contracts"] = contracts

        ok, reason = safe_to_trade(actual, daily)
        if not ok:
            telegram(f"⛔ <b>OASIS</b>: Blocked — {reason}")
            continue

        result = kalshi.place_trade(ticker, side, contracts, price)
        if "error" not in result:
            placed += 1
            daily["spent"] += actual
            daily["trades"].append({
                "time": datetime.now(timezone.utc).isoformat(),
                "ticker": ticker,
                "title": pick["market"].get("title", ""),
                "side": side, "contracts": contracts,
                "price": price, "spend": actual,
                "confidence": pick["confidence"],
                "edge": pick["edge"],
                "outcome": "open", "pnl": None
            })
            save_daily(daily)
            icon   = "📄" if PAPER_MODE else "🟢"
            action = "Simulated" if PAPER_MODE else "Placed"
            telegram(f"""{icon} <b>OASIS — Trade {action}</b>
<b>{pick['market'].get('title','')}</b>
Side: {side.upper()} · {contracts} contracts @ {price}¢
Spent: ${actual:.2f} · Confidence: {pick['confidence']}% · Edge: +{pick['edge']}pts
{pick.get('reasoning', '')}
<i>OasisWebAndAI · Seattle, WA</i>""")
        else:
            log.error(f"Trade failed: {ticker} — {result.get('error')}")
            telegram(f"❌ <b>OASIS</b>: Trade failed — {ticker}")

    telegram(f"""📊 <b>OASIS — Session Summary</b>
Scanned: {len(markets)} · Picks: {len(qualified)} · Placed: {placed}
Spent: ${daily['spent']:.2f} / ${MAX_DAILY_SPEND}
<i>OasisWebAndAI · Seattle, WA</i>""")
    save_daily(daily)


if __name__ == "__main__":
    run()
