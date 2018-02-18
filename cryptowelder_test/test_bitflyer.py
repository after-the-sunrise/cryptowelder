from decimal import Decimal
from unittest import TestCase, main, mock

from cryptowelder.bitflyer import BitflyerWelder


class TestBitflyerWelder(TestCase):

    def setUp(self):
        self.context = mock.MagicMock()
        self.context.get_logger.return_value = mock.MagicMock()
        self.context.get_property = lambda section, key, val: val

        self.target = BitflyerWelder(self.context)

    def test_run(self):
        self.context.is_closed = mock.MagicMock(return_value=True)
        self.target.run()
        self.target._join()
        self.context.is_closed.assert_called_once()

    def test__fetch_special_quotation(self):
        self.context.requests_get = mock.MagicMock()
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
