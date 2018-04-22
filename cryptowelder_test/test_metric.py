from collections import namedtuple, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from unittest import TestCase, main
from unittest.mock import MagicMock

from cryptowelder.context import CryptowelderContext, Ticker, Metric
from cryptowelder.metric import MetricWelder


class TestMetricWelder(TestCase):
    FORMAT = '%Y-%m-%d %H:%M:%S.%f %Z'

    def setUp(self):
        self.context = MagicMock()
        self.context.get_logger.return_value = MagicMock()
        self.context.get_property = lambda section, key, val: val
        self.context.parse_iso_timestamp = CryptowelderContext._parse_iso_timestamp

        self.target = MetricWelder(self.context)

    def test_run(self):
        self.target._wrap = MagicMock()

        self.target.run()
        self.target._join()

        calls = self.target._wrap.call_args_list
        self.assertEqual(self.target.process_metric, calls[0][0][0])
        self.assertEqual(self.target.purge_metric, calls[1][0][0])
        self.assertEqual(30, calls[0][0][1])
        self.assertEqual(3600, calls[1][0][1])

    def test__wrap(self):
        self.context.is_closed = MagicMock(side_effect=[False, False, False, True])

        method = MagicMock(
            __name__='mocked',
            side_effect=[None, Exception('test'), None]
        )

        self.target._wrap(method, 0.1)

        self.assertEqual(3, len(method.call_args_list))

    def test__process_metric(self):
        now = datetime.fromtimestamp(1234567890.123456)
        t0 = now.replace(second=0, microsecond=0)
        t1 = t0 - timedelta(minutes=1)
        t2 = t0 - timedelta(minutes=2)
        prices = {'foo': {'bar': 'hoge'}}
        self.context.get_now = MagicMock(return_value=now)
        self.target.process_ticker = MagicMock(return_value=prices)
        self.target.process_balance = MagicMock()
        self.target.process_position = MagicMock()
        self.target.process_transaction_trade = MagicMock()
        self.target.process_transaction_volume = MagicMock()

        self.target.process_metric()

        self.assertEqual(3, len(self.target.process_ticker.call_args_list))
        self.assertEqual(3, len(self.target.process_balance.call_args_list))
        self.assertEqual(3, len(self.target.process_position.call_args_list))
        self.assertEqual(3, len(self.target.process_transaction_trade.call_args_list))
        self.assertEqual(3, len(self.target.process_transaction_volume.call_args_list))

        for i, t in enumerate((t0, t1, t2)):
            self.assertEqual(t, self.target.process_ticker.call_args_list[i][0][0])

            self.assertEqual(t, self.target.process_balance.call_args_list[i][0][0])
            self.assertEqual(prices, self.target.process_balance.call_args_list[i][0][1])

            self.assertEqual(t, self.target.process_position.call_args_list[i][0][0])
            self.assertEqual(prices, self.target.process_position.call_args_list[i][0][1])

            self.assertEqual(t, self.target.process_transaction_trade.call_args_list[i][0][0])
            self.assertEqual(prices, self.target.process_transaction_trade.call_args_list[i][0][1])

            self.assertEqual(t, self.target.process_transaction_volume.call_args_list[i][0][0])
            self.assertEqual(prices, self.target.process_transaction_volume.call_args_list[i][0][1])

    def test_process_ticker(self):
        now = datetime.fromtimestamp(1234567890.123456)

        dto = namedtuple('TickerDto', ('ticker',))
        tickers = [dto(1), dto(2), dto(3)]
        self.context.fetch_tickers = MagicMock(return_value=tickers)

        prices = defaultdict(lambda: {})
        self.target._calculate_prices = MagicMock(return_value=prices)

        metrics = [Metric(), None, Metric()]
        self.target._convert_ticker = MagicMock(side_effect=metrics)

        self.context.save_metrics = MagicMock()
        result = self.target.process_ticker(now)
        self.assertEqual(prices, result)
        self.context.save_metrics.assert_called_once()

        self.assertEqual(2, len(self.context.save_metrics.call_args[0][0]))
        self.assertEqual(metrics[0], self.context.save_metrics.call_args[0][0][0])
        self.assertEqual(metrics[2], self.context.save_metrics.call_args[0][0][1])

        self.context.fetch_tickers = MagicMock(side_effect=Exception('test'))
        self.assertIsNone(self.target.process_ticker(now))

    def test__calculate_prices(self):
        t1 = Ticker()
        t1.tk_site = 's1'
        t1.tk_code = 'c1'
        t1.tk_ask = Decimal('1.5')
        t1.tk_bid = Decimal('1.1')
        t1.tk_ltp = Decimal('1.2')

        t2 = Ticker()
        t2.tk_site = 's1'
        t2.tk_code = 'c2'
        t2.tk_ask = None
        t2.tk_bid = Decimal('1.1')
        t2.tk_ltp = Decimal('1.2')

        t3 = Ticker()
        t3.tk_site = 's2'
        t3.tk_code = 'c1'
        t3.tk_ask = Decimal('1.5')
        t3.tk_bid = Decimal(0)
        t3.tk_ltp = Decimal('1.2')

        t4 = Ticker()
        t4.tk_site = 's3'
        t4.tk_code = 'c3'
        t4.tk_ask = Decimal('0.0')
        t4.tk_bid = None
        t4.tk_ltp = Decimal('1.2')

        t5 = Ticker()
        t5.tk_site = 's4'
        t5.tk_code = 'c4'
        t5.tk_ask = None
        t5.tk_bid = None
        t5.tk_ltp = Decimal('0.0')

        dto = namedtuple('TickerDto', ('ticker',))
        prices = self.target._calculate_prices((dto(t1), dto(t2), dto(t3), dto(t4), dto(t5)))
        self.assertEqual(Decimal('1.3'), prices['s1']['c1'])
        self.assertEqual(Decimal('1.15'), prices['s1']['c2'])
        self.assertEqual(Decimal('1.35'), prices['s2']['c1'])
        self.assertEqual(Decimal('1.2'), prices['s3']['c3'])
        self.assertIsNone(prices['s4']['c4'])


if __name__ == '__main__':
    main()
