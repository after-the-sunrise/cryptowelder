from datetime import datetime
from decimal import Decimal
from unittest import TestCase, main
from unittest.mock import MagicMock

from pytz import utc

from cryptowelder.btcbox import BtcboxWelder
from cryptowelder.context import CryptowelderContext


class TestBtcboxWelder(TestCase):
    FORMAT = '%Y-%m-%d %H:%M:%S.%f %Z'

    def setUp(self):
        self.context = MagicMock()
        self.context.get_logger.return_value = MagicMock()
        self.context.get_property = lambda section, key, val: val
        self.context.parse_iso_timestamp = CryptowelderContext._parse_iso_timestamp

        self.target = BtcboxWelder(self.context)

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
        self.assertEqual(2 * 4, self.target._process_ticker.call_count)
        self.assertEqual(2 * 1, self.target._process_balance.call_count)

    def test__process_ticker(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_now = MagicMock(return_value=now)
        self.context.save_tickers = MagicMock()
        self.context.requests_get = MagicMock(return_value=CryptowelderContext._parse("""
            {"high":39700,"low":36300,"buy":1.879,"sell":0,"last":38800,"vol":283.954}
        """))

        self.target._process_ticker('btc')

        tickers = self.context.save_tickers.call_args[0][0]
        self.assertEqual(1, len(tickers))

        self.assertEqual('btcbox', tickers[0].tk_site)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', tickers[0].tk_time.strftime(self.FORMAT))
        self.assertEqual('btc', tickers[0].tk_code)
        self.assertEqual(Decimal('0'), tickers[0].tk_ask)
        self.assertEqual(Decimal('1.879'), tickers[0].tk_bid)
        self.assertEqual(Decimal('38800'), tickers[0].tk_ltp)

        # Query Empty
        self.context.requests_get.reset_mock()
        self.context.requests_get.return_value = {}
        self.context.save_tickers.reset_mock()
        self.target._process_ticker('btc')
        self.context.requests_get.assert_called_once()
        self.context.save_tickers.assert_called_once()

        # Query None
        self.context.requests_get.reset_mock()
        self.context.requests_get.return_value = None
        self.context.save_tickers.reset_mock()
        self.target._process_ticker('btc')
        self.context.requests_get.assert_called_once()
        self.context.save_tickers.assert_not_called()

        # Query Failure
        self.context.requests_get.reset_mock()
        self.context.requests_get.side_effect = Exception('test')
        self.context.save_tickers.reset_mock()
        self.target._process_ticker('btc')
        self.context.requests_get.assert_called_once()
        self.context.save_tickers.assert_not_called()

    def test__query_private(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_nonce = MagicMock(return_value=now)
        self.context.requests_post = MagicMock(return_value='json')

        # With Parameter
        self.context.get_property = MagicMock(side_effect=['foo', 'bar'])
        self.assertEqual('json', self.target._query_private('/some_path', parameters={'hoge': 'piyo'}))
        self.assertEqual('https://www.btcbox.co.jp/some_path', self.context.requests_post.call_args[0][0])
        headers = self.context.requests_post.call_args[1]['headers']
        self.assertEqual(2, len(headers))
        self.assertEqual('application/json', headers['Accept'])
        self.assertEqual('application/x-www-form-urlencoded', headers['Content-Type'])
        data = self.context.requests_post.call_args[1]['data']
        self.assertEqual('hoge=piyo&key=foo&nonce=1234567890123&signature=' +
                         '8f5eaca142f2c0ce12d989a28a5b0de1878b948934fc81ca4b90f4e1d6786d8b', data)

        # No Parameters
        self.context.get_property = MagicMock(side_effect=['foo', 'bar'])
        self.assertEqual('json', self.target._query_private('/some_path'))
        self.assertEqual('https://www.btcbox.co.jp/some_path', self.context.requests_post.call_args[0][0])
        headers = self.context.requests_post.call_args[1]['headers']
        self.assertEqual(2, len(headers))
        self.assertEqual('application/json', headers['Accept'])
        self.assertEqual('application/x-www-form-urlencoded', headers['Content-Type'])
        data = self.context.requests_post.call_args[1]['data']
        self.assertEqual('key=foo&nonce=1234567890123&signature=' +
                         'f415f8de8057cfc5c78cb0caa1c29db6905b1c12a026f4097f77dff34655e658', data)

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
                "uid":8,
                "nameauth":0,
                "moflag":0,
                "btc_balance":4234234,
                "btc_lock":1,
                "ltc_balance":32429.6,
                "ltc_lock":2.4,
                "eth_balance":2,
                "eth_lock":0,
                "jpy_balance":2344581.519,
                "jpy_lock":868862.481,
                "hoge_balance":8,
                "hoge_lock":9
            }
        """))

        self.target._process_balance()

        balances = self.context.save_balances.call_args[0][0]
        self.assertEqual(4, len(balances))

        map = {b.bc_unit.name: b for b in balances}
        key = sorted(map.keys())

        b = map[key[0]]
        self.assertEqual('btcbox', b.bc_site)
        self.assertEqual('CASH', b.bc_acct.name)
        self.assertEqual('BTC', b.bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', b.bc_time.strftime(self.FORMAT))
        self.assertEqual(Decimal('4234235'), b.bc_amnt)

        b = map[key[1]]
        self.assertEqual('btcbox', b.bc_site)
        self.assertEqual('CASH', b.bc_acct.name)
        self.assertEqual('ETH', b.bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', b.bc_time.strftime(self.FORMAT))
        self.assertEqual(Decimal('2'), b.bc_amnt)

        b = map[key[2]]
        self.assertEqual('btcbox', b.bc_site)
        self.assertEqual('CASH', b.bc_acct.name)
        self.assertEqual('JPY', b.bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', b.bc_time.strftime(self.FORMAT))
        self.assertEqual(Decimal('3213444.000'), b.bc_amnt)

        b = map[key[3]]
        self.assertEqual('btcbox', b.bc_site)
        self.assertEqual('CASH', b.bc_acct.name)
        self.assertEqual('LTC', b.bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', b.bc_time.strftime(self.FORMAT))
        self.assertEqual(Decimal('32432.0'), b.bc_amnt)

        # Query Empty
        self.target._query_private.reset_mock()
        self.target._query_private.return_value = {}
        self.context.save_balances.reset_mock()
        self.target._process_balance()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_called_once()

        # Query Reject
        self.target._query_private.reset_mock()
        self.target._query_private.return_value = CryptowelderContext._parse("""
            {
                "result":false
            }
        """)
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
