from threading import Thread
from time import sleep

from cryptowelder.context import CryptowelderContext, Ticker


class PoloniexWelder:
    _ID = 'poloniex'

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://poloniex.com')
        self.__thread = Thread(daemon=False, target=self._loop)

    def run(self):

        self.__thread.start()

    def _join(self):

        self.__thread.join()

    def _loop(self, *, default_interval=20):

        self.__logger.info('Processing : %s', self.__endpoint)

        while not self.__context.is_closed():

            threads = [
                Thread(target=self._process_ticker)
            ]

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            sleep(float(self.__context.get_property(self._ID, 'interval', default_interval)))

        self.__logger.info('Terminated.')

    def _process_ticker(self):

        try:

            now = self.__context.get_now()

            response = self.__context.requests_get(self.__endpoint + '/public?command=returnTicker')

            if response is None:
                return

            values = []

            codes = self.__context.get_property(self._ID, 'codes', 'USDT_BTC,BTC_BCH,BTC_ETH').split(',')

            for code in codes:

                value = response.get(code)

                if value is None:
                    continue

                ticker = Ticker()
                ticker.tk_site = self._ID
                ticker.tk_code = code
                ticker.tk_time = now
                ticker.tk_ask = value.get('lowestAsk')
                ticker.tk_bid = value.get('highestBid')
                ticker.tk_ltp = value.get('last')

                values.append(ticker)

            self.__context.save_tickers(values)

            for v in values:
                self.__logger.debug('Ticker : %s', v)

        except Exception as e:

            self.__logger.warn('Ticker Failure : %s - %s', type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = PoloniexWelder(context)
    target.run()


if __name__ == '__main__':
    main()
