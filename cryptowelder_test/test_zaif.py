from datetime import datetime
from decimal import Decimal
from unittest import TestCase, main
from unittest.mock import MagicMock

from pytz import utc

from cryptowelder.context import CryptowelderContext, TransactionType, AccountType
from cryptowelder.zaif import ZaifWelder


class TestZaifWelder(TestCase):
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
        self.context.get_nonce = MagicMock(return_value=now)
        self.context.requests_post = MagicMock(return_value='json')

        # With Parameter
        self.context.get_property = MagicMock(side_effect=['foo', 'bar'])
        self.assertEqual('json', self.target._query_private('some_path', parameters={'hoge': 'piyo'}))
        self.assertEqual('https://api.zaif.jp/tapi', self.context.requests_post.call_args[0][0])
        headers = self.context.requests_post.call_args[1]['headers']
        self.assertEqual(2, len(headers))
        self.assertEqual('foo', headers['key'])
        self.assertEqual('841e8622e8e5e5b3fdc7d555861294dc7d4e3854d59207e62fc7ef8cd511642e' +
                         '1a6665cecd683d3df6fa980a5f527651592b2be0240ffe04f73aa025d84d2e18', headers['sign'])
        data = self.context.requests_post.call_args[1]['data']
        self.assertEqual('nonce=1234567890.123&method=some_path&hoge=piyo', data)

        # No Parameters
        self.context.get_property = MagicMock(side_effect=['foo', 'bar'])
        self.assertEqual('json', self.target._query_private('some_path'))
        self.assertEqual('https://api.zaif.jp/tapi', self.context.requests_post.call_args[0][0])
        headers = self.context.requests_post.call_args[1]['headers']
        self.assertEqual(2, len(headers))
        self.assertEqual('foo', headers['key'])
        self.assertEqual('930b53d0a387f72714a2bc841ea2bc44d2beaeca3678f0a87a3ca7bfa140ac25' +
                         'ab01418a6bdaa5a76d328461dc95fce8a12f019d6a734239d30668cc2686cbc2', headers['sign'])
        data = self.context.requests_post.call_args[1]['data']
        self.assertEqual('nonce=1234567890.123&method=some_path', data)

        # No Token
        self.context.get_property = MagicMock(return_value=None)
        self.context.requests_post.reset_mock()
        self.assertIsNone(self.target._query_private('some_path'))
        self.context.requests_post.assert_not_called()

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

    def test__process_trade(self):
        side_effects = [
            CryptowelderContext._parse("""
                {
                    "success": 1,
                    "return": {
                        "182": {
                            "currency_pair": "btc_jpy",
                            "action": "bid",
                            "amount": 0.03,
                            "price": 56000,
                            "fee": 0,
                            "your_action": "ask",
                            "bonus": 1.6,
                            "timestamp": 1402018713,
                            "comment" : "demo"
                        }
                    }
                }
            """),
            CryptowelderContext._parse("""
                {
                    "success": 1,
                    "return": {
                        "180": {
                            "currency_pair": "btc_jpy",
                            "action": "ask",
                            "amount": 0.04,
                            "price": 56001,
                            "fee": 3.2,
                            "your_action": "bid",
                            "bonus": 0,
                            "timestamp": 1402018710,
                            "comment" : "test"
                        }
                    }
                }
            """),
            CryptowelderContext._parse("""
                {
                    "success": 1
                }
            """)
        ]

        # Query 3 times
        self.target._query_private = MagicMock(side_effect=side_effects)
        self.context.save_transactions = MagicMock(return_value=[None])
        self.target._process_trades('foo_bar')
        self.target._query_private.assert_called()
        self.context.save_transactions.assert_called()

        calls = self.context.save_transactions.call_args_list
        self.assertEqual(2, len(calls))

        values = list(calls[0][0][0])
        self.assertEqual(1, len(values))
        self.assertEqual('zaif', values[0].tx_site)
        self.assertEqual('foo_bar', values[0].tx_code)
        self.assertEqual(TransactionType.TRADE, values[0].tx_type)
        self.assertEqual(AccountType.CASH, values[0].tx_acct)
        self.assertEqual('182', values[0].tx_oid)
        self.assertEqual('182', values[0].tx_eid)
        self.assertEqual('2014-06-06 01:38:33.000000 UTC', values[0].tx_time.strftime(self.FORMAT))
        self.assertEqual(Decimal('-0.03'), values[0].tx_inst)
        self.assertEqual(Decimal('1681.60'), values[0].tx_fund)

        values = list(calls[1][0][0])
        self.assertEqual(1, len(values))
        self.assertEqual('zaif', values[0].tx_site)
        self.assertEqual('foo_bar', values[0].tx_code)
        self.assertEqual(TransactionType.TRADE, values[0].tx_type)
        self.assertEqual(AccountType.CASH, values[0].tx_acct)
        self.assertEqual('180', values[0].tx_oid)
        self.assertEqual('180', values[0].tx_eid)
        self.assertEqual('2014-06-06 01:38:30.000000 UTC', values[0].tx_time.strftime(self.FORMAT))
        self.assertEqual(Decimal('0.04'), values[0].tx_inst)
        self.assertEqual(Decimal('-2243.24'), values[0].tx_fund)

        # Nothing saved
        self.target._query_private = MagicMock(side_effect=side_effects)
        self.context.save_transactions = MagicMock(return_value=None)
        self.target._process_trades('foo_bar')
        self.target._query_private.assert_called_once()
        self.context.save_transactions.assert_called_once()

        # Empty Trades
        self.target._query_private = MagicMock(return_value=CryptowelderContext._parse("""
            {
                "success": 1,
                "return": {
                }
            }
        """))
        self.context.save_transactions = MagicMock(return_value=[None])
        self.target._process_trades('foo_bar')
        self.target._query_private.assert_called_once()
        self.context.save_transactions.assert_not_called()

        # Failure Response
        self.target._query_private = MagicMock(return_value=CryptowelderContext._parse("""
            {
                "success": 0,
                "return": {
                }
            }
        """))
        self.context.save_transactions = MagicMock(return_value=[None])
        self.target._process_trades('foo_bar')
        self.target._query_private.assert_called_once()
        self.context.save_transactions.assert_not_called()

        # Exception Response
        self.target._query_private = MagicMock(side_effect=Exception('test'))
        self.context.save_transactions = MagicMock(return_value=[None])
        self.target._process_trades('foo_bar')
        self.target._query_private.assert_called_once()
        self.context.save_transactions.assert_not_called()


if __name__ == '__main__':
    main()
