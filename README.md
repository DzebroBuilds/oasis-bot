```
╔══════════════════════════════════════════════════════════════════╗
║                       OASIS BOT                                  ║
║        Autonomous Kalshi Prediction Market Trader                ║
║        Developed by OasisWebAndAI  |  Seattle, Washington        ║
╚══════════════════════════════════════════════════════════════════╝
```

## What Oasis does
- Runs automatically every 6 hours via GitHub Actions (free)
- Scans ALL open Kalshi sports prediction markets
- Researches each matchup using Gemini AI (free)
- Scores confidence 0–100
- Places trades ONLY on picks scoring 90%+ with real market edge
- Sends instant Telegram alerts to your phone for every trade
- Hard daily spend cap — never exceeds your set budget

---

## Setup (one time — ~45 minutes)

### 1. Gemini AI API — free at aistudio.google.com
- Visit https://aistudio.google.com/
- Sign in with Google → click "Get API key" → "Create API key"
- Free tier: 1,500 requests/day — plenty for Oasis
- Save as secret: `GEMINI_API_KEY`

### 2. Kalshi account
- Visit https://kalshi.com/
- Create account and deposit your trading bankroll
- Kalshi is CFTC-regulated and fully legal in Washington state
- Your email/password are the credentials Oasis uses
- Save as secrets: `KALSHI_EMAIL`, `KALSHI_PASSWORD`

### 3. Telegram alerts — free
- Open Telegram on your phone
- Search for @BotFather → send `/newbot` → follow prompts
- You'll get a bot TOKEN — save as: `TELEGRAM_TOKEN`
- Search for @userinfobot → send `/start` → get your CHAT_ID
- Save as: `TELEGRAM_CHAT_ID`
- Start a chat with your new bot so it can message you

---

## Deploy to GitHub (free hosting)

1. Create a free account at github.com
2. Create a new repository (can be private)
3. Upload these files to it
4. Go to: Settings → Secrets and variables → Actions → New repository secret
5. Add each of these secrets:

| Secret name      | Value                          |
|------------------|-------------------------------|
| GEMINI_API_KEY   | your Gemini key                |
| KALSHI_EMAIL     | your Kalshi email              |
| KALSHI_PASSWORD  | your Kalshi password           |
| TELEGRAM_TOKEN   | your Telegram bot token        |
| TELEGRAM_CHAT_ID | your Telegram chat ID          |
| PAPER_MODE       | true (start here!) or false    |

6. Go to Actions tab → click "I understand my workflows, enable them"
7. Oasis will now run automatically on its own every 6 hours

To run manually anytime:
Actions → "OASIS — Auto Scan & Trade" → "Run workflow" → Run

---

## IMPORTANT: Start in paper mode

Set `PAPER_MODE = true` as a GitHub secret first.

Oasis will run fully — research, score, find picks, send Telegram alerts —
but will NOT spend real money. Watch it for 1–2 weeks and verify the
90%+ picks are actually winning before switching to live.

To go live: change `PAPER_MODE` secret to `false`

---

## Bankroll settings (edit in src/oasis_agent.py)

| Setting              | Default | What it does                              |
|----------------------|---------|-------------------------------------------|
| CONFIDENCE_THRESHOLD | 90      | Min % score to place any trade            |
| UNIT_SIZE            | $10     | Base dollar amount per unit               |
| MAX_DAILY_SPEND      | $100    | Hard stop — Oasis quits after this/day    |
| MAX_PER_CONTRACT     | $40     | Max on any single Kalshi market           |

Recommended starting bankroll: $200–$500 on Kalshi

---

## Cost breakdown

| Component        | Cost                           |
|------------------|-------------------------------|
| GitHub Actions   | Free (2,000 min/month)        |
| Gemini Flash AI  | Free (1,500 req/day)          |
| ESPN data API    | Free (no key needed)           |
| Telegram alerts  | Free                           |
| Kalshi trading   | Your deposit only (withdrawable)|

Total monthly cost outside Kalshi deposit: $0

---

## How Kalshi markets work

Kalshi sells Yes/No contracts priced 1¢–99¢.
- If YES wins, the contract pays $1.00
- If NO wins, the contract pays $0
- Price = the market's implied probability

Example: "Will the Chiefs win Sunday?" priced at 72¢
- Market implies 72% chance Chiefs win
- If Oasis thinks Chiefs win 95%, the edge = 23 points
- Oasis buys YES contracts at 72¢, each pays $1 if correct
- Profit per contract: $0.28

---

Developed by OasisWebAndAI | Seattle, Washington
```
