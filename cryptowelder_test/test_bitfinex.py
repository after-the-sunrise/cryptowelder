from unittest import TestCase, main
from unittest.mock import MagicMock

from cryptowelder.bitfinex import BitfinexWelder
from cryptowelder.context import CryptowelderContext


class TestBitfinexWelder(TestCase):
    FORMAT = '%Y-%m-%d %H:%M:%S.%f %Z'

    def setUp(self):
        self.context = MagicMock()
        self.context.get_logger.return_value = MagicMock()
        self.context.get_property = lambda section, key, val: val
        self.context.parse_iso_timestamp = CryptowelderContext._parse_iso_timestamp

        self.target = BitfinexWelder(self.context)

    def test_run(self):
        self.context.is_closed = MagicMock(return_value=True)
        self.target.run()
        self.target._join()
        self.context.is_closed.assert_called_once()

    def test___loop(self):
        self.context.is_closed = MagicMock(side_effect=(False, False, True))
        self.target._process_ticker = MagicMock()
        self.target._loop(default_interval=0.1)
        self.assertEqual(3, self.context.is_closed.call_count)
        self.assertEqual(2 * 3, self.target._process_ticker.call_count)

    def test__process_ticker(self):
        self.context.save_tickers = MagicMock()
        self.context.requests_get = MagicMock(return_value=CryptowelderContext._parse("""
            {
              "mid": "8901.25",
              "bid": "8901.2",
              "ask": "8901.3",
              "last_price": "8901.4",
              "low": "7890.123456789",
              "high": "9012.3",
              "volume": "123456.78901234",
              "timestamp": "1234567890.1234567"
            }
        """))

        self.target._process_ticker("FOO_BAR")

        tickers = self.context.save_tickers.call_args[0][0]
        self.assertEqual(1, len(tickers))
        self.assertEqual('bitfinex', tickers[0].tk_site)
        self.assertEqual('FOO_BAR', tickers[0].tk_code)
        self.assertEqual('2009-02-13 23:31:30.123457 UTC', tickers[0].tk_time.strftime(self.FORMAT))
        self.assertEqual('8901.3', tickers[0].tk_ask)
        self.assertEqual('8901.2', tickers[0].tk_bid)
        self.assertEqual('8901.4', tickers[0].tk_ltp)

        # Query None
        self.context.requests_get.reset_mock()
        self.context.requests_get.return_value = None
        self.context.save_tickers.reset_mock()
        self.target._process_ticker("FOO_BAR")
        self.context.requests_get.assert_called_once()
        self.context.save_tickers.assert_not_called()

        # Query Failure
        self.context.requests_get.reset_mock()
        self.context.requests_get.side_effect = Exception('test')
        self.context.save_tickers.reset_mock()
        self.target._process_ticker("FOO_BAR")
        self.context.requests_get.assert_called_once()
        self.context.save_tickers.assert_not_called()


if __name__ == '__main__':
    main()
