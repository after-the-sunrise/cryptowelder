from datetime import datetime
from decimal import Decimal
from unittest import TestCase, main
from unittest.mock import MagicMock

from pytz import utc

from cryptowelder.context import CryptowelderContext
from cryptowelder.zaif import ZaifWelder


class TestPoloniexWelder(TestCase):
    FORMAT = '%Y-%m-%d %H:%M:%S.%f %Z'

    def setUp(self):
        self.context = MagicMock()
        self.context.get_logger.return_value = MagicMock()
        self.context.get_property = lambda section, key, val: val
        self.context.parse_iso_timestamp = CryptowelderContext._parse_iso_timestamp

        self.target = ZaifWelder(self.context)

    def test_run(self):
        self.context.is_closed = MagicMock(return_value=True)
        self.target.run()
        self.target._join()
        self.context.is_closed.assert_called_once()

    def test___loop(self):
        self.context.is_closed = MagicMock(side_effect=(False, False, True))
        self.target._process_ticker = MagicMock()
        self.target._process_balance = MagicMock()
        self.target._process_trades = MagicMock()
        self.target._loop(default_interval=0.1)
        self.assertEqual(3, self.context.is_closed.call_count)
        self.assertEqual(2 * 3, self.target._process_ticker.call_count)
        self.assertEqual(2 * 3, self.target._process_trades.call_count)
        self.assertEqual(2 * 1, self.target._process_balance.call_count)

    def test__process_ticker(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_now = MagicMock(return_value=now)
        self.context.save_tickers = MagicMock()
        self.context.requests_get = MagicMock(return_value=CryptowelderContext._parse("""
            {
              "last": 723000,
              "high": 768540,
              "low": 718000,
              "vwap": 748497.021,
              "volume": 11395.2944,
              "bid": 723000,
              "ask": 723485
            }
        """))

        self.target._process_ticker('btc_jpy')

        tickers = self.context.save_tickers.call_args[0][0]
        self.assertEqual(1, len(tickers))

        self.assertEqual('zaif', tickers[0].tk_site)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', tickers[0].tk_time.strftime(self.FORMAT))
        self.assertEqual('btc_jpy', tickers[0].tk_code)
        self.assertEqual(Decimal('723485'), tickers[0].tk_ask)
        self.assertEqual(Decimal('723000'), tickers[0].tk_bid)
        self.assertEqual(Decimal('723000'), tickers[0].tk_ltp)

        # Query None
        self.context.requests_get.reset_mock()
        self.context.requests_get.return_value = None
        self.context.save_tickers.reset_mock()
        self.target._process_ticker('btc_jpy')
        self.context.requests_get.assert_called_once()
        self.context.save_tickers.assert_not_called()

        # Query Failure
        self.context.requests_get.reset_mock()
        self.context.requests_get.side_effect = Exception('test')
        self.context.save_tickers.reset_mock()
        self.target._process_ticker('btc_jpy')
        self.context.requests_get.assert_called_once()
        self.context.save_tickers.assert_not_called()

    def test__process_balance(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_now = MagicMock(return_value=now)
        self.context.save_balances = MagicMock()
        self.target._query_private = MagicMock(return_value=CryptowelderContext._parse("""
            {
                "success": 1,
                "return": {
                    "funds": {
                        "jpy": 15320,
                        "btc": 1.389,
                        "xem": 100.2,
                        "mona": 2600,
                        "pepecash": 0.1
                    },
                    "deposit": {
                        "jpy": 20440,
                        "btc": 1.479,
                        "xem": 100.2,
                        "mona": 3200,
                        "pepecash": 0.1
                    },
                    "rights": {
                        "info": 1,
                        "trade": 1,
                        "withdraw": 0,
                        "personal_info": 0
                    },
                    "open_orders": 3,
                    "server_time": 1401950833
                }
            }
        """))

        self.target._process_balance()

        balances = self.context.save_balances.call_args[0][0]
        self.assertEqual(2, len(balances))

        self.assertEqual('zaif', balances[0].bc_site)
        self.assertEqual('CASH', balances[0].bc_acct.name)
        self.assertEqual('JPY', balances[0].bc_unit.name)
        self.assertEqual('2014-06-05 06:47:13.000000 UTC', balances[0].bc_time.strftime(self.FORMAT))
        self.assertEqual(Decimal('15320'), balances[0].bc_amnt)

        self.assertEqual('zaif', balances[1].bc_site)
        self.assertEqual('CASH', balances[1].bc_acct.name)
        self.assertEqual('BTC', balances[1].bc_unit.name)
        self.assertEqual('2014-06-05 06:47:13.000000 UTC', balances[1].bc_time.strftime(self.FORMAT))
        self.assertEqual(Decimal('1.389'), balances[1].bc_amnt)

        # Query Reject
        self.target._query_private.reset_mock()
        self.target._query_private.return_value = '{"success": 0}'
        self.context.save_balances.reset_mock()
        self.target._process_balance()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_not_called()

        # Query None
        self.target._query_private.reset_mock()
        self.target._query_private.return_value = None
        self.context.save_balances.reset_mock()
        self.target._process_balance()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_not_called()

        # Query Failure
        self.target._query_private.reset_mock()
        self.target._query_private.side_effect = Exception('test')
        self.context.save_balances.reset_mock()
        self.target._process_balance()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_not_called()


if __name__ == '__main__':
    main()
