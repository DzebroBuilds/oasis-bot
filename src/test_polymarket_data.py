import unittest
from polymarket_data import amount,opposite_ask,scan_polymarket


class PolymarketTests(unittest.TestCase):
    def test_only_usd_finite_prices(self):
        self.assertEqual(amount({'value':'0.551','currency':'USD'}),56)
        self.assertIsNone(amount({'value':'NaN','currency':'USD'}))
        self.assertIsNone(amount({'value':'0.5','currency':'EUR'}))
        self.assertEqual(opposite_ask({'value':'0.43','currency':'USD'}),57)

    def test_public_listing_and_bbo_use_separate_namespace(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            if url.endswith('/bbo'):
                return {'marketData':{'bestAsk':{'value':'0.55','currency':'USD'},'bestBid':{'value':'0.50','currency':'USD'},'sharesTraded':'123.00'}}
            return {'markets':[{'slug':'example-game','question':'Synthetic game?', 'active':True,'closed':False,
                                'description':'Synthetic settlement rules','marketSides':[{'long':True,'description':'Team A'}]}]}
        row=scan_polymarket(fetch)[0]
        self.assertEqual(row['ticker'],'PMUS:example-game')
        self.assertEqual(row['source'],'polymarket_us')
        self.assertEqual(row['yes_ask_cents'],55)
        self.assertEqual(row['no_ask_cents'],50)
        self.assertEqual(row['volume'],123)
        self.assertEqual(row['outcome_label'],'Team A')
        self.assertTrue(row['read_only'])
        self.assertTrue(all(url.startswith('https://gateway.polymarket.us/') for url in calls))

    def test_closed_and_unknown_markets_not_assumed_open(self):
        result=scan_polymarket(lambda url:{'markets':[{'slug':'closed','active':True,'closed':True},{'slug':'unknown','active':True}]})
        self.assertEqual(result,[])

    def test_failed_book_does_not_invent_quote_or_volume(self):
        def fetch(url):
            if url.endswith('/bbo'):
                raise OSError('unavailable')
            return {'markets':[{'slug':'x','active':True,'closed':False,'lastTradePrice':'0.9'}]}
        row=scan_polymarket(fetch)[0]
        self.assertIsNone(row['yes_ask_cents'])
        self.assertIsNone(row['volume'])


if __name__=='__main__':
    unittest.main()
