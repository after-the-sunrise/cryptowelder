from threading import Thread
from time import sleep

from cryptowelder.context import CryptowelderContext, Ticker


class BitfinexWelder:
    _ID = 'bitfinex'

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://api.bitfinex.com')
        self.__thread = Thread(daemon=False, target=self._loop)

    def run(self):

        self.__thread.start()

    def _join(self):

        self.__thread.join()

    def _loop(self, *, default_interval=15):

        self.__logger.info('Processing : %s', self.__endpoint)

        while not self.__context.is_closed():

            codes = self.__context.get_property(self._ID, 'codes', 'btcusd,bchbtc,ethbtc').split(',')

            threads = [Thread(target=self._process_ticker, args=(code,)) for code in codes]

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            sleep(float(self.__context.get_property(self._ID, 'interval', default_interval)))

        self.__logger.info('Terminated.')

    def _process_ticker(self, code):

        try:

            response = self.__context.requests_get(self.__endpoint + '/v1/pubticker/' + code)

            if response is None:
                return

            ticker = Ticker()
            ticker.tk_site = self._ID
            ticker.tk_code = code
            ticker.tk_time = self.__context.parse_iso_timestamp(response.get('timestamp'))
            ticker.tk_ask = response.get('ask')
            ticker.tk_bid = response.get('bid')
            ticker.tk_ltp = response.get('last_price')

            self.__context.save_tickers([ticker])

            self.__logger.debug('Ticker : %s - %s', code, ticker)

        except Exception as e:

            self.__logger.warn('Ticker Failure - %s : %s - %s', code, type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = BitfinexWelder(context)
    target.run()


if __name__ == '__main__':
    main()
