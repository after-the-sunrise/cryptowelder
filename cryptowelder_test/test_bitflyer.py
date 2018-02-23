from datetime import datetime
from decimal import Decimal
from unittest import TestCase, main
from unittest.mock import MagicMock, call

from cryptowelder.bitflyer import BitflyerWelder
from cryptowelder.context import CryptowelderContext


class TestBitflyerWelder(TestCase):
    FORMAT = '%Y-%m-%d %H:%M:%S.%f %Z'

    def setUp(self):
        self.context = MagicMock()
        self.context.get_logger.return_value = MagicMock()
        self.context.get_property = lambda section, key, val: val

        self.target = BitflyerWelder(self.context)

    def test_run(self):
        self.context.is_closed = MagicMock(return_value=True)
        self.target.run()
        self.target._join()
        self.context.is_closed.assert_called_once()

    def test___loop(self):
        self.context.is_closed = MagicMock(side_effect=(False, False, True))
        self.context.get_property = MagicMock(return_value=0.1)
        self.target._process_markets = MagicMock()
        self.target._process_balance = MagicMock()
        self.target._loop()
        self.assertEqual(3, self.context.is_closed.call_count)
        self.assertEqual(2, self.context.get_property.call_count)

    def test__process_markets(self):
        self.target._process_ticker = MagicMock()
        self.target._process_position = MagicMock()
        self.target._process_transaction = MagicMock()
        self.context.requests_get = MagicMock(return_value=CryptowelderContext._parse("""
        [
          { "product_code": "BTC_JPY" },
          { "product_code": "FX_BTC_JPY" },
          { "product_code": "ETH_BTC" },
          {
            "product_code": "BTCJPY28APR2017",
            "alias": "BTCJPY_MAT1WK"
          },
          {
            "product_code": "BTCJPY05MAY2017",
            "alias": "BTCJPY_MAT2WK"
          }
        ]
        """))
        self.target._process_markets()

        products = ["BTC_JPY", "FX_BTC_JPY", "ETH_BTC", "BTCJPY28APR2017", "BTCJPY05MAY2017"]
        self.target._process_ticker.assert_has_calls([call(p) for p in products])
        self.target._process_position.assert_has_calls([call(p) for p in products])
        self.target._process_transaction.assert_has_calls([call(p) for p in products])

        # Query Failure
        self.context.requests_get = MagicMock(side_effect=Exception('test'))
        self.target._process_ticker.reset_mock()
        self.target._process_position.reset_mock()
        self.target._process_transaction.reset_mock()
        self.target._process_markets()
        self.target._process_ticker.assert_not_called()
        self.target._process_position.assert_not_called()
        self.target._process_transaction.assert_not_called()

    def test__process_ticker(self):
        self.target._fetch_special_quotation = MagicMock(return_value=None)
        self.context.save_tickers = MagicMock()
        self.context.requests_get = MagicMock(return_value=CryptowelderContext._parse("""
            {
              "product_code": "BTC_JPY",
              "timestamp": "2015-07-08T02:50:59.97",
              "tick_id": 3579,
              "best_bid": 30000,
              "best_ask": 36640,
              "best_bid_size": 0.1,
              "best_ask_size": 5,
              "total_bid_depth": 15.13,
              "total_ask_depth": 20,
              "ltp": 31690,
              "volume": 16819.26,
              "volume_by_product": 6819.26
            }
        """))

        self.target._process_ticker("FOO_BAR")

        tickers = self.context.save_tickers.call_args[0][0]
        self.assertEqual(1, len(tickers))
        self.assertEqual('bitflyer', tickers[0].tk_site)
        self.assertEqual('FOO_BAR', tickers[0].tk_code)
        self.assertEqual('2015-07-08 02:50:59.000000 UTC', tickers[0].tk_time.strftime(self.FORMAT))
        self.assertEqual(Decimal('36640'), tickers[0].tk_ask)
        self.assertEqual(Decimal('30000'), tickers[0].tk_bid)
        self.assertEqual(Decimal('31690'), tickers[0].tk_ltp)

    def test__process_ticker_matured(self):
        self.target._fetch_special_quotation = MagicMock(return_value=Decimal('1.234'))
        self.target._parse_expiry = MagicMock(return_value=datetime.fromtimestamp(1234567890))
        self.context.save_tickers = MagicMock()
        self.context.requests_get = MagicMock(side_effect=Exception('Fail'))

        self.target._process_ticker("FOO_BAR")

        tickers = self.context.save_tickers.call_args[0][0]
        self.assertEqual(1, len(tickers))
        self.assertEqual('bitflyer', tickers[0].tk_site)
        self.assertEqual('FOO_BAR', tickers[0].tk_code)
        self.assertEqual(1234567890.0, tickers[0].tk_time.timestamp())
        self.assertIsNone(tickers[0].tk_ask)
        self.assertIsNone(tickers[0].tk_bid)
        self.assertEqual(Decimal('1.234'), tickers[0].tk_ltp)

    def test__fetch_special_quotation(self):
        self.context.requests_get = MagicMock()
        url = "https://api.bitflyer.jp/v1/getboardstate?product_code=BTCJPY14APR2017"

        # Valid
        self.context.requests_get.return_value = {"data": {"special_quotation": Decimal('12.345678')}}
        self.context.requests_get.reset_mock()
        self.assertEqual(Decimal('12.345678'), self.target._fetch_special_quotation("BTCJPY14APR2017"))
        self.assertIsNone(self.target._fetch_special_quotation(""))
        self.assertIsNone(self.target._fetch_special_quotation(None))
        self.context.requests_get.assert_called_once_with(url)

        # No Price
        self.context.requests_get.return_value = {"data": {}}
        self.context.requests_get.reset_mock()
        self.assertIsNone(self.target._fetch_special_quotation("BTCJPY14APR2017"))
        self.context.requests_get.assert_called_once_with(url)

        # No Data
        self.context.requests_get.return_value = {}
        self.context.requests_get.reset_mock()
        self.assertIsNone(self.target._fetch_special_quotation("BTCJPY14APR2017"))
        self.context.requests_get.assert_called_once_with(url)

        # None
        self.context.requests_get.return_value = None
        self.context.requests_get.reset_mock()
        self.assertIsNone(self.target._fetch_special_quotation("BTCJPY14APR2017"))
        self.context.requests_get.assert_called_once_with(url)

    def test__parse_exipiry(self):
        result = self.target._parse_expiry('BTCJPY14APR2017')
        self.assertIsNotNone(result)
        self.assertEqual(2017, result.year)
        self.assertEqual(4, result.month)
        self.assertEqual(14, result.day)
        self.assertEqual(16 - 9, result.hour)
        self.assertEqual(0, result.minute)
        self.assertEqual(0, result.second)
        self.assertEqual(0, result.microsecond)
        self.assertEqual('UTC', result.tzname())

        # Invalid Formats
        self.assertIsNone(self.target._parse_expiry('BTCJPY14APR2017*'))
        self.assertIsNone(self.target._parse_expiry('BTCJPY14APR'))
        self.assertIsNone(self.target._parse_expiry('14APR2017'))
        self.assertIsNone(self.target._parse_expiry('BTCJPY**APR2017'))
        self.assertIsNone(self.target._parse_expiry('BTCJPY14***2017'))
        self.assertIsNone(self.target._parse_expiry('BTCJPY14ABC2017'))
        self.assertIsNone(self.target._parse_expiry('BTCJPY14APR****'))
        self.assertIsNone(self.target._parse_expiry(''))
        self.assertIsNone(self.target._parse_expiry(None))

    def test__parse_timestamp(self):
        result = self.target._parse_timestamp('2017-04-14T12:34:56.789')
        self.assertIsNotNone(result)
        self.assertEqual(2017, result.year)
        self.assertEqual(4, result.month)
        self.assertEqual(14, result.day)
        self.assertEqual(12, result.hour)
        self.assertEqual(34, result.minute)
        self.assertEqual(56, result.second)
        self.assertEqual(0, result.microsecond)
        self.assertEqual('UTC', result.tzname())

        # Various Formats
        self.assertEqual(result, self.target._parse_timestamp('2017-04-14T12:34:56'))
        self.assertEqual(result, self.target._parse_timestamp('2017-04-14T12:34:56Z'))
        self.assertEqual(result, self.target._parse_timestamp('2017-04-14T12:34:56.789123'))
        self.assertEqual(result, self.target._parse_timestamp('2017-04-14T12:34:56.789123Z'))

        # Invalid Formats
        self.assertIsNone(self.target._parse_timestamp('2017-04-14T12:34'))
        self.assertIsNone(self.target._parse_timestamp('2017-04-14T12:34Z'))
        self.assertIsNone(self.target._parse_timestamp(''))
        self.assertIsNone(self.target._parse_timestamp(None))

    def test__query_private(self):
        now = datetime.fromtimestamp(1234567890)
        self.context.get_now = MagicMock(return_value=now)
        self.context.get_property = MagicMock(side_effect=('foo', 'bar'))
        self.context.requests_get = MagicMock(return_value='hoge')

        self.assertEqual('hoge', self.target._query_private('/p1/p2?a=b'))
        args = self.context.requests_get.call_args[0]
        self.assertEqual('https://api.bitflyer.jp/p1/p2?a=b', args[0])
        head = self.context.requests_get.call_args[1]['headers']
        self.assertEqual(4, len(head))
        self.assertEqual('foo', head['ACCESS-KEY'])
        self.assertEqual('1234567890000', head['ACCESS-TIMESTAMP'])
        self.assertEqual('d16857465df740e78f296f5b47f3db7b490bab42f3e2369b26af48ec9ce22aa3', head['ACCESS-SIGN'])
        self.assertEqual('application/json', head['Content-Type'])

        # No Key/Secret
        self.context.get_property = MagicMock(return_value=None)
        self.assertIsNone(self.target._query_private('/p1/p2?a=b'))

    def test__process_position(self):
        now = datetime.fromtimestamp(1234567890)
        self.context.save_positions = MagicMock()
        self.context.get_now = MagicMock(return_value=now)
        self.target._query_private = MagicMock(return_value=CryptowelderContext._parse("""
            [
              {
                "product_code": "FOO_BAR",
                "side": "BUY",
                "price": 36000,
                "size": 10,
                "commission": 5,
                "swap_point_accumulate": -35,
                "require_collateral": 120000,
                "open_date": "2015-11-03T10:04:45.011",
                "leverage": 3,
                "pnl": 965
              },
              {
                "product_code": "HOGE_PIYO",
                "side": "SELL",
                "price": 12000,
                "size": 3,
                "commission": 2,
                "swap_point_accumulate": -20,
                "require_collateral": 100000,
                "open_date": "2015-11-03T10:04:45.010",
                "leverage": 10,
                "pnl": -123
              }
            ]
        """))

        self.target._process_position('FX_BTC_JPY')
        self.target._query_private.assert_called_once_with('/v1/me/getpositions?product_code=FX_BTC_JPY')

        positions = self.context.save_positions.call_args[0][0]
        self.assertEqual(1, len(positions))
        self.assertEqual('bitflyer', positions[0].ps_site)
        self.assertEqual('FX_BTC_JPY', positions[0].ps_code)
        self.assertEqual(1234567890, positions[0].ps_time.timestamp())
        self.assertEqual(Decimal('7'), positions[0].ps_inst)
        self.assertEqual(Decimal('890'), positions[0].ps_fund)

        # Not Margin Product
        self.target._query_private.reset_mock()
        self.target._process_position('BTC_JPY')
        self.target._query_private.assert_not_called()


if __name__ == '__main__':
    main()
