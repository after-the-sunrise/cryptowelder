from copy import copy
from datetime import datetime, timedelta
from decimal import Decimal
from http.server import HTTPServer, BaseHTTPRequestHandler
from logging import DEBUG, StreamHandler
from logging.handlers import BufferingHandler
from threading import Thread
from time import sleep
from unittest import TestCase, main, mock

from requests import get

from cryptowelder.context import CryptowelderContext, Transaction, Ticker, Balance, AccountType, UnitType


class TestHander(BaseHTTPRequestHandler):

    @classmethod
    def init(cls, *, status=200, content=None):
        cls.STATUS = status
        cls.CONTENT = content

    def do_GET(self):

        if self.STATUS is None:
            raise Exception('TEST-ERROR')

        if self.STATUS >= 400:
            self.send_error(self.STATUS, "TEST-FAIL")
            self.end_headers()
            return

        if self.CONTENT is None:
            self.send_response(204, "TEST-NONE")
            self.end_headers()
        else:
            self.send_response(self.STATUS, "TEST-OK")
            self.end_headers()
            self.wfile.write(str.encode(self.CONTENT))


class TestCryptowelderContext(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.SERVER = HTTPServer(('localhost', 65535), TestHander)
        Thread(target=lambda: cls.SERVER.serve_forever()).start()
        sleep(1)  # Wait for the server to start.

    @classmethod
    def tearDownClass(cls):
        cls.SERVER.shutdown()

    def setUp(self):
        self.target = CryptowelderContext()

    def test_get_logger(self):
        logger = self.target.get_logger(self)
        self.assertEqual(logger.level, DEBUG)
        self.assertEqual(len(logger.handlers), 2)
        self.assertIsInstance(logger.handlers[0], StreamHandler)
        self.assertIsInstance(logger.handlers[1], BufferingHandler)

    def test__request(self):
        TestHander.init(content='{"str":"foo", "int":123, "flt":1.2, "flg":true}')
        result = self.target._request(lambda: get("http://localhost:65535"), interval=0.001)
        self.assertEqual(len(result), 4)
        self.assertEqual(result['str'], "foo")
        self.assertEqual(result['int'], 123)
        self.assertEqual(result['flt'], Decimal('1.2'))
        self.assertEqual(result['flg'], True)

    def test__request_ClientError(self):
        TestHander.init(status=404)
        result = self.target._request(lambda: get("http://localhost:65535"), interval=0.001)
        self.assertIsNone(result)

    def test__request_ServerError(self):
        TestHander.init(status=502)
        result = self.target._request(lambda: get("http://localhost:65535"), interval=0.001)
        self.assertIsNone(result)

    def test_requests_get(self):
        response = "{'foo': 'bar'}"
        self.target._request = mock.MagicMock(return_value=response)
        self.assertEqual(self.target.requests_get('http://localhost:65535'), response)

    def test_requests_post(self):
        response = "{'foo': 'bar'}"
        self.target._request = mock.MagicMock(return_value=response)
        self.assertEqual(self.target.requests_post('http://localhost:65535'), response)

    def test_save_tickers(self):
        self.target._create_all()

        dt = datetime.now()

        t1 = Ticker()
        t1.tk_site = 'ts'
        t1.tk_product = 'tp'
        t1.tk_time = dt + timedelta(minutes=1)
        t1.tk_ltp = Decimal('1.2')

        t2 = Ticker()
        t2.tk_site = 'ts'
        t2.tk_product = 'tp'
        t2.tk_time = dt + timedelta(minutes=2)
        t2.tk_ltp = Decimal('2.3')

        t3 = copy(t1)
        t3.tk_ltp = Decimal('3.4')

        t4 = copy(t2)
        t4.tk_ltp = Decimal('4.5')

        # All new records
        results = self.target.save_tickers([t1, t2])
        self.assertEqual(len(results), 2)
        self.assertTrue(t1 in results)
        self.assertTrue(t2 in results)

        # Existing records
        results = self.target.save_tickers([t3, None, t4])
        self.assertEqual(len(results), 2)
        self.assertTrue(t3 in results)
        self.assertTrue(t4 in results)

    def test_save_balances(self):
        self.target._create_all()

        dt = datetime.now()

        b1 = Balance()
        b1.bc_site = 'ts'
        b1.bc_acct = AccountType.CASH
        b1.bc_unit = UnitType.QTY
        b1.bc_time = dt + timedelta(minutes=1)
        b1.bc_amnt = Decimal('1.2')

        b2 = Balance()
        b2.bc_site = 'ts'
        b2.bc_acct = AccountType.CASH
        b2.bc_unit = UnitType.QTY
        b2.bc_time = dt + timedelta(minutes=2)
        b2.bc_amnt = Decimal('1.2')

        b3 = copy(b1)
        b3.bc_amnt = Decimal('3.4')

        b4 = copy(b2)
        b4.bc_amnt = Decimal('4.5')

        # All new records
        results = self.target.save_balances([b1, b2])
        self.assertEqual(len(results), 2)
        self.assertTrue(b1 in results)
        self.assertTrue(b2 in results)

        # Existing records
        results = self.target.save_balances([b3, None, b4])
        self.assertEqual(len(results), 2)
        self.assertTrue(b3 in results)
        self.assertTrue(b4 in results)

    def test_save_transactions(self):
        self.target._create_all()

        t1 = Transaction()
        t1.tx_site = 'ts'
        t1.tx_product = 'tp'
        t1.tx_id = 'ti'
        t1.tx_time = datetime.now()
        t1.tx_fund = -1.2
        t1.tx_inst = +2.3

        t2 = Transaction()
        t2.tx_site = 'ts'
        t2.tx_product = 'tp'
        t2.tx_id = 'NEW'
        t2.tx_time = datetime.now()
        t2.tx_fund = -2.3
        t2.tx_inst = +3.4

        t3 = Transaction()
        t3.tx_site = 'ts'
        t3.tx_product = 'NEW'
        t3.tx_id = 'ti'
        t3.tx_time = datetime.now()
        t3.tx_fund = -3.4
        t3.tx_inst = +4.5

        t4 = Transaction()
        t4.tx_site = 'NEW'
        t4.tx_product = 'tp'
        t4.tx_id = 'ti'
        t4.tx_time = datetime.now()
        t4.tx_fund = -4.5
        t4.tx_inst = +5.6

        t2c = copy(t2)
        t3c = copy(t3)

        # All new records
        results = self.target.save_transactions([t1, t2, t3])
        self.assertEqual(len(results), 3)
        self.assertTrue(t1 in results)
        self.assertTrue(t2 in results)
        self.assertTrue(t3 in results)

        # One new record
        results = self.target.save_transactions([t2c, t3c, None, t4])
        self.assertEqual(len(results), 1)
        self.assertTrue(t4 in results)

        # No record
        results = self.target.save_transactions(None)
        self.assertEqual(len(results), 0)


if __name__ == '__main__':
    main()
