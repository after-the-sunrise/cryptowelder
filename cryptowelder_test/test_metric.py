from unittest import TestCase, main
from unittest.mock import MagicMock

from cryptowelder.context import CryptowelderContext
from cryptowelder.metric import MetricWelder


class TestPoloniexWelder(TestCase):
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


if __name__ == '__main__':
    main()
