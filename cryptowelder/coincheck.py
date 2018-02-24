from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from hmac import new
from re import compile
from threading import Thread, Lock
from time import sleep
from urllib.parse import urlencode

from pytz import utc

from cryptowelder.context import CryptowelderContext, Ticker, Balance, AccountType, UnitType, Transaction, \
    TransactionType


class CoincheckWelder:
    _ID = 'coincheck'

    # "yyyy-MM-ddTHH:mm:ss", "yyyy-MM-ddTHH:mm:ss.SSS", "yyyy-MM-ddTHH:mm:ss.SSSZ"
    _TIMEFMT = compile('^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z?$')

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://coincheck.com')
        self.__lock = Lock()
        self.__thread = Thread(daemon=False, target=self._loop)

    def run(self):

        self.__thread.start()

    def _join(self):

        self.__thread.join()

    def _loop(self):

        self.__logger.info('Processing : %s', self.__endpoint)

        while not self.__context.is_closed():

            threads = [
                Thread(target=self._process_ticker),
                Thread(target=self._process_transaction),
                Thread(target=self._process_cash),
                Thread(target=self._process_margin),
            ]

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            sleep(self.__context.get_property(self._ID, 'interval', 15))

        self.__logger.info('Terminated.')

    def _process_ticker(self, *, code='btc_jpy'):

        try:

            now = self.__context.get_now()

            value = self.__context.requests_get(self.__endpoint + '/api/ticker')

            if value is None:
                return

            ticker = Ticker()
            ticker.tk_site = self._ID
            ticker.tk_code = code
            ticker.tk_time = now
            ticker.tk_ask = value.get('ask', None)
            ticker.tk_bid = value.get('bid', None)
            ticker.tk_ltp = value.get('last', None)

            self.__context.save_tickers([ticker])

            self.__logger.debug('Ticker : %s - %s', code, ticker)

        except Exception as e:

            self.__logger.warn('Ticker Failure - %s : %s - %s', code, type(e), e.args)

    def _query_private(self, path):

        apikey = self.__context.get_property(self._ID, 'apikey', None)
        secret = self.__context.get_property(self._ID, 'secret', None)

        if apikey is None or secret is None:
            return None

        with self.__lock:
            sleep(0.001)  # Avoid duplicate nonce

            timestamp = str(int(self.__context.get_now().timestamp() * 1000))

            data = timestamp + self.__endpoint + path

            digest = new(str.encode(secret), str.encode(data), sha256).hexdigest()

            headers = {
                "ACCESS-KEY": apikey,
                "ACCESS-NONCE": timestamp,
                "ACCESS-SIGNATURE": digest,
                "Accept": "application/json"
            }

            return self.__context.requests_get(self.__endpoint + path, headers=headers)

    def _parse_timestamp(self, value):

        if value is None or not self._TIMEFMT.match(value):
            return None

        # 01234567890123456789012
        # yyyy-MM-ddTHH:mm:ss.SSS
        stripped = value[:19]

        local = datetime.strptime(stripped, '%Y-%m-%dT%H:%M:%S')

        return local.replace(tzinfo=utc)

    def _process_transaction(self, *, limit=100):

        try:

            pk = 'starting_after'

            page = {
                'limit': limit,  # Max seems to be 25.
                'order': 'desc',
            }

            while True:

                if pk not in page:

                    result = self._query_private('/api/exchange/orders/transactions');

                    executions = result.get('transactions', []) if result is not None else []

                else:

                    result = self._query_private('/api/exchange/orders/transactions_pagination?' + urlencode(page))

                    executions = result.get('data', []) if result is not None else []

                values = []

                for execution in executions:
                    page[pk] = execution['id'] if pk not in page else min(execution['id'], page[pk])

                    value = Transaction()
                    value.tx_site = self._ID
                    value.tx_code = execution.get('pair')
                    value.tx_type = TransactionType.TRADE
                    value.tx_oid = str(execution.get('order_id'))
                    value.tx_eid = str(execution.get('id'))
                    value.tx_time = self._parse_timestamp(execution.get('created_at'))
                    value.tx_inst = execution.get('funds').get('btc')
                    value.tx_fund = execution.get('funds').get('jpy')

                    values.append(value)

                self.__logger.debug('Transactions : fetched=[%s] sequence=[%s]', len(values), page[pk])

                results = self.__context.save_transactions(values)

                if len(results) <= 0:
                    break

        except Exception as e:

            self.__logger.warn('Transaction Failure : %s - %s', type(e), e.args)

    def _process_cash(self):

        try:

            now = self.__context.get_now()

            balances = self._query_private('/api/accounts/balance')

            if balances is None:
                return

            values = []

            for key, val in balances.items():

                try:
                    unit = UnitType[key.upper()]
                except KeyError:
                    continue

                value = Balance()
                value.bc_site = self._ID
                value.bc_acct = AccountType.CASH
                value.bc_unit = unit
                value.bc_time = now
                value.bc_amnt = Decimal(val) + Decimal(balances.get(key + '_reserved'))

                values.append(value)

            self.__context.save_balances(values)

            for value in values:
                self.__logger.debug('Cash : %s', value)

        except Exception as e:

            self.__logger.warn('Cash Failure : %s - %s', type(e), e.args)

    def _process_margin(self):

        try:

            now = self.__context.get_now()

            balances = self._query_private('/api/accounts/leverage_balance')

            if balances is None:
                return

            values = []

            for key, val in balances.get('margin', {}).items():

                try:
                    unit = UnitType[key.upper()]
                except KeyError:
                    continue

                value = Balance()
                value.bc_site = self._ID
                value.bc_acct = AccountType.MARGIN
                value.bc_unit = unit
                value.bc_time = now
                value.bc_amnt = Decimal(val)

                values.append(value)

            self.__context.save_balances(values)

            for value in values:
                self.__logger.debug('Margin : %s', value)

        except Exception as e:

            self.__logger.warn('Margin Failure : %s - %s', type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = CoincheckWelder(context)
    target.run()


if __name__ == '__main__':
    main()
