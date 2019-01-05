from decimal import Decimal
from hashlib import md5, sha256
from hmac import new
from threading import Thread, Lock
from time import sleep

from cryptowelder.context import CryptowelderContext, Ticker, Balance, AccountType, UnitType


class BtcboxWelder:
    _ID = 'btcbox'
    _ZERO = Decimal('0')

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://www.btcbox.co.jp')
        self.__lock = Lock()
        self.__thread = Thread(daemon=False, target=self._loop)

    def run(self):

        self.__thread.start()

    def _join(self):

        self.__thread.join()

    def _loop(self, *, default_interval=20):

        self.__logger.info('Processing : %s', self.__endpoint)

        while not self.__context.is_closed():

            threads = [
                Thread(target=self._process_balance),
            ]

            coins = self.__context.get_property(self._ID, 'coins', 'btc,eth').split(',')

            for coin in coins:
                threads.append(Thread(target=self._process_ticker, args=(coin,)))

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            sleep(float(self.__context.get_property(self._ID, 'interval', default_interval)))

        self.__logger.info('Terminated.')

    def _process_ticker(self, coin):

        try:

            now = self.__context.get_now()

            value = self.__context.requests_get(self.__endpoint + '/api/v1/ticker?coin=' + coin)

            if value is None:
                return

            ticker = Ticker()
            ticker.tk_site = self._ID
            ticker.tk_code = coin
            ticker.tk_time = now
            ticker.tk_ask = value.get('sell')
            ticker.tk_bid = value.get('buy')
            ticker.tk_ltp = value.get('last')

            self.__context.save_tickers([ticker])

            self.__logger.debug('Ticker : %s - %s', coin, ticker)

        except Exception as e:

            self.__logger.warn('Ticker Failure - %s : %s - %s', coin, type(e), e.args)

    def _query_private(self, path, *, parameters={}):

        apikey = self.__context.get_property(self._ID, 'apikey', None)
        secret = self.__context.get_property(self._ID, 'secret', None)

        if apikey is None or secret is None:
            return None

        with self.__lock:
            copied = dict(parameters)
            copied['key'] = apikey
            copied['nonce'] = str(int(self.__context.get_nonce(self._ID).timestamp() * 1000))

            data = ''

            for key, val in copied.items():
                data = data + '&' if data != '' else data
                data = data + key + '=' + val

            encoded = md5()
            encoded.update(str.encode(secret))
            encoded = encoded.hexdigest()
            digest = new(str.encode(encoded), str.encode(data), sha256).hexdigest()

            data = data + '&signature=' + digest

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            }

            return self.__context.requests_post(self.__endpoint + path, headers=headers, data=data)

    def _process_balance(self):

        try:

            now = self.__context.get_now()

            balance = self._query_private('/api/v1/balance')

            if balance is None:
                return

            if not balance.get('result', True):
                raise Exception('Code : %s' % balance.get('code'))

            values = []

            for key, val in balance.items():

                if not key.endswith('_balance'):
                    continue

                ccy = key[: len(key) - len('_balance')]

                try:
                    unit = UnitType[ccy.upper()]
                except KeyError:
                    continue

                value = Balance()
                value.bc_site = self._ID
                value.bc_acct = AccountType.CASH
                value.bc_unit = unit
                value.bc_time = now
                value.bc_amnt = val + balance.get(ccy + '_lock', self._ZERO)

                values.append(value)

            self.__context.save_balances(values)

            for value in values:
                self.__logger.debug('Balance : %s', value)

        except Exception as e:

            self.__logger.warn('Balance Failure : %s - %s', type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = BtcboxWelder(context)
    target.run()


if __name__ == '__main__':
    main()
