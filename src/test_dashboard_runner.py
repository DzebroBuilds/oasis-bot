import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from dashboard_runner import cents, normalize, restore, run, scan_markets, apply_signals, grounded_research, dump
from paper_engine import PaperEngine


def event_payload():
    return {'events':[{'category':'Economics','markets':[{
        'ticker':'TEST-MARKET','event_ticker':'TEST','title':'Synthetic test market',
        'yes_ask_dollars':'0.451','no_ask_dollars':'0.56','volume_fp':'100.5',
        'yes_ask_size_fp':'8.9','rules_primary':'Synthetic test rules','status':'active','close_time':'2099-01-01T00:00:00Z'}]}], 'cursor':''}


class DashboardTests(unittest.TestCase):
    def setup_state(self,directory):
        path=Path(directory)
        (path/'ledger.json').write_text(json.dumps({'version':1,'paused':False,'positions':[],'decisions':[]}))
        (path/'paper-signals.json').write_text('[]')
        return path

    def test_subcent_ask_rounds_up_and_invalid_is_missing(self):
        self.assertEqual(cents('0.451'),46)
        for value in ('NaN','Infinity',None,'0','1'):
            self.assertIsNone(cents(value))

    def test_scan_is_bounded_and_deduplicates(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            result=event_payload(); result['cursor']='more'
            return result
        self.assertEqual(len(scan_markets(fetch)),1)
        self.assertEqual(len(calls),3)

    def test_export_is_paper_and_rejects_without_probability(self):
        with tempfile.TemporaryDirectory() as directory:
            path=self.setup_state(directory)
            feed=run(path,fetch=lambda url:event_payload())
            self.assertEqual(feed['mode'],'paper')
            self.assertEqual(feed['health']['status'],'ok')
            self.assertEqual(feed['stats']['open_positions'],0)
            self.assertEqual(feed['decisions'][0]['reason'],'invalid_probability')
            self.assertFalse(feed['entries_enabled'])
            self.assertEqual(json.loads((path/'dashboard.json').read_text())['schema_version'],1)

    def test_pause_persists_and_no_network_called(self):
        with tempfile.TemporaryDirectory() as directory:
            path=self.setup_state(directory)
            def fail(url):
                self.fail('Paused worker made network request')
            feed=run(path,'pause',fetch=fail)
            self.assertTrue(feed['paused'])
            self.assertTrue(run(path,fetch=fail)['paused'])

    def test_outage_retains_previous_market_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            path=self.setup_state(directory)
            first=run(path,fetch=lambda url:event_payload())
            def fail(url):
                raise OSError('Provider secret must not be published')
            second=run(path,fetch=fail)
            self.assertEqual(second['markets'],first['markets'])
            self.assertEqual(second['health']['market_data_at'],first['health']['market_data_at'])
            self.assertEqual(second['health']['status'],'degraded')
            self.assertNotIn('Provider secret',json.dumps(second))

    def test_missing_ledger_fails_instead_of_resetting(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                run(directory)

    def test_corrupt_budget_state_is_rejected(self):
        engine=PaperEngine(':memory:')
        try:
            with self.assertRaises(ValueError):
                restore(engine,{'version':1,'paused':False,'positions':[['X','E','2026-11-14','yes',1,-50,.8,'open',None,None]],'decisions':[]})
            self.assertEqual(engine.report()['open_positions'],0)
        finally:
            engine.db.close()

    def test_signal_uses_exchange_book_not_submitted_price(self):
        engine=PaperEngine(':memory:')
        now=datetime.now(timezone.utc).isoformat()
        signal={'ticker':'TEST-MARKET','model_version':'test-only','probability_yes':.9,'uncertainty':.1,
                'fee_bound_cents':2,'market_price':1,'evidence':[{'url':'https://example.com/test','summary':'Synthetic evidence','observed_at':now}]}
        def fetch(url):
            if url.endswith('/orderbook'):
                return {'orderbook_fp':{'yes_dollars':[['0.40','10.00']],'no_dollars':[['0.50','5.00']]}}
            return {'market':event_payload()['events'][0]['markets'][0]}
        try:
            apply_signals(engine,[signal],fetch)
            position=engine.db.execute('SELECT side,count,cost FROM positions').fetchone()
            self.assertEqual(position,('yes',5,260))
            saved=json.loads(json.dumps(dump(engine)))
            other=PaperEngine(':memory:')
            try:
                restore(other,saved)
                self.assertEqual(other.report()['open_positions'],1)
                apply_signals(other,[signal],fetch)
                self.assertEqual(other.report()['open_positions'],1)
            finally:
                other.db.close()
        finally:
            engine.db.close()

    def test_research_rejects_uncited_provider_output(self):
        result=grounded_research({'title':'test','rules':'test'},'synthetic-key',
            lambda *args:{'steps':[{'type':'model_output','content':[{'type':'text','text':'Unsupported claim'}]}]})
        self.assertEqual(result['status'],'ungrounded')
        self.assertNotIn('text',result)


if __name__=='__main__':
    unittest.main()
