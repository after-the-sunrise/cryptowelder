from logging import DEBUG, StreamHandler
from logging.handlers import BufferingHandler
from unittest import TestCase, main, mock, skip

from cryptowelder.context import CryptowelderContext, Transaction


class TestCryptowelderContext(TestCase):

    def setUp(self):
        self.target = CryptowelderContext()

    def test_get_logger(self):
        logger = self.target.get_logger(self)
        self.assertEqual(logger.level, DEBUG)
        self.assertEqual(len(logger.handlers), 2)
        self.assertIsInstance(logger.handlers[0], StreamHandler)
        self.assertIsInstance(logger.handlers[1], BufferingHandler)

    def test__request(self):
        f = mock.MagicMock(side_effect=Exception("side effect"))
        result = self.target._request(f, interval=0.001)
        self.assertIsNone(result)

    def test_requests_get(self):
        response = "{'foo': 'bar'}"
        self.target._request = mock.MagicMock(return_value=response)
        self.assertEqual(self.target.requests_get('localhost:65535'), response)

    @skip
    def test_requests_get_real(self):
        print(self.target.requests_get('http://xkcd.com/info.0.json'))

    def test_requests_post(self):
        response = "{'foo': 'bar'}"
        self.target._request = mock.MagicMock(return_value=response)
        self.assertEqual(self.target.requests_post('localhost:65535'), response)

    def test_add_transactions(self):
        # Initialize in-memory tables.
        self.target._create_all()

        t1 = Transaction()
        t1.tx_site = 'ts'
        t1.tx_product = 'tp'
        t1.tx_id = 'ti'
        t1.tx_fund = -1.2
        t1.tx_inst = +2.3

        t2 = Transaction()
        t2.tx_site = 'ts'
        t2.tx_product = 'tp'
        t2.tx_id = 'NEW'
        t2.tx_fund = -2.3
        t2.tx_inst = +3.4

        t3 = Transaction()
        t3.tx_site = 'ts'
        t3.tx_product = 'NEW'
        t3.tx_id = 'ti'
        t3.tx_fund = -3.4
        t3.tx_inst = +4.5

        t4 = Transaction()
        t4.tx_site = 'NEW'
        t4.tx_product = 'tp'
        t4.tx_id = 'ti'
        t4.tx_fund = -4.5
        t4.tx_inst = +5.6

        # All new records
        results = self.target.add_transactions([t1, t2, t3])
        self.assertEqual(len(results), 3)
        self.assertTrue(t1 in results)
        self.assertTrue(t2 in results)
        self.assertTrue(t3 in results)

        # One new record
        results = self.target.add_transactions([t2, t3, t4])
        self.assertEqual(len(results), 1)
        self.assertTrue(t4 in results)

        # No record
        results = self.target.add_transactions(None)
        self.assertEqual(len(results), 0)


if __name__ == '__main__':
    main()
