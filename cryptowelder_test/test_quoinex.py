from datetime import datetime
from decimal import Decimal
from unittest import TestCase, main
from unittest.mock import MagicMock

from pytz import utc

from cryptowelder.context import CryptowelderContext
from cryptowelder.quoinex import QuoinexWelder


class TestQuoinexWelder(TestCase):
    FORMAT = '%Y-%m-%d %H:%M:%S.%f %Z'

    def setUp(self):
        self.context = MagicMock()
        self.context.get_logger.return_value = MagicMock()
        self.context.get_property = lambda section, key, val: val
        self.context.parse_iso_timestamp = CryptowelderContext._parse_iso_timestamp

        self.target = QuoinexWelder(self.context)

    def test_run(self):
        self.context.is_closed = MagicMock(return_value=True)
        self.target.run()
        self.target._join()
        self.context.is_closed.assert_called_once()

    def test___loop(self):
        self.context.is_closed = MagicMock(side_effect=(False, False, True))
        self.target._process_products = MagicMock()
        self.target._process_cash = MagicMock()
        self.target._loop(default_interval=0.1)
        self.assertEqual(3, self.context.is_closed.call_count)
        self.assertEqual(2, self.target._process_products.call_count)
        self.assertEqual(2, self.target._process_cash.call_count)

    def test__process_products(self):
        self.context.requests_get = MagicMock()
        self.target._process_ticker = MagicMock()
        self.target._process_transaction = MagicMock()
        self.target._process_products()
        self.assertEqual(1, self.context.requests_get.call_count)
        self.assertEqual(2, self.target._process_ticker.call_count)
        self.assertEqual(2, self.target._process_transaction.call_count)

        # Failure
        self.context.requests_get.reset_mock()
        self.context.requests_get.side_effect = Exception('test')
        self.target._process_ticker.reset_mock()
        self.target._process_transaction.reset_mock()
        self.target._process_products()
        self.assertEqual(1, self.context.requests_get.call_count)
        self.target._process_ticker.assert_not_called()
        self.target._process_transaction.assert_not_called()

    def test__process_ticker(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.save_tickers = MagicMock()
        self.target._process_ticker(now, 'BTCUSD', CryptowelderContext._parse("""
            [
              {
                "id": "5",
                "product_type": "CurrencyPair",
                "code": "CASH",
                "name": " CASH Trading",
                "market_ask": 800000.02,
                "market_bid": 800000.01,
                "indicator": -1,
                "currency": "JPY",
                "currency_pair_code": "BTCJPY",
                "symbol": "¥",
                "btc_minimum_withdraw": null,
                "fiat_minimum_withdraw": null,
                "pusher_channel": "product_cash_btcjpy_5",
                "taker_fee": 0,
                "maker_fee": 0,
                "low_market_bid": "700000.1",
                "high_market_ask": "900000.2",
                "volume_24h": "7890.123456789123456789",
                "last_price_24h": "800000.3",
                "last_traded_price": "800000.4",
                "last_traded_quantity": "0.123",
                "quoted_currency": "JPY",
                "base_currency": "BTC",
                "disabled": false
              },
              {
                "id": "1",
                "product_type": "CurrencyPair",
                "code": "CASH",
                "name": " CASH Trading",
                "market_ask": 7000.02,
                "market_bid": 7000.01,
                "indicator": 1,
                "currency": "USD",
                "currency_pair_code": "BTCUSD",
                "symbol": "$",
                "btc_minimum_withdraw": null,
                "fiat_minimum_withdraw": null,
                "pusher_channel": "product_cash_btcusd_1",
                "taker_fee": 0,
                "maker_fee": 0,
                "low_market_bid": "6000.01",
                "high_market_ask": "8000.02",
                "volume_24h": "123.456789",
                "last_price_24h": "7000.03",
                "last_traded_price": "7000.04",
                "last_traded_quantity": "0.00123",
                "quoted_currency": "USD",
                "base_currency": "BTC",
                "disabled": false
              }
            ]  
        """))

        tickers = self.context.save_tickers.call_args[0][0]
        self.assertEqual(1, len(tickers))

        self.assertEqual('quoinex', tickers[0].tk_site)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', tickers[0].tk_time.strftime(self.FORMAT))
        self.assertEqual('BTCUSD', tickers[0].tk_code)
        self.assertEqual(Decimal('7000.02'), tickers[0].tk_ask)
        self.assertEqual(Decimal('7000.01'), tickers[0].tk_bid)
        self.assertEqual(Decimal('7000.04'), tickers[0].tk_ltp)

        # Query Blank
        self.context.save_tickers.reset_mock()
        self.target._process_ticker(now, 'BTCUSD', [{'currency_pair_code': 'BTCUSD'}])
        self.context.save_tickers.assert_called_once()

        # Query Empty
        self.context.save_tickers.reset_mock()
        self.target._process_ticker(now, 'BTCUSD', {})
        self.context.save_tickers.assert_not_called()

        # Query None
        self.context.save_tickers.reset_mock()
        self.target._process_ticker(now, 'BTCUSD', None)
        self.context.save_tickers.assert_not_called()

        # Save Failure
        self.context.save_tickers.reset_mock()
        self.context.save_tickers.side_effect = Exception('test')
        self.target._process_ticker(now, 'BTCUSD', [{'currency_pair_code': 'BTCUSD'}])
        self.context.save_tickers.assert_called_once()

    def test__query_private(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_nonce = MagicMock(return_value=now)
        self.context.requests_get = MagicMock(return_value='json')

        self.context.get_property = MagicMock(side_effect=['foo', 'bar'])
        self.assertEqual('json', self.target._query_private('/some_path'))
        self.assertEqual('https://api.liquid.com/some_path', self.context.requests_get.call_args[0][0])
        headers = self.context.requests_get.call_args[1]['headers']
        self.assertEqual(3, len(headers))
        self.assertEqual('application/json', headers['Content-Type'])
        self.assertEqual('2', headers['X-Quoine-API-Version'])
        self.assertEqual(b'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJwYXRoIjoiL3NvbWVfcGF0aCIsIm5vbmNlIjo' +
                         b'iMTIzNDU2Nzg5MDEyMyIsInRva2VuX2lkIjoiZm9vIn0.2KATaHP5ULsEOhwVaauET1R_ETTVcyk' +
                         b'pE4aqL01xhFU', headers['X-Quoine-Auth'])

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
            [
                {
                    "currency": "BTC",
                    "balance": "0.04925688"
                },
                {
                    "currency": "FOO",
                    "balance": "7.17696"
                },
                {
                    "currency": "JPY",
                    "balance": "356.01377"
                }
            ]
        """))

        self.target._process_cash()

        balances = self.context.save_balances.call_args[0][0]
        self.assertEqual(2, len(balances))

        self.assertEqual('quoinex', balances[0].bc_site)
        self.assertEqual('CASH', balances[0].bc_acct.name)
        self.assertEqual('BTC', balances[0].bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', balances[0].bc_time.strftime(self.FORMAT))
        self.assertEqual('0.04925688', balances[0].bc_amnt)

        self.assertEqual('quoinex', balances[1].bc_site)
        self.assertEqual('CASH', balances[1].bc_acct.name)
        self.assertEqual('JPY', balances[1].bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', balances[1].bc_time.strftime(self.FORMAT))
        self.assertEqual('356.01377', balances[1].bc_amnt)

        # Query Reject
        self.target._query_private.reset_mock()
        self.target._query_private.return_value = '{"success": 0}'
        self.context.save_balances.reset_mock()
        self.target._process_cash()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_not_called()

        # Query None
        self.target._query_private.reset_mock()
        self.target._query_private.return_value = None
        self.context.save_balances.reset_mock()
        self.target._process_cash()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_called_once()

        # Query Failure
        self.target._query_private.reset_mock()
        self.target._query_private.side_effect = Exception('test')
        self.context.save_balances.reset_mock()
        self.target._process_cash()
        self.target._query_private.assert_called_once()
        self.context.save_balances.assert_not_called()

    def test__process_transaction(self):
        pass  # TODO


if __name__ == '__main__':
    main()
