from datetime import timedelta
from hashlib import sha256
from hmac import new
from threading import Thread, Lock
from time import sleep

from cryptowelder.context import CryptowelderContext, Ticker


class GmoCoinWelder:
    _ID = 'gmocoin'

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://api.coin.z.com')
        self.__lock = Lock()
        self.__thread = Thread(daemon=False, target=self._loop)

    def run(self):

        self.__thread.start()

    def _join(self):

        self.__thread.join()

    def _loop(self, *, default_interval=20):

        self.__logger.info('Processing : %s', self.__endpoint)

        while not self.__context.is_closed():

            codes = self.__context.get_property(self._ID, 'codes', 'BTC_JPY,ETH_JPY').split(',')

            threads = [
                Thread(target=self._process_balance)
            ]

            for code in codes:
                threads.append(Thread(target=self._process_ticker, args=(code,)))
                threads.append(Thread(target=self._process_trades, args=(code,)))

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            sleep(float(self.__context.get_property(self._ID, 'interval', default_interval)))

        self.__logger.info('Terminated.')

    def _process_ticker(self, code):

        try:

            with self.__lock:
                now = self.__context.get_nonce(self._ID, delta=timedelta(seconds=1)).timestamp()
                response = self.__context.requests_get(self.__endpoint + '/public/v1/ticker?symbol=' + code);

            if response is None or response.get('status', None) != 0 or not isinstance(response.get('data'), list):
                return

            for data in response.get('data'):

                if data.get('symbol') != code:
                    continue

                ticker = Ticker()
                ticker.tk_site = self._ID
                ticker.tk_code = code
                ticker.tk_time = now
                ticker.tk_ask = data.get('ask')
                ticker.tk_bid = data.get('bid')
                ticker.tk_ltp = data.get('last')

                self.__context.save_tickers([ticker])
                self.__logger.debug('Ticker : %s - %s', code, ticker)

        except Exception as e:

            self.__logger.warn('Ticker Failure - %s : %s - %s', code, type(e), e.args)

    def _query_private(self, path, *, parameters={}, body=''):

        apikey = self.__context.get_property(self._ID, 'apikey', None)
        secret = self.__context.get_property(self._ID, 'secret', None)

        if apikey is None or secret is None:
            return None

        with self.__lock:

            time = self.__context.get_nonce(self._ID, delta=timedelta(seconds=1)).timestamp()

            params = ''

            for k, v in parameters.items():
                params = params + ('&%s=%s' % (k, v))

            full_path = path + '?' + params if len(params) > 0 else path

            digest = new(secret.encode(), ''.join([str(time), 'GET', full_path, body]).encode(), sha256).hexdigest()

            headers = {
                "API-KEY": apikey,
                "API-TIMESTAMP": time,
                "API-SIGN": digest
            }

            return self.__context.requests_get(self.__endpoint + '/private' + full_path, headers=headers, data=body)

    def _process_balance(self):
        pass  # TODO

    def _process_trades(self, code, *, count=100):
        pass  # TODO


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = GmoCoinWelder(context)
    target.run()


if __name__ == '__main__':
    main()
