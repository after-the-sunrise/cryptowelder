from threading import Thread
from time import sleep

from cryptowelder.context import CryptowelderContext, Ticker


class ZaifWelder:
    _ID = 'zaif'

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://api.zaif.jp')
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


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = ZaifWelder(context)
    target.run()


if __name__ == '__main__':
    main()
