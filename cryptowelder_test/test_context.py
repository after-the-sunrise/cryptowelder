from copy import copy
from datetime import datetime, timedelta
from decimal import Decimal
from http.server import HTTPServer, BaseHTTPRequestHandler
from logging import DEBUG, StreamHandler
from logging.handlers import BufferingHandler
from threading import Thread
from time import sleep
from unittest import TestCase, main
from unittest.mock import MagicMock

from pytz import utc
from requests import get

from cryptowelder.context import CryptowelderContext, Transaction, Ticker, Balance, Position, AccountType, UnitType, \
    TransactionType


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
        self.target = CryptowelderContext(read_only=False)

    def test_property(self):
        self.assertIsNone(self.target.get_property('foo', 'bar', None))
        self.assertEquals(self.target.get_property('foo', 'bar', '12'), '12')

        self.target.set_property('foo', 'bar', '34')
        self.assertEquals(self.target.get_property('foo', 'bar', None), '34')
        self.assertEquals(self.target.get_property('foo', 'bar', '12'), '34')

        self.target.set_property('foo', 'bar', '56')
        self.assertEquals(self.target.get_property('foo', 'bar', None), '56')
        self.assertEquals(self.target.get_property('foo', 'bar', '12'), '56')

    def test_get_logger(self):
        logger = self.target.get_logger(self)
        self.assertEqual(logger.level, DEBUG)
        self.assertEqual(len(logger.handlers), 2)
        self.assertIsInstance(logger.handlers[0], StreamHandler)
        self.assertIsInstance(logger.handlers[1], BufferingHandler)

    def test_is_closed(self):
        self.assertFalse(self.target.is_closed())

    def test_get_now(self):
        self.assertIsNotNone(self.target.get_now())

    def test_parse_iso_timestamp(self):
        # Unix Time
        result = self.target.parse_iso_timestamp('1234567890')
        self.assertIsNotNone(result)
        self.assertEqual(2009, result.year)
        self.assertEqual(2, result.month)
        self.assertEqual(13, result.day)
        self.assertEqual(23, result.hour)
        self.assertEqual(31, result.minute)
        self.assertEqual(30, result.second)
        self.assertEqual(0, result.microsecond)
        self.assertEqual('UTC', result.tzname())

        # Unix Time - Various Types
        self.assertEqual(result, self.target.parse_iso_timestamp(1234567890))
        self.assertEqual(result, self.target.parse_iso_timestamp(1234567890.0))
        self.assertEqual(result, self.target.parse_iso_timestamp(Decimal('1234567890.0')))

        # Unix Time with Decimal
        result = self.target.parse_iso_timestamp('1234567890.123456')
        self.assertIsNotNone(result)
        self.assertEqual(2009, result.year)
        self.assertEqual(2, result.month)
        self.assertEqual(13, result.day)
        self.assertEqual(23, result.hour)
        self.assertEqual(31, result.minute)
        self.assertEqual(30, result.second)
        self.assertEqual(123456, result.microsecond)
        self.assertEqual('UTC', result.tzname())

        # Unix Time - Various Types
        self.assertEqual(result, self.target.parse_iso_timestamp(1234567890.123456))
        self.assertEqual(result, self.target.parse_iso_timestamp(Decimal('1234567890.123456')))

        # ISO
        result = self.target.parse_iso_timestamp('2017-04-14T12:34:56.789')
        self.assertIsNotNone(result)
        self.assertEqual(2017, result.year)
        self.assertEqual(4, result.month)
        self.assertEqual(14, result.day)
        self.assertEqual(12, result.hour)
        self.assertEqual(34, result.minute)
        self.assertEqual(56, result.second)
        self.assertEqual(0, result.microsecond)
        self.assertEqual('UTC', result.tzname())

        # ISO - Various Formats
        self.assertEqual(result, self.target.parse_iso_timestamp('2017-04-14T12:34:56'))
        self.assertEqual(result, self.target.parse_iso_timestamp('2017-04-14T12:34:56Z'))
        self.assertEqual(result, self.target.parse_iso_timestamp('2017-04-14T12:34:56.789123'))
        self.assertEqual(result, self.target.parse_iso_timestamp('2017-04-14T12:34:56.789123Z'))

        # ISO - Invalid Formats
        self.assertIsNone(self.target.parse_iso_timestamp('2017-04-14T12:34'))
        self.assertIsNone(self.target.parse_iso_timestamp('2017-04-14T12:34Z'))
        self.assertIsNone(self.target.parse_iso_timestamp(''))
        self.assertIsNone(self.target.parse_iso_timestamp(None))

    def test_launch_prometheus(self):
        method = MagicMock()

        # Default
        self.target.launch_prometheus(method=method)
        method.assert_called_with(20000, addr='localhost')

        # Custom host:port
        self.target.set_property(self.target._SECTION, 'prometheus_host', '127.0.0.1')
        self.target.set_property(self.target._SECTION, 'prometheus_port', '65535')
        self.target.launch_prometheus(method=method)
        method.assert_called_with(65535, addr='127.0.0.1')

    def test__parse(self):
        result = self.target._parse('{"str":"foo", "int":123, "flt":1.2, "flg":true}')
        self.assertEqual(len(result), 4)
        self.assertEqual(result['str'], "foo")
        self.assertEqual(result['int'], 123)
        self.assertEqual(result['flt'], Decimal('1.2'))
        self.assertEqual(result['flg'], True)

    def test__request(self):
        TestHander.init(content='{"str":"foo", "int":123, "flt":1.2, "flg":true}')
        result = self.target._request(lambda: get("http://localhost:65535"))
        self.assertEqual(len(result), 4)
        self.assertEqual(result['str'], "foo")
        self.assertEqual(result['int'], 123)
        self.assertEqual(result['flt'], Decimal('1.2'))
        self.assertEqual(result['flg'], True)

    def test__request_ClientError(self):
        self.target.set_property(self.target._SECTION, 'request_retry', '3')
        self.target.set_property(self.target._SECTION, 'request_sleep', '0.001')
        TestHander.init(status=404)
        result = self.target._request(lambda: get("http://localhost:65535"), label='test client')
        self.assertIsNone(result)

    def test__request_ServerError(self):
        self.target.set_property(self.target._SECTION, 'request_retry', '3')
        self.target.set_property(self.target._SECTION, 'request_sleep', '0.001')
        TestHander.init(status=502)
        result = self.target._request(lambda: get("http://localhost:65535"), label='test server')
        self.assertIsNone(result)

    def test_requests_get(self):
        response = "{'foo': 'bar'}"
        self.target._request = MagicMock(return_value=response)
        self.assertEqual(self.target.requests_get('http://localhost:65535'), response)
        self.target._request.assert_called_once()

    def test_requests_post(self):
        response = "{'foo': 'bar'}"
        self.target._request = MagicMock(return_value=response)
        self.assertEqual(self.target.requests_post('http://localhost:65535'), response)
        self.target._request.assert_called_once()

    def test__truncate_datetime(self):
        # Arbitrary Time
        dt = datetime(year=2017, month=4, day=14, hour=12, minute=34, second=56, microsecond=789123, tzinfo=utc)
        result = self.target._truncate_datetime(dt)
        self.assertEqual(2017, result.year)
        self.assertEqual(4, result.month)
        self.assertEqual(14, result.day)
        self.assertEqual(12, result.hour)
        self.assertEqual(35, result.minute)  # Round UP
        self.assertEqual(0, result.second)
        self.assertEqual(0, result.microsecond)
        self.assertEqual('UTC', result.tzname())

        # On boundary
        dt = datetime(year=2017, month=4, day=14, hour=12, minute=34, second=0, microsecond=0, tzinfo=utc)
        result = self.target._truncate_datetime(dt)
        self.assertEqual(2017, result.year)
        self.assertEqual(4, result.month)
        self.assertEqual(14, result.day)
        self.assertEqual(12, result.hour)
        self.assertEqual(34, result.minute)  # Round NONE
        self.assertEqual(0, result.second)
        self.assertEqual(0, result.microsecond)
        self.assertEqual('UTC', result.tzname())

        # On boundary + 1 micro
        result = self.target._truncate_datetime(dt + timedelta(microseconds=1))
        self.assertEqual(2017, result.year)
        self.assertEqual(4, result.month)
        self.assertEqual(14, result.day)
        self.assertEqual(12, result.hour)
        self.assertEqual(35, result.minute)  # Round UP
        self.assertEqual(0, result.second)
        self.assertEqual(0, result.microsecond)
        self.assertEqual('UTC', result.tzname())

        # On boundary - 1 micro
        result = self.target._truncate_datetime(dt - timedelta(microseconds=1))
        self.assertEqual(2017, result.year)
        self.assertEqual(4, result.month)
        self.assertEqual(14, result.day)
        self.assertEqual(12, result.hour)
        self.assertEqual(34, result.minute)  # Round UP
        self.assertEqual(0, result.second)
        self.assertEqual(0, result.microsecond)
        self.assertEqual('UTC', result.tzname())

    def test_save_tickers(self):
        self.target._create_all()

        dt = datetime.now()

        t1 = Ticker()
        t1.tk_site = 'ts'
        t1.tk_code = 'tp'
        t1.tk_time = dt + timedelta(minutes=1)
        t1.tk_ltp = Decimal('1.2')

        t2 = Ticker()
        t2.tk_site = 'ts'
        t2.tk_code = 'tp'
        t2.tk_time = dt + timedelta(minutes=2)
        t2.tk_ltp = Decimal('2.3')

        t3 = copy(t1)
        t3.tk_ltp = Decimal('3.4')

        t4 = copy(t2)
        t4.tk_ltp = Decimal('4.5')

        t5 = copy(t1)
        t5.tk_code = None

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

        # PK Failure
        with self.assertRaises(BaseException):
            self.target.save_tickers([t5])

        # Read-only
        self.target._is_read_only = lambda: True
        results = self.target.save_tickers([t1])
        self.assertEqual(len(results), 0)

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

        b5 = copy(b1)
        b5.bc_unit = None

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

        # PK Failure
        with self.assertRaises(BaseException):
            self.target.save_balances([b5])

        # Read-only
        self.target._is_read_only = lambda: True
        results = self.target.save_balances([b1])
        self.assertEqual(len(results), 0)

    def test_save_positions(self):
        self.target._create_all()

        dt = datetime.now()

        p1 = Position()
        p1.ps_site = 'ps'
        p1.ps_code = 'pc'
        p1.ps_time = dt + timedelta(minutes=1)
        p1.ps_inst = Decimal('1.2')
        p1.ps_fund = None

        p2 = Position()
        p2.ps_site = 'ps'
        p2.ps_code = 'pc'
        p2.ps_time = dt + timedelta(minutes=2)
        p2.ps_inst = None
        p2.ps_fund = Decimal('3.4')

        p3 = copy(p1)
        p3.ps_inst = Decimal('3.4')
        p3.ps_fund = Decimal('4.5')

        p4 = copy(p2)
        p4.ps_inst = Decimal('5.6')
        p4.ps_fund = Decimal('6.7')

        p5 = copy(p1)
        p5.ps_code = None

        # All new records
        results = self.target.save_positions([p1, p2])
        self.assertEqual(len(results), 2)
        self.assertTrue(p1 in results)
        self.assertTrue(p2 in results)

        # Existing records
        results = self.target.save_positions([p3, None, p4])
        self.assertEqual(len(results), 2)
        self.assertTrue(p3 in results)
        self.assertTrue(p4 in results)

        # PK Failure
        with self.assertRaises(BaseException):
            self.target.save_positions([p5])

        # Read-only
        self.target._is_read_only = lambda: True
        results = self.target.save_positions([p1])
        self.assertEqual(len(results), 0)

    def test_save_transactions(self):
        self.target._create_all()

        t1 = Transaction()
        t1.tx_site = 'ts'
        t1.tx_code = 'tp'
        t1.tx_type = TransactionType.TRADE
        t1.tx_acct = AccountType.CASH
        t1.tx_oid = 'to'
        t1.tx_eid = 'te'
        t1.tx_time = datetime.now()
        t1.tx_fund = -1.2
        t1.tx_inst = +2.3

        t2 = Transaction()
        t2.tx_site = 'ts'
        t2.tx_code = 'tp'
        t2.tx_type = TransactionType.TRADE
        t2.tx_acct = AccountType.CASH
        t2.tx_oid = 'NEW'
        t2.tx_eid = 'te'
        t2.tx_time = datetime.now()
        t2.tx_fund = -2.3
        t2.tx_inst = +3.4

        t3 = Transaction()
        t3.tx_site = 'ts'
        t3.tx_code = 'NEW'
        t3.tx_type = TransactionType.TRADE
        t3.tx_acct = AccountType.CASH
        t3.tx_oid = 'to'
        t3.tx_eid = 'te'
        t3.tx_time = datetime.now()
        t3.tx_fund = -3.4
        t3.tx_inst = +4.5

        t4 = Transaction()
        t4.tx_site = 'NEW'
        t4.tx_code = 'tp'
        t4.tx_type = TransactionType.TRADE
        t4.tx_acct = AccountType.CASH
        t4.tx_oid = 'to'
        t4.tx_eid = 'te'
        t4.tx_time = datetime.now()
        t4.tx_fund = -4.5
        t4.tx_inst = +5.6

        t2c = copy(t2)
        t3c = copy(t3)
        t4c = copy(t4)
        t4c.tx_oid = None

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

        # PK Failure
        with self.assertRaises(BaseException):
            self.target.save_transactions([t4c])

        # Read-only
        self.target._is_read_only = lambda: True
        results = self.target.save_transactions([t1])
        self.assertEqual(len(results), 0)


if __name__ == '__main__':
    main()
