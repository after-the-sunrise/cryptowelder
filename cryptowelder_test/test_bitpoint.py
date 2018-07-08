from datetime import datetime
from unittest import TestCase, main
from unittest.mock import MagicMock

from pytz import utc

from cryptowelder.bitpoint import BitpointWelder
from cryptowelder.context import CryptowelderContext


class TestBtcboxWelder(TestCase):
    FORMAT = '%Y-%m-%d %H:%M:%S.%f %Z'

    def setUp(self):
        self.context = MagicMock()
        self.context.get_logger.return_value = MagicMock()
        self.context.get_property = lambda section, key, val: val
        self.context.parse_iso_timestamp = CryptowelderContext._parse_iso_timestamp

        self.target = BitpointWelder(self.context)

    def test_run(self):
        self.context.is_closed = MagicMock(return_value=True)
        self.target.run()
        self.target._join()
        self.context.is_closed.assert_called_once()

    def test___loop(self):
        self.context.is_closed = MagicMock(side_effect=(False, False, True))
        self.target._process_cash = MagicMock()
        self.target._process_coin = MagicMock()
        self.target._loop(default_interval=0.1)
        self.assertEqual(3, self.context.is_closed.call_count)
        self.assertEqual(2, self.target._process_cash.call_count)
        self.assertEqual(2, self.target._process_coin.call_count)

    def test__fetch_token(self):
        self.context.get_property = MagicMock(side_effect=('p1', 'p2', 'p3', 'p4', None, None))
        self.context.requests_get = MagicMock(return_value=CryptowelderContext._parse("""
            {"access_token":"00000000-0000-0000-0000-000000000000"}
        """))
        self.assertEqual('00000000-0000-0000-0000-000000000000', self.target._fetch_token())
        self.assertEqual(1, self.context.requests_get.call_count)

        # Cached
        self.assertEqual('00000000-0000-0000-0000-000000000000', self.target._fetch_token())
        self.assertEqual('00000000-0000-0000-0000-000000000000', self.target._fetch_token())
        self.assertEqual(1, self.context.requests_get.call_count)

        # Force Refresh
        self.assertEqual('00000000-0000-0000-0000-000000000000', self.target._fetch_token(force=True))
        self.assertEqual(2, self.context.requests_get.call_count)

        # No key
        self.assertIsNone(self.target._fetch_token(force=True))
        self.assertEqual(2, self.context.requests_get.call_count)

    def test__process_cash(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_now = MagicMock(return_value=now)
        self.context.save_balances = MagicMock()
        self.context.requests_post = MagicMock(return_value=CryptowelderContext._parse("""
            {
              "resultCode": "0",
              "errors": null,
              "rcBalanceList": [
                {
                  "currencyCd": "JPY",
                  "decPlace": "0",
                  "cashBalance": "1.0000000000",
                  "availableCash": "2.0000000000",
                  "undeliveredAmount": "0",
                  "reservedWithdrawal": "0",
                  "ttbRate": null,
                  "rateDecPlace": null,
                  "jpyChange": "0.0000000000",
                  "currencyCd2": "JPY",
                  "decPlace2": "0"
                },
                {
                  "currencyCd": "USD",
                  "decPlace": "2",
                  "cashBalance": "3.0000000000",
                  "availableCash": "4.0000000000",
                  "undeliveredAmount": "0",
                  "reservedWithdrawal": null,
                  "ttbRate": "108.40",
                  "rateDecPlace": "2",
                  "jpyChange": "0",
                  "currencyCd2": "JPY",
                  "decPlace2": "0"
                }
              ],
              "totalLegalTenderJpy": "0.0000000000"
            }
        """))

        # No token
        self.target._process_cash(None)
        self.assertEqual(0, self.context.requests_post.call_count)
        self.assertEqual(0, self.context.save_balances.call_count)

        # With Token
        self.target._process_cash('tkn')
        self.assertEqual(1, self.context.requests_post.call_count)
        self.assertEqual(1, self.context.save_balances.call_count)

        balances = self.context.save_balances.call_args[0][0]
        self.assertEqual(2, len(balances))

        b = balances[0]
        self.assertEqual('bitpoint', b.bc_site)
        self.assertEqual('CASH', b.bc_acct.name)
        self.assertEqual('JPY', b.bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', b.bc_time.strftime(self.FORMAT))
        self.assertEqual('1.0000000000', b.bc_amnt)

        b = balances[1]
        self.assertEqual('bitpoint', b.bc_site)
        self.assertEqual('CASH', b.bc_acct.name)
        self.assertEqual('USD', b.bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', b.bc_time.strftime(self.FORMAT))
        self.assertEqual('3.0000000000', b.bc_amnt)

        # Error response
        self.context.requests_post = MagicMock(return_value=CryptowelderContext._parse("""
            {
              "error": "invalid_token",
              "error_description": "Invalid access token: hoge"
            }
        """))
        self.target._fetch_token = MagicMock(return_value='hoge')
        self.target._process_cash('tkn')
        self.assertEqual(2, self.context.requests_post.call_count)
        self.assertEqual(1, self.context.save_balances.call_count)

        # No response
        self.context.requests_post = MagicMock(return_value=None)
        self.target._fetch_token = MagicMock(return_value='hoge')
        self.target._process_cash('tkn')
        self.assertEqual(1, self.context.requests_post.call_count)
        self.assertEqual(1, self.context.save_balances.call_count)

    def test__process_coin(self):
        now = datetime.fromtimestamp(1234567890.123456, utc)
        self.context.get_now = MagicMock(return_value=now)
        self.context.save_balances = MagicMock()
        self.context.save_tickers = MagicMock()
        self.context.requests_post = MagicMock(return_value=CryptowelderContext._parse("""
            {
              "resultCode": "0",
              "errors": null,
              "vcBalanceList": [
                {
                  "currencyCd1": "???",
                  "currencyCd2": "JPY",
                  "nominal": "2.0000000000"
                },
                {
                  "currencyCd1": "BTC",
                  "currencyCd2": "???",
                  "nominal": "3.0000000000"
                },
                {
                  "currencyCd1": "BTC",
                  "currencyCd2": "JPY",
                  "nominal": "1.0000000000",
                  "avgInvestmentAmount": "0.0000000000",
                  "valuationPrice": "744418.13",
                  "valuationAmount": "0",
                  "valuationPl": "0.0000000000",
                  "valuationPlRate": "0",
                  "totalInvestmetAmount": "0.0000000000",
                  "c1DecPlace": "4",
                  "c2DecPlace": "0",
                  "currencyPairDecPlace": "2"
                }
              ],
              "totalValuationPl": "0.0000000000",
              "currencyCd2": "JPY",
              "c2DecPlace": "0",
              "totalValuationPlRate": null
            }
        """))

        # No token
        self.target._process_coin(None)
        self.assertEqual(0, self.context.requests_post.call_count)
        self.assertEqual(0, self.context.save_balances.call_count)
        self.assertEqual(0, self.context.save_tickers.call_count)

        # With Token
        self.target._process_coin('tkn')
        self.assertEqual(1, self.context.requests_post.call_count)
        self.assertEqual(1, self.context.save_balances.call_count)
        self.assertEqual(1, self.context.save_tickers.call_count)

        balances = self.context.save_balances.call_args[0][0]
        self.assertEqual(1, len(balances))

        b = balances[0]
        self.assertEqual('bitpoint', b.bc_site)
        self.assertEqual('CASH', b.bc_acct.name)
        self.assertEqual('BTC', b.bc_unit.name)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', b.bc_time.strftime(self.FORMAT))
        self.assertEqual('1.0000000000', b.bc_amnt)

        tickers = self.context.save_tickers.call_args[0][0]
        self.assertEqual(1, len(tickers))

        t = tickers[0]
        self.assertEqual('bitpoint', t.tk_site)
        self.assertEqual('2009-02-13 23:31:30.123456 UTC', t.tk_time.strftime(self.FORMAT))
        self.assertEqual('BTC_JPY', t.tk_code)
        self.assertEqual(None, t.tk_ask)
        self.assertEqual(None, t.tk_bid)
        self.assertEqual('744418.13', t.tk_ltp)

        # Error response
        self.context.requests_post = MagicMock(return_value=CryptowelderContext._parse("""
            {
              "error": "invalid_token",
              "error_description": "Invalid access token: hoge"
            }
        """))
        self.target._fetch_token = MagicMock(return_value='hoge')
        self.target._process_coin('tkn')
        self.assertEqual(2, self.context.requests_post.call_count)
        self.assertEqual(1, self.context.save_balances.call_count)
        self.assertEqual(1, self.context.save_tickers.call_count)

        # No response
        self.context.requests_post = MagicMock(return_value=None)
        self.target._fetch_token = MagicMock(return_value='hoge')
        self.target._process_coin('tkn')
        self.assertEqual(1, self.context.requests_post.call_count)
        self.assertEqual(1, self.context.save_balances.call_count)
        self.assertEqual(1, self.context.save_tickers.call_count)


if __name__ == '__main__':
    main()
