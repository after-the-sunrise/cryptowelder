from datetime import datetime
from decimal import Decimal
from unittest import TestCase, main
from unittest.mock import MagicMock

from pytz import utc

from cryptowelder.context import CryptowelderContext
from cryptowelder.oanda import OandaWelder


class TestBtcboxWelder(TestCase):
    FORMAT = '%Y-%m-%d %H:%M:%S.%f %Z'

    def setUp(self):
        self.context = MagicMock()
        self.context.get_logger.return_value = MagicMock()
        self.context.get_property = lambda section, key, val: val
        self.context.parse_iso_timestamp = CryptowelderContext._parse_iso_timestamp

        self.target = OandaWelder(self.context)

    def test_run(self):
        self.context.is_closed = MagicMock(return_value=True)
        self.target.run()
        self.target._join()
        self.context.is_closed.assert_called_once()

    def test___loop(self):
        self.context.is_closed = MagicMock(side_effect=(False, False, True))
        self.target._process_ticker = MagicMock()
        self.target._process_balance = MagicMock()
        self.target._loop(default_interval=0.1)
        self.assertEqual(3, self.context.is_closed.call_count)
        self.assertEqual(2, self.target._process_ticker.call_count)
        self.assertEqual(2, self.target._process_balance.call_count)

    def test__process_ticker(self):
        self.context.save_tickers = MagicMock()
        self.context.requests_get = MagicMock(return_value=CryptowelderContext._parse("""
            {
              "prices": [
                {
                  "instrument":"USD_JPY",
                  "time":"2013-06-21T17:49:02.475381Z",
                  "bid":97.618,
                  "ask":97.633
                },
                {
                  "instrument":"EUR_CAD",
                  "time":"2013-06-21T17:51:38.063560Z",
                  "bid":1.37489,
                  "ask":1.37517,
                  "status": "halted"
                }
                ]
            }
        """))

        self.context.get_property = MagicMock(side_effect=['foo', 'bar'])
        self.target._process_ticker()

        tickers = self.context.save_tickers.call_args[0][0]
        self.assertEqual(2, len(tickers))

        self.assertEqual('oanda', tickers[0].tk_site)
        self.assertEqual('2013-06-21 17:49:02.000000 UTC', tickers[0].tk_time.strftime(self.FORMAT))
        self.assertEqual('USD_JPY', tickers[0].tk_code)
        self.assertEqual(Decimal('97.633'), tickers[0].tk_ask)
        self.assertEqual(Decimal('97.618'), tickers[0].tk_bid)
        self.assertEqual(None, tickers[0].tk_ltp)

        self.assertEqual('oanda', tickers[1].tk_site)
        self.assertEqual('2013-06-21 17:51:38.000000 UTC', tickers[1].tk_time.strftime(self.FORMAT))
        self.assertEqual('EUR_CAD', tickers[1].tk_code)
        self.assertEqual(Decimal('1.37517'), tickers[1].tk_ask)
        self.assertEqual(Decimal('1.37489'), tickers[1].tk_bid)
        self.assertEqual(None, tickers[0].tk_ltp)

        # Query Empty
        self.context.get_property = MagicMock(side_effect=['foo', 'bar'])
        self.context.requests_get.reset_mock()
        self.context.requests_get.return_value = {}
        self.context.save_tickers.reset_mock()
        self.target._process_ticker()
        self.context.requests_get.assert_called_once()
        self.context.save_tickers.assert_called_once()

        # Query None
        self.context.get_property = MagicMock(side_effect=['foo', 'bar'])
        self.context.requests_get.reset_mock()
        self.context.requests_get.return_value = None
        self.context.save_tickers.reset_mock()
        self.target._process_ticker()
        self.context.requests_get.assert_called_once()
        self.context.save_tickers.assert_called_once()

        # Query Failure
        self.context.get_property = MagicMock(side_effect=['foo', 'bar'])
        self.context.requests_get.reset_mock()
        self.context.requests_get.side_effect = Exception('test')
        self.context.save_tickers.reset_mock()
        self.target._process_ticker()
        self.context.requests_get.assert_called_once()
        self.context.save_tickers.assert_not_called()

        # No Token
        self.context.get_property = MagicMock(return_value=None)
        self.context.requests_get.reset_mock()
        self.context.requests_get.side_effect = Exception('test')
        self.context.save_tickers.reset_mock()
        self.target._process_ticker()
        self.context.requests_get.assert_not_called()
        self.context.save_tickers.assert_not_called()

    def test__process_balance(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_now = MagicMock(return_value=now)
        self.context.get_property = MagicMock(return_value='hoge')
        self.context.save_balances = MagicMock()
        self.context.requests_get = MagicMock(side_effect=[CryptowelderContext._parse("""
            {
              "accounts": [
                  {
                    "accountId" : 8954947,
                    "accountName" : "Primary",
                    "accountCurrency" : "USD",
                    "marginRate" : 0.05
                  },
                  {
                    "accountId" : 8954950,
                    "accountName" : "SweetHome",
                    "accountCurrency" : "CAD",
                    "marginRate" : 0.02
                  }
              ]
            }
        """), CryptowelderContext._parse("""
            {
              "accountId" : 8954947,
              "accountName" : "Primary",
              "balance" : 100000,
              "unrealizedPl" : 2,
              "realizedPl" : 4,
              "marginUsed" : 8,
              "marginAvail" : 100001,
              "openTrades" : 16,
              "openOrders" : 32,
              "marginRate" : 0.05,
              "accountCurrency" : "USD"
            }
        """), None])

        self.target._process_balance()

        balances = self.context.save_balances.call_args[0][0]
        self.assertEqual(1, len(balances))

        b = balances[0]
        self.assertEqual('oanda', b.bc_site)
        self.assertEqual('MARGIN', b.bc_acct.name)
        self.assertEqual('USD', b.bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', b.bc_time.strftime(self.FORMAT))
        self.assertEqual(Decimal('100000'), b.bc_amnt)

        # Query Empty
        self.context.requests_get.reset_mock()
        self.context.requests_get.side_effect = [{}, {}]
        self.context.save_balances.reset_mock()
        self.target._process_balance()
        self.context.requests_get.assert_called_once()
        self.context.save_balances.assert_called_once()

        # Query None
        self.context.requests_get.reset_mock()
        self.context.requests_get.return_value = None
        self.context.save_balances.reset_mock()
        self.target._process_balance()
        self.context.requests_get.assert_called_once()
        self.context.save_balances.assert_called_once()

        # Query Failure
        self.context.requests_get.reset_mock()
        self.context.requests_get.side_effect = Exception('test')
        self.context.save_balances.reset_mock()
        self.target._process_balance()
        self.context.requests_get.assert_called_once()
        self.context.save_balances.assert_not_called()

        # No Token
        self.context.get_property = MagicMock(return_value=None)
        self.context.requests_get.reset_mock()
        self.context.requests_get.side_effect = Exception('test')
        self.context.save_balances.reset_mock()
        self.target._process_balance()
        self.context.requests_get.assert_not_called()
        self.context.save_balances.assert_not_called()


if __name__ == '__main__':
    main()
