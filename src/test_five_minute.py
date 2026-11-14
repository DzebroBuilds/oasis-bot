import unittest
from datetime import datetime,timezone
from five_minute import discover,window


class FiveMinuteTests(unittest.TestCase):
    def fixture(self):
        return {'slug':'btc-updown-5m-2026-11-14-1200z','title':'BTC Up or Down 5m',
                'markets':[{'slug':'btc-round-up','closed':False}]}

    def test_only_exact_five_minute_btc_rounds(self):
        good=self.fixture();wrong={**self.fixture(),'slug':'btc-updown-15m-2026-11-14-1200z'}
        result=discover(lambda url:{'events':[wrong,good]},datetime(2026,11,14,12,2,tzinfo=timezone.utc))
        self.assertEqual(result['current']['slug'],'btc-round-up')
        self.assertEqual(result['current']['time_source'],'event_slug_schedule')

    def test_expired_round_not_current(self):
        result=discover(lambda url:{'events':[self.fixture()]},datetime(2026,11,14,12,5,tzinfo=timezone.utc))
        self.assertIsNone(result['current'])

    def test_provider_window_wrong_duration_rejected(self):
        market={'assetPriceTerms':{'windowStart':'2026-11-14T12:00:00Z','windowEnd':'2026-11-14T12:15:00Z'}}
        self.assertIsNone(window(self.fixture(),market))

    def test_future_round_is_upcoming(self):
        result=discover(lambda url:{'events':[self.fixture()]},datetime(2026,11,14,11,59,tzinfo=timezone.utc))
        self.assertIsNone(result['current'])
        self.assertEqual(len(result['upcoming']),1)


if __name__=='__main__':
    unittest.main()
