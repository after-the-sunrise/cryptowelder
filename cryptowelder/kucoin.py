from threading import Thread
from time import sleep

from cryptowelder.context import CryptowelderContext, Ticker


class KucoinWelder:
    _ID = 'kucoin'

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://api.kucoin.com')
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

            ticks = self.__context.requests_get(self.__endpoint + '/api/v1/market/allTickers')

            if ticks is None or ticks.get('code') != '200000':
                raise Exception(str(ticks))

            codes = self.__context.get_property(self._ID, 'codes', 'BTC-USDT,ETH-BTC').split(',')

            data = ticks.get('data', {})

            time = self.__context.parse_iso_timestamp(data.get('time') / 1000.0)

            values = []

            for tick in data.get('ticker', []):

                if tick.get('symbol') not in codes:
                    continue

                ticker = Ticker()
                ticker.tk_site = self._ID
                ticker.tk_code = tick.get('symbol')
                ticker.tk_time = time
                ticker.tk_ask = tick.get('sell')
                ticker.tk_bid = tick.get('buy')
                ticker.tk_ltp = tick.get('last')

                values.append(ticker)

            self.__context.save_tickers(values)

            for v in values:
                self.__logger.debug('Ticker : %s', v)

        except Exception as e:

            self.__logger.warn('Ticker Failure : %s - %s', type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = KucoinWelder(context)
    target.run()


if __name__ == '__main__':
    main()
