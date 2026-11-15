import unittest
from security import paper_mode, validated_pick

class SecurityTests(unittest.TestCase):
    def test_live_fails_closed(self):
        for value in (None, '', 'true', 'typo'):
            self.assertTrue(paper_mode(value))
        with self.assertRaises(ValueError):
            paper_mode('false')

    def test_model_cannot_choose_price_or_ticker(self):
        market={'ticker':'REAL','yes_ask':40,'no_ask':62}
        result=validated_pick({'skip':False,'side':'NO','confidence':95,'market_price':1,'ticker':'EVIL'},market)
        self.assertEqual(result['market_price'],62)
        self.assertEqual(result['ticker'],'REAL')

    def test_malformed_model_output_skipped(self):
        market={'ticker':'REAL','yes_ask':40}
        for value in ([],None,{'skip':False,'side':'BUY','confidence':99},{'skip':False,'side':'YES','confidence':float('nan')},{'skip':False,'side':'YES','confidence':True}):
            self.assertTrue(validated_pick(value,market)['skip'])
        self.assertTrue(validated_pick({'skip':False,'side':'YES','confidence':99},{'ticker':'REAL','yes_ask':0})['skip'])

if __name__=='__main__':unittest.main()
