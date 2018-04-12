from datetime import datetime
from decimal import Decimal
from unittest import TestCase, main
from unittest.mock import MagicMock

from pytz import utc

from cryptowelder.bitmex import BitmexWelder
from cryptowelder.context import CryptowelderContext


class TestQuoinexWelder(TestCase):
    FORMAT = '%Y-%m-%d %H:%M:%S.%f %Z'

    def setUp(self):
        self.context = MagicMock()
        self.context.get_logger.return_value = MagicMock()
        self.context.get_property = lambda section, key, val: val
        self.context.parse_iso_timestamp = CryptowelderContext._parse_iso_timestamp

        self.target = BitmexWelder(self.context)

    def test_run(self):
        self.context.is_closed = MagicMock(return_value=True)
        self.target.run()
        self.target._join()
        self.context.is_closed.assert_called_once()

    def test___loop(self):
        self.context.is_closed = MagicMock(side_effect=(False, False, True))
        self.target._process_ticker = MagicMock()
        self.target._process_margin = MagicMock()
        self.target._process_transaction = MagicMock()
        self.target._loop(default_interval=0.1)
        self.assertEqual(3, self.context.is_closed.call_count)
        self.assertEqual(2, self.target._process_ticker.call_count)
        self.assertEqual(2, self.target._process_margin.call_count)
        self.assertEqual(2, self.target._process_transaction.call_count)

    def test__process_ticker(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.save_tickers = MagicMock()
        self.context.requests_get = MagicMock(return_value=CryptowelderContext._parse("""
            [
              {
                "symbol": ".BXBT",
                "state": "Unlisted",
                "referenceSymbol": ".BXBT",
                "multiplier": null,
                "lastPrice": 6789.1,
                "bidPrice": null,
                "askPrice": null,
                "timestamp": "2018-04-14T12:34:56.789Z"
              },
              {
                "symbol": ".BXBT30M",
                "state": "Unlisted",
                "referenceSymbol": ".BXBT",
                "multiplier": -100000000,
                "lastPrice": 89.1,
                "bidPrice": 89.0,
                "askPrice": 89.2,
                "timestamp": "2018-04-14T02:34:56.789Z"
              },
              {
                "symbol": "XBTM18",
                "state": "Open",
                "referenceSymbol": ".BXBT30M",
                "multiplier": -100000000,
                "lastPrice": 7890.1,
                "bidPrice": 7890.0,
                "askPrice": 7890.2,
                "timestamp": "2018-04-14T01:23:45.678Z"
              }
            ]
        """))

        self.target._process_ticker()

        tickers = self.context.save_tickers.call_args[0][0]
        self.assertEqual(2, len(tickers))

        self.assertEqual('bitmex', tickers[0].tk_site)
        self.assertEqual('2018-04-14 12:34:56.000000 UTC', tickers[0].tk_time.strftime(self.FORMAT))
        self.assertEqual('.BXBT', tickers[0].tk_code)
        self.assertEqual(None, tickers[0].tk_ask)
        self.assertEqual(None, tickers[0].tk_bid)
        self.assertEqual(Decimal('6789.1'), tickers[0].tk_ltp)

        self.assertEqual('bitmex', tickers[1].tk_site)
        self.assertEqual('2018-04-14 01:23:45.000000 UTC', tickers[1].tk_time.strftime(self.FORMAT))
        self.assertEqual('XBTM18', tickers[1].tk_code)
        self.assertEqual(Decimal('7890.2'), tickers[1].tk_ask)
        self.assertEqual(Decimal('7890.0'), tickers[1].tk_bid)
        self.assertEqual(Decimal('7890.1'), tickers[1].tk_ltp)

        # Query Blank
        self.context.save_tickers.reset_mock()
        self.context.requests_get.reset_mock()
        self.context.requests_get.return_value = {}
        self.target._process_ticker()
        self.context.save_tickers.assert_called_once()

        # Query Empty
        self.context.save_tickers.reset_mock()
        self.context.requests_get.reset_mock()
        self.context.requests_get.return_value = None
        self.target._process_ticker()
        self.context.save_tickers.assert_not_called()

        # Query Failure
        self.context.save_tickers.reset_mock()
        self.context.requests_get.reset_mock()
        self.context.requests_get.side_effect = Exception('test')
        self.target._process_ticker()
        self.context.save_tickers.assert_not_called()

    def test__query_private(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_now = MagicMock(return_value=now)
        self.context.requests_get = MagicMock(return_value='json')

        self.context.get_property = MagicMock(side_effect=['foo', 'bar'])
        self.assertEqual('json', self.target._query_private('/some_path'))
        self.assertEqual('https://www.bitmex.com/some_path', self.context.requests_get.call_args[0][0])
        headers = self.context.requests_get.call_args[1]['headers']
        self.assertEqual(4, len(headers))
        self.assertEqual('application/json', headers['Accept'])
        self.assertEqual('foo', headers['api-key'])
        self.assertEqual('1234567890123', headers['api-nonce'])
        self.assertEqual('d555d6626dd9105a68b83344011cce99'
                         '3545f1875cbe17dee770dd11114e9505', headers['api-signature'])

        # No Token
        self.context.get_property = MagicMock(return_value=None)
        self.context.requests_get.reset_mock()
        self.assertIsNone(self.target._query_private('/some_path'))
        self.context.requests_get.assert_not_called()

    def test__process_margin(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_now = MagicMock(return_value=now)
        self.context.save_balances = MagicMock()
        self.target._query_private = MagicMock(return_value=CryptowelderContext._parse("""
            [
                {
                    "currency": "FOO",
                    "walletBalance": 12345678
                },
                {
                    "currency": "XBt",
                    "walletBalance": 23456789
                }
            ]
        """))

        self.target._process_margin()

        balances = self.context.save_balances.call_args[0][0]
        self.assertEqual(1, len(balances))

        self.assertEqual('bitmex', balances[0].bc_site)
        self.assertEqual('MARGIN', balances[0].bc_acct.name)
        self.assertEqual('BTC', balances[0].bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', balances[0].bc_time.strftime(self.FORMAT))
        self.assertEqual(Decimal('0.23456789'), balances[0].bc_amnt)

        # Query Empty
        self.target._query_private.reset_mock()
        self.target._query_private.return_value = {}
        self.context.save_balances.reset_mock()
        self.target._process_margin()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_called_once()

        # Query None
        self.target._query_private.reset_mock()
        self.target._query_private.return_value = None
        self.context.save_balances.reset_mock()
        self.target._process_margin()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_called_once()

        # Query Failure
        self.target._query_private.reset_mock()
        self.target._query_private.side_effect = Exception('test')
        self.context.save_balances.reset_mock()
        self.target._process_margin()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_not_called()

    def test__process_transaction(self):
        pass  # TODO


if __name__ == '__main__':
    main()
