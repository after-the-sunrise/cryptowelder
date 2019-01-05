from threading import Thread
from time import sleep

from cryptowelder.context import CryptowelderContext, Ticker


class BinanceWelder:
    _ID = 'binance'

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://api.binance.com')
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

            trades = self.__context.requests_get(self.__endpoint + '/api/v3/ticker/price')

            quotes = self.__context.requests_get(self.__endpoint + '/api/v3/ticker/bookTicker')

            if trades is None and quotes is None:
                return

            values = []

            codes = self.__context.get_property(self._ID, 'codes', 'BTCUSDT,ETHBTC,BCCBTC').split(',')

            for code in codes:

                ticker = Ticker()
                ticker.tk_site = self._ID
                ticker.tk_code = code
                ticker.tk_time = now

                for trade in trades if trades is not None else []:
                    if code == trade.get('symbol'):
                        ticker.tk_ltp = trade.get('price')
                        break

                for quote in quotes if quotes is not None else []:
                    if code == quote.get('symbol'):
                        ticker.tk_ask = quote.get('askPrice')
                        ticker.tk_bid = quote.get('bidPrice')
                        break

                values.append(ticker)

            self.__context.save_tickers(values)

            for v in values:
                self.__logger.debug('Ticker : %s', v)

        except Exception as e:

            self.__logger.warn('Ticker Failure : %s - %s', type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = BinanceWelder(context)
    target.run()


if __name__ == '__main__':
    main()
