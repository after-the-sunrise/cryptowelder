from datetime import datetime
from unittest import TestCase, main
from unittest.mock import MagicMock

from pytz import utc

from cryptowelder.binance import BinanceWelder
from cryptowelder.context import CryptowelderContext


class TestPoloniexWelder(TestCase):
    FORMAT = '%Y-%m-%d %H:%M:%S.%f %Z'

    def setUp(self):
        self.context = MagicMock()
        self.context.get_logger.return_value = MagicMock()
        self.context.get_property = lambda section, key, val: val
        self.context.parse_iso_timestamp = CryptowelderContext._parse_iso_timestamp

        self.target = BinanceWelder(self.context)

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
        self.assertEqual(2, self.target._process_ticker.call_count)

    def test__process_ticker(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_now = MagicMock(return_value=now)
        self.context.save_tickers = MagicMock()
        self.context.requests_get = MagicMock(side_effect=[
            CryptowelderContext._parse("""
                [
                  {
                    "symbol": "ETHBTC",
                    "price": "0.05618000"
                  },
                  {
                    "symbol": "BCCBTC",
                    "price": "0.09989100"
                  },
                  {
                    "symbol": "BTCUSDT",
                    "price": "6778.00000000"
                  }
                ]
            """),
            CryptowelderContext._parse("""
                [
                  {
                    "symbol": "ETHBTC",
                    "bidPrice": "0.05608800",
                    "bidQty": "2.09100000",
                    "askPrice": "0.05613000",
                    "askQty": "0.71900000"
                  },
                  {
                    "symbol": "BCCBTC",
                    "bidPrice": "0.09977100",
                    "bidQty": "0.77700000",
                    "askPrice": "0.09990500",
                    "askQty": "3.96600000"
                  },
                  {
                    "symbol": "BTCUSDT",
                    "bidPrice": "6762.01000000",
                    "bidQty": "0.29040300",
                    "askPrice": "6768.97000000",
                    "askQty": "0.01863300"
                  }
                ]
            """)
        ])

        self.target._process_ticker()

        tickers = self.context.save_tickers.call_args[0][0]
        self.assertEqual(3, len(tickers))

        for t in tickers:
            self.assertEqual('binance', t.tk_site)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', t.tk_time.strftime(self.FORMAT))

        self.assertEqual('BTCUSDT', tickers[0].tk_code)
        self.assertEqual('6768.97000000', tickers[0].tk_ask)
        self.assertEqual('6762.01000000', tickers[0].tk_bid)
        self.assertEqual('6778.00000000', tickers[0].tk_ltp)
        self.assertEqual('ETHBTC', tickers[1].tk_code)
        self.assertEqual('0.05613000', tickers[1].tk_ask)
        self.assertEqual('0.05608800', tickers[1].tk_bid)
        self.assertEqual('0.05618000', tickers[1].tk_ltp)
        self.assertEqual('BCCBTC', tickers[2].tk_code)
        self.assertEqual('0.09990500', tickers[2].tk_ask)
        self.assertEqual('0.09977100', tickers[2].tk_bid)
        self.assertEqual('0.09989100', tickers[2].tk_ltp)

        # Query Empty
        self.context.requests_get.reset_mock()
        self.context.requests_get.side_effect = ([], [])
        self.context.save_tickers.reset_mock()
        self.target._process_ticker()
        self.context.requests_get.assert_called()
        self.context.save_tickers.assert_called_once()

        # Query None
        self.context.requests_get.reset_mock()
        self.context.requests_get.side_effect = (None, None)
        self.context.save_tickers.reset_mock()
        self.target._process_ticker()
        self.context.requests_get.assert_called()
        self.context.save_tickers.assert_not_called()

        # Query Failure
        self.context.requests_get.reset_mock()
        self.context.requests_get.side_effect = Exception('test')
        self.context.save_tickers.reset_mock()
        self.target._process_ticker()
        self.context.requests_get.assert_called_once()
        self.context.save_tickers.assert_not_called()


if __name__ == '__main__':
    main()
