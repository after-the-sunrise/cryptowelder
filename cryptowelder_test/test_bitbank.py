from datetime import datetime
from unittest import TestCase, main
from unittest.mock import MagicMock

from pytz import utc

from cryptowelder.bitbank import BitbankWelder
from cryptowelder.context import CryptowelderContext


class TestBitbankWelder(TestCase):
    FORMAT = '%Y-%m-%d %H:%M:%S.%f %Z'

    def setUp(self):
        self.context = MagicMock()
        self.context.get_logger.return_value = MagicMock()
        self.context.get_property = lambda section, key, val: val
        self.context.parse_iso_timestamp = CryptowelderContext._parse_iso_timestamp

        self.target = BitbankWelder(self.context)

    def test_run(self):
        self.context.is_closed = MagicMock(return_value=True)
        self.target.run()
        self.target._join()
        self.context.is_closed.assert_called_once()

    def test___loop(self):
        self.context.is_closed = MagicMock(side_effect=(False, False, True))
        self.target._process_ticker = MagicMock()
        self.target._process_balance = MagicMock()
        self.target._process_transaction = MagicMock()
        self.target._loop(default_interval=0.1)
        self.assertEqual(3, self.context.is_closed.call_count)
        self.assertEqual(2 * 1, self.target._process_balance.call_count)
        self.assertEqual(2 * 5, self.target._process_ticker.call_count)
        self.assertEqual(2 * 5, self.target._process_transaction.call_count)

    def test__process_ticker(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_now = MagicMock(return_value=now)
        self.context.save_tickers = MagicMock()
        self.context.requests_get = MagicMock(return_value=CryptowelderContext._parse("""
            {
              "success": 1,
              "data": {
                "sell": "800002",
                "buy": "800001",
                "high": "890123",
                "low": "789123",
                "last": "800000",
                "vol": "1234.5678",
                "timestamp": 1234567890123
              }
            }
        """))

        self.target._process_ticker('btc_jpy')

        tickers = self.context.save_tickers.call_args[0][0]
        self.assertEqual(1, len(tickers))

        self.assertEqual('bitbank', tickers[0].tk_site)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', tickers[0].tk_time.strftime(self.FORMAT))
        self.assertEqual('btc_jpy', tickers[0].tk_code)
        self.assertEqual('800002', tickers[0].tk_ask)
        self.assertEqual('800001', tickers[0].tk_bid)
        self.assertEqual('800000', tickers[0].tk_ltp)

        # Query Reject
        self.context.requests_get = MagicMock(return_value=CryptowelderContext._parse("""
            {
              "success": 0,
              "data": {
                "code": 99999
              }
            }
        """))
        self.context.save_tickers.reset_mock()
        self.target._process_ticker('btc_jpy')
        self.context.requests_get.assert_called_once()
        self.context.save_tickers.assert_not_called()

        # Query Empty
        self.context.requests_get.reset_mock()
        self.context.requests_get.return_value = {}
        self.context.save_tickers.reset_mock()
        self.target._process_ticker('btc_jpy')
        self.context.requests_get.assert_called_once()
        self.context.save_tickers.assert_called_once()

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

    def test__query_private(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_now = MagicMock(return_value=now)
        self.context.requests_get = MagicMock(return_value='json')

        self.context.get_property = MagicMock(side_effect=['foo', 'bar'])
        self.assertEqual('json', self.target._query_private('/some_path'))
        self.assertEqual('https://api.bitbank.cc/some_path', self.context.requests_get.call_args[0][0])
        headers = self.context.requests_get.call_args[1]['headers']
        self.assertEqual(4, len(headers))
        self.assertEqual('foo', headers['ACCESS-KEY'])
        self.assertEqual('1234567890123', headers['ACCESS-NONCE'])
        self.assertEqual('2488beaac6aa9eb4d3b7c698262aee52c'
                         '69ca743d7bb967189b16e56d471d1bd', headers['ACCESS-SIGNATURE'])
        self.assertEqual('application/json', headers['Accept'])

        # No Token
        self.context.get_property = MagicMock(return_value=None)
        self.context.requests_get.reset_mock()
        self.assertIsNone(self.target._query_private('some_path'))
        self.context.requests_get.assert_not_called()

    def test__process_balance(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_now = MagicMock(return_value=now)
        self.context.save_balances = MagicMock()
        self.target._query_private = MagicMock(return_value=CryptowelderContext._parse("""
            {
              "success": 1,
              "data": {
                "assets": [
                  {
                    "asset": "jpy",
                    "amount_precision": 4,
                    "onhand_amount": "30000.0000",
                    "locked_amount": "10000.0000",
                    "free_amount": "20000.0000",
                    "stop_deposit": false,
                    "stop_withdrawal": false,
                    "withdrawal_fee": {
                      "threshold": "30000.0000",
                      "under": "540.0000",
                      "over": "756.0000"
                    }
                  },
                  {
                    "asset": "xrp",
                    "amount_precision": 6,
                    "onhand_amount": "0.000003",
                    "locked_amount": "0.000002",
                    "free_amount": "0.000001",
                    "stop_deposit": false,
                    "stop_withdrawal": false,
                    "withdrawal_fee": "0.150000"
                  },
                  {
                    "asset": "btc",
                    "amount_precision": 8,
                    "onhand_amount": "0.30000000",
                    "locked_amount": "0.20000000",
                    "free_amount": "0.10000000",
                    "stop_deposit": false,
                    "stop_withdrawal": false,
                    "withdrawal_fee": "0.00100000"
                  }
                ]
              }
            }
        """))

        self.target._process_balance()

        balances = self.context.save_balances.call_args[0][0]
        self.assertEqual(2, len(balances))

        self.assertEqual('bitbank', balances[0].bc_site)
        self.assertEqual('CASH', balances[0].bc_acct.name)
        self.assertEqual('JPY', balances[0].bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', balances[0].bc_time.strftime(self.FORMAT))
        self.assertEqual('30000.0000', balances[0].bc_amnt)

        self.assertEqual('bitbank', balances[1].bc_site)
        self.assertEqual('CASH', balances[1].bc_acct.name)
        self.assertEqual('BTC', balances[1].bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', balances[1].bc_time.strftime(self.FORMAT))
        self.assertEqual('0.30000000', balances[1].bc_amnt)

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

    def test__process_transaction(self):
        # TODO : API not available.
        self.target._process_transaction('btc_jpy')


if __name__ == '__main__':
    main()
