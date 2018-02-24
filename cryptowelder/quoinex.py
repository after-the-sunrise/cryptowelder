from datetime import datetime
from decimal import Decimal
from threading import Thread, Lock
from time import sleep

import jwt

from cryptowelder.context import CryptowelderContext, Ticker, Balance, AccountType, UnitType, Transaction, \
    TransactionType


class QuoinexWelder:
    _ID = 'quoinex'
    _ZERO = Decimal('0')
    _SIDE = {'buy': Decimal('+1'), 'sell': Decimal('-1')}

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://api.quoine.com')
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
                Thread(target=self._process_products),
                Thread(target=self._process_cash),
            ]

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            sleep(self.__context.get_property(self._ID, 'interval', 15))

        self.__logger.info('Terminated.')

    def _process_products(self):

        try:

            products = self.__context.requests_get(self.__endpoint + '/products')

            codes = self.__context.get_property(self._ID, 'products', 'BTCJPY,BTCUSD').split(',')

            threads = []

            for product in codes:
                threads.append(Thread(target=self._process_ticker, args=(product, products)))
                threads.append(Thread(target=self._process_transaction, args=(product, products)))

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            self.__logger.debug('Products : %s', codes)

        except Exception as e:

            self.__logger.warn('Products Failure : %s - %s', type(e), e.args)

    def _decimalize(self, data, key):

        value = data.get(key)

        if value is None:
            return None

        if isinstance(value, str):
            return Decimal(value)

        return value

    def _process_ticker(self, code, products):

        try:

            now = self.__context.get_now()

            for product in products:

                if code != product.get('currency_pair_code'):
                    continue

                ticker = Ticker()
                ticker.tk_site = self._ID
                ticker.tk_code = code
                ticker.tk_time = now
                ticker.tk_ask = self._decimalize(product, 'market_ask')
                ticker.tk_bid = self._decimalize(product, 'market_bid')
                ticker.tk_ltp = self._decimalize(product, 'last_traded_price')

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

            payload = {
                "path": path,
                "nonce": str(int(self.__context.get_now().timestamp() * 1000)),
                "token_id": apikey
            }

            signature = jwt.encode(payload, secret, algorithm='HS256')

            headers = {
                'X-Quoine-API-Version': '2',
                'X-Quoine-Auth': signature,
                'Content-Type': "application/json"
            }

            return self.__context.requests_get(self.__endpoint + path, headers=headers)

    def _process_transaction(self, code, products):

        try:

            for product in products:

                if code != product.get('currency_pair_code'):
                    continue

                product_id = product.get('id')

                limit = self.__context.get_property(self._ID, 'tx_limit', 100)

                page = 1

                while True:

                    path = '/executions/me?limit=%s&product_id=%s' % (limit, product_id)

                    if page > 1:
                        path = path + '&page=%s' % page

                    result = self._query_private(path)

                    values = []

                    for execution in result.get('models', []):
                        value = Transaction()
                        value.tx_site = self._ID
                        value.tx_code = code
                        value.tx_type = TransactionType.TRADE
                        value.tx_oid = str(execution.get('id')) + '@' + execution.get('my_side')
                        value.tx_eid = str(execution.get('id'))
                        value.tx_time = datetime.utcfromtimestamp(execution.get('created_at'))
                        value.tx_inst = self._decimalize(execution, 'quantity') * self._SIDE[execution.get('my_side')]
                        value.tx_fund = self._decimalize(execution, 'price') * value.tx_inst * -1

                        values.append(value)

                    self.__logger.debug('Transactions : %s - fetched=[%s] page=[%s]', code, len(values), page)

                    results = self.__context.save_transactions(values)

                    if len(results) <= 0:
                        break

                    page = page + 1

        except Exception as e:

            self.__logger.warn('Transaction Failure - %s : %s - %s', code, type(e), e.args)

    def _process_cash(self):

        try:

            now = self.__context.get_now()

            balances = self._query_private('/accounts/balance')

            values = []

            for balance in balances if balances is not None else []:

                ccy = balance.get('currency')

                try:
                    unit = UnitType[ccy]
                except KeyError:
                    continue

                value = Balance()
                value.bc_site = self._ID
                value.bc_acct = AccountType.CASH
                value.bc_unit = unit
                value.bc_time = now
                value.bc_amnt = balance.get('balance')

                values.append(value)

            self.__context.save_balances(values)

            for value in values:
                self.__logger.debug('Balance : %s', value)

        except Exception as e:

            self.__logger.warn('Balance Failure : %s - %s', type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = QuoinexWelder(context)
    target.run()


if __name__ == '__main__':
    main()
