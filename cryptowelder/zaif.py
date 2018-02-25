from hashlib import sha512
from hmac import new
from threading import Thread, Lock
from time import sleep

from cryptowelder.context import CryptowelderContext, Ticker, Balance, AccountType, UnitType


class ZaifWelder:
    _ID = 'zaif'

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://api.zaif.jp')
        self.__lock = Lock()
        self.__thread = Thread(daemon=False, target=self._loop)

    def run(self):

        self.__thread.start()

    def _join(self):

        self.__thread.join()

    def _loop(self):

        self.__logger.info('Processing : %s', self.__endpoint)

        while not self.__context.is_closed():

            codes = self.__context.get_property(self._ID, 'codes', 'btc_jpy,bch_btc,eth_btc').split(',')

            threads = [Thread(target=self._process_ticker, args=(code,)) for code in codes]

            threads.append(Thread(target=self._process_balance))

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            sleep(float(self.__context.get_property(self._ID, 'interval', 15)))

        self.__logger.info('Terminated.')

    def _process_ticker(self, code):

        try:

            now = self.__context.get_now()

            response = self.__context.requests_get(self.__endpoint + '/api/1/ticker/' + code)

            if response is None:
                return

            ticker = Ticker()
            ticker.tk_site = self._ID
            ticker.tk_code = code
            ticker.tk_time = now
            ticker.tk_ask = response.get('ask')
            ticker.tk_bid = response.get('bid')
            ticker.tk_ltp = response.get('last')

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

            time = self.__context.get_now().timestamp()

            data = 'nonce=%.3f&method=%s' % (time, path)

            digest = new(secret.encode(), data.encode(), sha512).hexdigest()

            headers = {
                "key": apikey,
                "sign": digest
            }

            return self.__context.requests_post(self.__endpoint + '/tapi', headers=headers, data=data)

    def _process_balance(self):

        try:

            response = self._query_private('get_info2')

            if response is None or response.get('success', 1) != 1:
                return

            returns = response.get('return', {})

            timestamp = self.__context.parse_iso_timestamp(returns.get('server_time'))

            values = []

            for currency, amount in returns.get('funds', {}).items():

                try:
                    unit = UnitType[currency.upper()]
                except KeyError:
                    continue

                value = Balance()
                value.bc_site = self._ID
                value.bc_acct = AccountType.CASH
                value.bc_unit = unit
                value.bc_time = timestamp
                value.bc_amnt = amount

                values.append(value)

            self.__context.save_balances(values)

            for value in values:
                self.__logger.debug('Cash : %s', value)

        except Exception as e:

            self.__logger.warn('Cash Failure : %s - %s', type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = ZaifWelder(context)
    target.run()


if __name__ == '__main__':
    main()
