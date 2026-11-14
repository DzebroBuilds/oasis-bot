"""Offline-only paper ledger. Integer cents; no provider clients or credentials."""
import json
import math
import sqlite3
from datetime import datetime, timezone


def utc(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timezone required')
    return parsed.astimezone(timezone.utc)


def integer(value, low, high):
    return type(value) is int and low <= value <= high


class PaperEngine:
    def __init__(self, path, daily_cap=15000, unit_cap=1500, event_cap=3000):
        if any(not integer(v, 1, 100000000) for v in (daily_cap, unit_cap, event_cap)):
            raise ValueError('Invalid limits')
        self.limits = daily_cap, unit_cap, event_cap
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS decisions (
          id INTEGER PRIMARY KEY, at TEXT NOT NULL, ticker TEXT, reason TEXT NOT NULL,
          snapshot TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS positions (
          ticker TEXT PRIMARY KEY, event TEXT NOT NULL, day TEXT NOT NULL,
          side TEXT NOT NULL, count INTEGER NOT NULL, cost INTEGER NOT NULL,
          probability REAL NOT NULL, status TEXT NOT NULL, pnl INTEGER,
          yes_won INTEGER);
        CREATE TABLE IF NOT EXISTS controls (id INTEGER PRIMARY KEY CHECK(id=1), paused INTEGER NOT NULL);
        INSERT OR IGNORE INTO controls VALUES (1, 0);
        ''')

    def pause(self, paused):
        if type(paused) is not bool:
            raise ValueError('Boolean required')
        self.db.execute('UPDATE controls SET paused=? WHERE id=1', (int(paused),))

    def evaluate(self, snapshot, now=None):
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError('Timezone required')
        now = now.astimezone(timezone.utc)
        day = now.date().isoformat()
        # Serialize before transaction so unserializable input cannot leave a lock.
        raw = json.dumps(snapshot, allow_nan=False, sort_keys=True)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            reason, order = self._assess(snapshot, now, day)
            self.db.execute('INSERT INTO decisions(at,ticker,reason,snapshot) VALUES (?,?,?,?)',
                            (now.isoformat(), snapshot.get('ticker'), reason, raw))
            if order:
                self.db.execute('INSERT INTO positions VALUES (?,?,?,?,?,?,?, ?,NULL,NULL)',
                                (snapshot['ticker'], snapshot['event'], day, order['side'],
                                 order['count'], order['cost_cents'], snapshot['probability_yes'], 'open'))
            self.db.execute('COMMIT')
            return {'accepted': order is not None, 'reason': reason, 'order': order}
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def _assess(self, s, now, day):
        def reject(reason):
            return reason, None
        if self.db.execute('SELECT paused FROM controls WHERE id=1').fetchone()[0]:
            return reject('paused')
        if any(not isinstance(s.get(k), str) or not s[k].strip() for k in ('ticker', 'event', 'rules', 'model_version')):
            return reject('missing_identity_rules_or_model')
        if self.db.execute('SELECT 1 FROM positions WHERE ticker=?', (s['ticker'],)).fetchone():
            return reject('duplicate_market')
        p, uncertainty = s.get('probability_yes'), s.get('uncertainty')
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in (p, uncertainty)):
            return reject('invalid_probability')
        try:
            quote_age = (now - utc(s['quoted_at'])).total_seconds()
            close = utc(s['closes_at'])
            evidence = s['evidence']
            if not isinstance(evidence, list) or not evidence:
                return reject('missing_evidence')
            for e in evidence:
                age = (now - utc(e['observed_at'])).total_seconds()
                if not isinstance(e['url'], str) or not e['url'].startswith('https://') or not isinstance(e['summary'], str) or not e['summary'].strip() or not 0 <= age <= 3600:
                    return reject('stale_or_invalid_evidence')
        except (KeyError, TypeError, ValueError, AttributeError):
            return reject('invalid_timestamps_or_evidence')
        if not 0 <= quote_age <= 60 or close <= now:
            return reject('stale_or_closed_market')
        # Fee is a caller-supplied conservative per-contract bound, NOT a Kalshi fee formula.
        fee = s.get('fee_bound_cents')
        if not integer(fee, 0, 100):
            return reject('missing_fee_bound')
        candidates = []
        for side, probability in (('yes', p), ('no', 1-p)):
            price = s.get(side + '_ask_cents')
            size = s.get(side + '_ask_size')
            if not integer(price, 1, 99) or not integer(size, 1, 1000000):
                continue
            edge = 100 * (probability - uncertainty) - price - fee
            if edge >= 5:
                candidates.append((edge, side, price, size))
        if not candidates:
            return reject('insufficient_edge_or_liquidity')
        edge, side, price, size = max(candidates)
        daily_cap, unit_cap, event_cap = self.limits
        spent = self.db.execute('SELECT COALESCE(SUM(cost),0) FROM positions WHERE day=?', (day,)).fetchone()[0]
        exposure = self.db.execute("SELECT COALESCE(SUM(cost),0) FROM positions WHERE event=? AND status='open'", (s['event'],)).fetchone()[0]
        budget = min(unit_cap, daily_cap-spent, event_cap-exposure)
        count = min(size, budget // (price+fee))
        if count < 1:
            return reject('budget_or_event_limit')
        return 'paper_fill_assumed', {'side': side, 'count': count, 'price_cents': price,
                                     'cost_cents': count*(price+fee), 'edge_cents': edge}

    def settle(self, ticker, yes_won):
        if type(yes_won) is not bool:
            raise ValueError('Settlement requires a boolean outcome')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT side,count,cost,status,yes_won FROM positions WHERE ticker=?', (ticker,)).fetchone()
            if row is None:
                raise ValueError('Unknown market')
            side, count, cost, status, previous = row
            if status == 'settled' and previous != int(yes_won):
                raise ValueError('Conflicting settlement')
            pnl = (100*count if (side == 'yes') == yes_won else 0)-cost
            self.db.execute("UPDATE positions SET status='settled',pnl=?,yes_won=? WHERE ticker=?", (pnl, int(yes_won), ticker))
            self.db.execute('COMMIT')
            return pnl
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def report(self):
        rows = self.db.execute('SELECT probability,yes_won,pnl FROM positions WHERE status=\'settled\'').fetchall()
        return {'mode': 'paper', 'settled': len(rows), 'pnl_cents': sum(r[2] for r in rows),
                'brier_score': sum((r[0]-r[1])**2 for r in rows)/len(rows) if rows else None,
                'open_positions': self.db.execute("SELECT COUNT(*) FROM positions WHERE status='open'").fetchone()[0],
                'decisions': self.db.execute('SELECT COUNT(*) FROM decisions').fetchone()[0]}


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Offline Oasis V2 paper ledger')
    parser.add_argument('--db', required=True, help='Persistent local SQLite path')
    sub = parser.add_subparsers(dest='command', required=True)
    scan = sub.add_parser('evaluate')
    scan.add_argument('snapshot')
    settle = sub.add_parser('settle')
    settle.add_argument('ticker')
    settle.add_argument('outcome', choices=['yes', 'no'])
    sub.add_parser('report')
    sub.add_parser('pause')
    sub.add_parser('resume')
    args = parser.parse_args()
    engine = PaperEngine(args.db)
    if args.command == 'evaluate':
        with open(args.snapshot, encoding='utf-8') as file:
            result = engine.evaluate(json.load(file))
    elif args.command == 'settle':
        result = {'pnl_cents': engine.settle(args.ticker, args.outcome == 'yes')}
    elif args.command in ('pause', 'resume'):
        engine.pause(args.command == 'pause')
        result = {'paused': args.command == 'pause'}
    else:
        result = engine.report()
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

