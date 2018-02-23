from decimal import Decimal
from unittest import TestCase, main
from unittest.mock import MagicMock, call

from cryptowelder.bitflyer import BitflyerWelder
from cryptowelder.context import CryptowelderContext


class TestBitflyerWelder(TestCase):

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


if __name__ == '__main__':
    main()
