from datetime import datetime
from unittest import TestCase, main
from unittest.mock import MagicMock

from pytz import utc

from cryptowelder.context import CryptowelderContext
from cryptowelder.poloniex import PoloniexWelder


class TestPoloniexWelder(TestCase):
    FORMAT = '%Y-%m-%d %H:%M:%S.%f %Z'

    def setUp(self):
        self.context = MagicMock()
        self.context.get_logger.return_value = MagicMock()
        self.context.get_property = lambda section, key, val: val
        self.context.parse_iso_timestamp = CryptowelderContext._parse_iso_timestamp

        self.target = PoloniexWelder(self.context)

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
        self.context.requests_get = MagicMock(return_value=CryptowelderContext._parse("""
            {
              "USDT_BTC": {
                "id": 121,
                "last": "6837.76161630",
                "lowestAsk": "6847.96452531",
                "highestBid": "6837.95942149",
                "percentChange": "0.00322068",
                "baseVolume": "16800887.95429000",
                "quoteVolume": "2394.01850315",
                "isFrozen": "0",
                "high24hr": "7230.95559729",
                "low24hr": "6790.00000400"
              },
              "BTC_BCH": {
                "id": 189,
                "last": "0.09980623",
                "lowestAsk": "0.09986232",
                "highestBid": "0.09980509",
                "percentChange": "-0.02342240",
                "baseVolume": "144.70806421",
                "quoteVolume": "1458.21509325",
                "isFrozen": "0",
                "high24hr": "0.10245491",
                "low24hr": "0.09791995"
              },
              "BTC_ETH": {
                "id": 148,
                "last": "0.05646514",
                "lowestAsk": "0.05646514",
                "highestBid": "0.05646490",
                "percentChange": "-0.01688621",
                "baseVolume": "926.77280825",
                "quoteVolume": "16280.27386100",
                "isFrozen": "0",
                "high24hr": "0.05772499",
                "low24hr": "0.05627504"
              }
            }
        """))

        self.target._process_ticker()

        tickers = self.context.save_tickers.call_args[0][0]
        self.assertEqual(3, len(tickers))

        for t in tickers:
            self.assertEqual('poloniex', t.tk_site)
            self.assertEqual('2009-02-13 23:31:30.123456 UTC', t.tk_time.strftime(self.FORMAT))

        self.assertEqual('USDT_BTC', tickers[0].tk_code)
        self.assertEqual('6847.96452531', tickers[0].tk_ask)
        self.assertEqual('6837.95942149', tickers[0].tk_bid)
        self.assertEqual('6837.76161630', tickers[0].tk_ltp)
        self.assertEqual('BTC_BCH', tickers[1].tk_code)
        self.assertEqual('0.09986232', tickers[1].tk_ask)
        self.assertEqual('0.09980509', tickers[1].tk_bid)
        self.assertEqual('0.09980623', tickers[1].tk_ltp)
        self.assertEqual('BTC_ETH', tickers[2].tk_code)
        self.assertEqual('0.05646514', tickers[2].tk_ask)
        self.assertEqual('0.05646490', tickers[2].tk_bid)
        self.assertEqual('0.05646514', tickers[2].tk_ltp)

        # Query Empty
        self.context.requests_get.reset_mock()
        self.context.requests_get.return_value = {}
        self.context.save_tickers.reset_mock()
        self.target._process_ticker()
        self.context.requests_get.assert_called_once()
        self.context.save_tickers.assert_called_once()

        # Query None
        self.context.requests_get.reset_mock()
        self.context.requests_get.return_value = None
        self.context.save_tickers.reset_mock()
        self.target._process_ticker()
        self.context.requests_get.assert_called_once()
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
