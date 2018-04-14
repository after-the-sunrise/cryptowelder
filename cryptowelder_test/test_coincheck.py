from datetime import datetime
from decimal import Decimal
from unittest import TestCase, main
from unittest.mock import MagicMock

from pytz import utc

from cryptowelder.coincheck import CoincheckWelder
from cryptowelder.context import CryptowelderContext, TransactionType, AccountType


class TestCoincheckWelder(TestCase):
    FORMAT = '%Y-%m-%d %H:%M:%S.%f %Z'

    def setUp(self):
        self.context = MagicMock()
        self.context.get_logger.return_value = MagicMock()
        self.context.get_property = lambda section, key, val: val
        self.context.parse_iso_timestamp = CryptowelderContext._parse_iso_timestamp

        self.target = CoincheckWelder(self.context)

    def test_run(self):
        self.context.is_closed = MagicMock(return_value=True)
        self.target.run()
        self.target._join()
        self.context.is_closed.assert_called_once()

    def test___loop(self):
        self.context.is_closed = MagicMock(side_effect=(False, False, True))
        self.target._process_ticker = MagicMock()
        self.target._process_transaction = MagicMock()
        self.target._process_cash = MagicMock()
        self.target._process_margin = MagicMock()
        self.target._loop(default_interval=0.1)
        self.assertEqual(3, self.context.is_closed.call_count)
        self.assertEqual(2, self.target._process_ticker.call_count)
        self.assertEqual(2, self.target._process_transaction.call_count)
        self.assertEqual(2, self.target._process_cash.call_count)
        self.assertEqual(2, self.target._process_margin.call_count)

    def test__process_ticker(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_now = MagicMock(return_value=now)
        self.context.save_tickers = MagicMock()
        self.context.requests_get = MagicMock(return_value=CryptowelderContext._parse("""
            {
              "last": 27390,
              "bid": 26900,
              "ask": 27390,
              "high": 27659,
              "low": 26400,
              "volume": "50.29627103",
              "timestamp": 1423377841
            }
        """))

        self.target._process_ticker()

        tickers = self.context.save_tickers.call_args[0][0]
        self.assertEqual(1, len(tickers))

        self.assertEqual('coincheck', tickers[0].tk_site)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', tickers[0].tk_time.strftime(self.FORMAT))
        self.assertEqual('btc_jpy', tickers[0].tk_code)
        self.assertEqual(Decimal('27390'), tickers[0].tk_ask)
        self.assertEqual(Decimal('26900'), tickers[0].tk_bid)
        self.assertEqual(Decimal('27390'), tickers[0].tk_ltp)

        # Query Blank
        self.context.save_tickers.reset_mock()
        self.context.requests_get.reset_mock()
        self.context.requests_get.return_value = {}
        self.target._process_ticker()
        self.context.save_tickers.assert_called_once()

        # Query Empty
        self.context.save_tickers.reset_mock()
        self.context.requests_get.reset_mock()
        self.context.requests_get.return_value = None
        self.target._process_ticker()
        self.context.save_tickers.assert_not_called()

        # Query Failure
        self.context.save_tickers.reset_mock()
        self.context.requests_get.reset_mock()
        self.context.requests_get.side_effect = Exception('test')
        self.target._process_ticker()
        self.context.save_tickers.assert_not_called()

    def test__query_private(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_nonce = MagicMock(return_value=now)
        self.context.requests_get = MagicMock(return_value='json')

        self.context.get_property = MagicMock(side_effect=['foo', 'bar'])
        self.assertEqual('json', self.target._query_private('/some_path'))
        self.assertEqual('https://coincheck.com/some_path', self.context.requests_get.call_args[0][0])
        headers = self.context.requests_get.call_args[1]['headers']
        self.assertEqual(4, len(headers))
        self.assertEqual('application/json', headers['Accept'])
        self.assertEqual('foo', headers['ACCESS-KEY'])
        self.assertEqual('1234567890123', headers['ACCESS-NONCE'])
        self.assertEqual('0863df4a7ab1eed49ec08d818819f949' +
                         'edd22267927000fab591eb2453406d4f', headers['ACCESS-SIGNATURE'])

        # No Token
        self.context.get_property = MagicMock(return_value=None)
        self.context.requests_get.reset_mock()
        self.assertIsNone(self.target._query_private('/some_path'))
        self.context.requests_get.assert_not_called()

    def test__process_cash(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_now = MagicMock(return_value=now)
        self.context.save_balances = MagicMock()
        self.target._query_private = MagicMock(return_value=CryptowelderContext._parse("""
            {
              "success": true,
              "jpy": "0.8401",
              "btc": "7.75052654",
              "jpy_reserved": "3000.0",
              "btc_reserved": "3.5002",
              "jpy_lend_in_use": "0",
              "btc_lend_in_use": "0.3",
              "jpy_lent": "0",
              "btc_lent": "1.2",
              "jpy_debt": "0",
              "btc_debt": "0"
            }
        """))

        self.target._process_cash()

        balances = self.context.save_balances.call_args[0][0]
        self.assertEqual(2, len(balances))

        self.assertEqual('coincheck', balances[0].bc_site)
        self.assertEqual('CASH', balances[0].bc_acct.name)
        self.assertEqual('JPY', balances[0].bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', balances[0].bc_time.strftime(self.FORMAT))
        self.assertEqual(Decimal('3000.8401'), balances[0].bc_amnt)

        self.assertEqual('coincheck', balances[1].bc_site)
        self.assertEqual('CASH', balances[1].bc_acct.name)
        self.assertEqual('BTC', balances[1].bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', balances[1].bc_time.strftime(self.FORMAT))
        self.assertEqual(Decimal('11.25072654'), balances[1].bc_amnt)

        # Query Reject
        self.target._query_private.reset_mock()
        self.target._query_private.return_value = {'success': False}
        self.context.save_balances.reset_mock()
        self.target._process_cash()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_not_called()

        # Query Empty
        self.target._query_private.reset_mock()
        self.target._query_private.return_value = {}
        self.context.save_balances.reset_mock()
        self.target._process_cash()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_called_once()

        # Query None
        self.target._query_private.reset_mock()
        self.target._query_private.return_value = None
        self.context.save_balances.reset_mock()
        self.target._process_cash()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_not_called()

        # Query Failure
        self.target._query_private.reset_mock()
        self.target._query_private.side_effect = Exception('test')
        self.context.save_balances.reset_mock()
        self.target._process_cash()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_not_called()

    def test__process_margin(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_now = MagicMock(return_value=now)
        self.context.save_balances = MagicMock()
        self.target._query_private = MagicMock(return_value=CryptowelderContext._parse("""
            {
              "success": true,
              "margin": {
                "foo": "123456.78901234",
                "jpy": "131767.22675655"
              },
              "margin_available": {
                "jpy": "116995.98446494"
              },
              "margin_level": "8.36743"
            }
        """))

        self.target._process_margin()

        balances = self.context.save_balances.call_args[0][0]
        self.assertEqual(1, len(balances))

        self.assertEqual('coincheck', balances[0].bc_site)
        self.assertEqual('MARGIN', balances[0].bc_acct.name)
        self.assertEqual('JPY', balances[0].bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', balances[0].bc_time.strftime(self.FORMAT))
        self.assertEqual(Decimal('131767.22675655'), balances[0].bc_amnt)

        # Query Reject
        self.target._query_private.reset_mock()
        self.target._query_private.return_value = {'success': False}
        self.context.save_balances.reset_mock()
        self.target._process_margin()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_not_called()

        # Query Empty
        self.target._query_private.reset_mock()
        self.target._query_private.return_value = {}
        self.context.save_balances.reset_mock()
        self.target._process_margin()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_called_once()

        # Query None
        self.target._query_private.reset_mock()
        self.target._query_private.return_value = None
        self.context.save_balances.reset_mock()
        self.target._process_margin()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_not_called()

        # Query Failure
        self.target._query_private.reset_mock()
        self.target._query_private.side_effect = Exception('test')
        self.context.save_balances.reset_mock()
        self.target._process_margin()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_not_called()

    def test__process_transaction(self):
        side_effects = [CryptowelderContext._parse("""
            {
              "success": true,
              "transactions": [
                {
                  "id": 38,
                  "order_id": 49,
                  "created_at": "2015-11-18T07:02:21.000Z",
                  "funds": {
                    "btc": "0.1",
                    "jpy": "-4096.135"
                  },
                  "pair": "btc_jpy",
                  "rate": "40900.0",
                  "fee_currency": "JPY",
                  "fee": "6.135",
                  "liquidity": "T",
                  "side": "buy"
                },
                {
                  "id": 37,
                  "order_id": 48,
                  "created_at": "2015-11-18T07:02:21.000Z",
                  "funds": {
                    "btc": "-0.1",
                    "jpy": "4094.09"
                  },
                  "pair": "btc_jpy",
                  "rate": "40900.0",
                  "fee_currency": "JPY",
                  "fee": "-4.09",
                  "liquidity": "M",
                  "side": "sell"
                }
              ]
            }
        """), CryptowelderContext._parse("""
          {
          "success": true,
          "pagination": {
            "limit": 1,
            "order": "desc",
            "starting_after": null,
            "ending_before": null
          },
          "data": [
            {
              "id": 36,
              "order_id": 49,
              "created_at": "2015-11-18T07:02:21.000Z",
              "funds": {
                "btc": "0.1",
                "jpy": "-4096.135"
              },
              "pair": "btc_jpy",
              "rate": "40900.0",
              "fee_currency": "JPY",
              "fee": "6.135",
              "liquidity": "T",
              "side": "buy"
            },
            {
              "id": 35,
              "order_id": 48,
              "created_at": "2015-11-18T07:02:21.000Z",
              "funds": {
                "btc": "-0.1",
                "jpy": "4094.09"
              },
              "pair": "btc_jpy",
              "rate": "40900.0",
              "fee_currency": "JPY",
              "fee": "-4.09",
              "liquidity": "M",
              "side": "sell"
            }
          ]
        }
        """), None]

        # Query 3 times
        self.target._query_private = MagicMock(side_effect=side_effects)
        self.context.save_transactions = MagicMock(side_effect=([None], []))
        self.target._process_transaction()
        self.target._query_private.assert_called()
        self.context.save_transactions.assert_called()

        calls = self.context.save_transactions.call_args_list
        self.assertEqual(2, len(calls))

        values = list(calls[0][0][0])
        self.assertEqual(2, len(values))

        value = values[0]
        self.assertEqual('coincheck', value.tx_site)
        self.assertEqual('btc_jpy', value.tx_code)
        self.assertEqual(TransactionType.TRADE, value.tx_type)
        self.assertEqual(AccountType.CASH, value.tx_acct)
        self.assertEqual('49', value.tx_oid)
        self.assertEqual('38', value.tx_eid)
        self.assertEqual('2015-11-18 07:02:21.000000 UTC', value.tx_time.strftime(self.FORMAT))
        self.assertEqual('0.1', value.tx_inst)
        self.assertEqual('-4096.135', value.tx_fund)

        value = values[1]
        self.assertEqual('coincheck', value.tx_site)
        self.assertEqual('btc_jpy', value.tx_code)
        self.assertEqual(TransactionType.TRADE, value.tx_type)
        self.assertEqual(AccountType.CASH, value.tx_acct)
        self.assertEqual('48', value.tx_oid)
        self.assertEqual('37', value.tx_eid)
        self.assertEqual('2015-11-18 07:02:21.000000 UTC', value.tx_time.strftime(self.FORMAT))
        self.assertEqual('-0.1', value.tx_inst)
        self.assertEqual('4094.09', value.tx_fund)

        values = list(calls[1][0][0])
        self.assertEqual(2, len(values))

        value = values[0]
        self.assertEqual('coincheck', value.tx_site)
        self.assertEqual('btc_jpy', value.tx_code)
        self.assertEqual(TransactionType.TRADE, value.tx_type)
        self.assertEqual(AccountType.CASH, value.tx_acct)
        self.assertEqual('49', value.tx_oid)
        self.assertEqual('36', value.tx_eid)
        self.assertEqual('2015-11-18 07:02:21.000000 UTC', value.tx_time.strftime(self.FORMAT))
        self.assertEqual('0.1', value.tx_inst)
        self.assertEqual('-4096.135', value.tx_fund)

        value = values[1]
        self.assertEqual('coincheck', value.tx_site)
        self.assertEqual('btc_jpy', value.tx_code)
        self.assertEqual(TransactionType.TRADE, value.tx_type)
        self.assertEqual(AccountType.CASH, value.tx_acct)
        self.assertEqual('48', value.tx_oid)
        self.assertEqual('35', value.tx_eid)
        self.assertEqual('2015-11-18 07:02:21.000000 UTC', value.tx_time.strftime(self.FORMAT))
        self.assertEqual('-0.1', value.tx_inst)
        self.assertEqual('4094.09', value.tx_fund)

        # Empty Trades
        self.target._query_private = MagicMock(return_value={"success": True})
        self.context.save_transactions = MagicMock(side_effect=[[None], None])
        self.target._process_transaction()
        self.target._query_private.assert_called()
        self.context.save_transactions.assert_called()
        self.assertEqual(2, len(self.context.save_transactions.call_args_list))
        self.assertEqual(0, len(self.context.save_transactions.call_args_list[0][0][0]))
        self.assertEqual(0, len(self.context.save_transactions.call_args_list[1][0][0]))

        # Failure Response
        self.target._query_private = MagicMock(return_value=CryptowelderContext._parse("""
            {
                "success": 0,
                "return": {
                }
            }
        """))
        self.context.save_transactions = MagicMock(return_value=[None])
        self.target._process_transaction()
        self.target._query_private.assert_called_once()
        self.context.save_transactions.assert_not_called()

        # No Response
        self.target._query_private = MagicMock(return_value=None)
        self.context.save_transactions = MagicMock(return_value=[None])
        self.target._process_transaction()
        self.target._query_private.assert_called_once()
        self.context.save_transactions.assert_not_called()

        # Exception Response
        self.target._query_private = MagicMock(side_effect=Exception('test'))
        self.context.save_transactions = MagicMock(return_value=[None])
        self.target._process_transaction()
        self.target._query_private.assert_called_once()
        self.context.save_transactions.assert_not_called()


if __name__ == '__main__':
    main()
