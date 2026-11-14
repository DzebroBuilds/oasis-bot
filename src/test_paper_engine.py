import copy
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from paper_engine import PaperEngine


NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)


def snapshot(ticker='SYNTHETIC-A'):
    return dict(ticker=ticker, event='SYNTHETIC', rules='Synthetic yes/no settlement rule',
                model_version='fixture-v1', probability_yes=.8, uncertainty=.05,
                yes_ask_cents=50, no_ask_cents=55, yes_ask_size=100, no_ask_size=100,
                fee_bound_cents=2, quoted_at=NOW.isoformat(),
                closes_at=(NOW+timedelta(days=1)).isoformat(),
                evidence=[dict(url='https://example.com/synthetic', summary='Synthetic test evidence', observed_at=NOW.isoformat())])


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name)/'paper.db')
        self.engine = PaperEngine(self.path, daily_cap=1500)

    def tearDown(self):
        self.engine.db.close()
        self.temp.cleanup()

    def test_restart_preserves_daily_cap_and_duplicate(self):
        first = self.engine.evaluate(snapshot(), NOW)
        self.assertTrue(first['accepted'])
        self.engine.db.close()
        self.engine = PaperEngine(self.path, daily_cap=1500)
        self.assertEqual(self.engine.evaluate(snapshot(), NOW)['reason'], 'duplicate_market')
        self.assertFalse(self.engine.evaluate(snapshot('B'), NOW)['accepted'])

    def test_no_side_uses_no_quote(self):
        s = snapshot(); s['probability_yes'] = .1
        order = self.engine.evaluate(s, NOW)['order']
        self.assertEqual((order['side'], order['price_cents']), ('no', 55))

    def test_rejects_invalid_or_stale_inputs(self):
        for key, value in [('probability_yes', True), ('uncertainty', -1), ('evidence', []),
                           ('fee_bound_cents', None), ('quoted_at', 'bad'), ('yes_ask_size', 0)]:
            with self.subTest(key=key):
                s = snapshot(); s[key] = value
                self.assertFalse(self.engine.evaluate(s, NOW)['accepted'])
        s = snapshot(); s['quoted_at'] = (NOW-timedelta(seconds=61)).isoformat()
        self.assertFalse(self.engine.evaluate(s, NOW)['accepted'])
        s = snapshot(); s['evidence'][0]['observed_at'] = (NOW+timedelta(seconds=1)).isoformat()
        self.assertFalse(self.engine.evaluate(s, NOW)['accepted'])

    def test_costs_and_uncertainty_remove_edge(self):
        s = snapshot(); s['probability_yes'] = .6; s['uncertainty'] = .1
        self.assertFalse(self.engine.evaluate(s, NOW)['accepted'])

    def test_pause_persists(self):
        self.engine.pause(True)
        self.assertEqual(self.engine.evaluate(snapshot(), NOW)['reason'], 'paused')
        self.engine.pause(False)
        self.assertTrue(self.engine.evaluate(snapshot(), NOW)['accepted'])

    def test_event_limit_across_days(self):
        self.engine.db.close()
        self.engine = PaperEngine(self.path, daily_cap=15000, event_cap=1500)
        self.assertTrue(self.engine.evaluate(snapshot(), NOW)['accepted'])
        tomorrow = NOW+timedelta(days=1)
        s = snapshot('B'); s['quoted_at'] = tomorrow.isoformat()
        s['closes_at'] = (tomorrow+timedelta(days=1)).isoformat()
        s['evidence'][0]['observed_at'] = tomorrow.isoformat()
        self.assertFalse(self.engine.evaluate(s, tomorrow)['accepted'])

    def test_settlement_idempotence_and_metrics(self):
        order = self.engine.evaluate(snapshot(), NOW)['order']
        expected = 100*order['count']-order['cost_cents']
        self.assertEqual(self.engine.settle('SYNTHETIC-A', True), expected)
        self.assertEqual(self.engine.settle('SYNTHETIC-A', True), expected)
        with self.assertRaises(ValueError):
            self.engine.settle('SYNTHETIC-A', False)
        self.assertAlmostEqual(self.engine.report()['brier_score'], .04)
        self.assertEqual(self.engine.report()['pnl_cents'], expected)

    def test_concurrent_writers_cannot_exceed_budget(self):
        def submit(ticker):
            engine = PaperEngine(self.path, daily_cap=1500)
            try:
                return engine.evaluate(snapshot(ticker), NOW)['accepted']
            finally:
                engine.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            accepted = list(pool.map(submit, ['A', 'B']))
        self.assertEqual(sum(accepted), 1)
        self.assertEqual(self.engine.report()['decisions'], 2)


if __name__ == '__main__':
    unittest.main()

