from threading import Thread
from time import sleep

from cryptowelder.context import CryptowelderContext, Ticker


class OandaWelder:
    _ID = 'oanda'

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://api-fxtrade.oanda.com')
        self.__thread = Thread(daemon=False, target=self._loop)

    def run(self):

        self.__thread.start()

    def _join(self):

        self.__thread.join()

    def _loop(self):

        self.__logger.info('Processing : %s', self.__endpoint)

        while not self.__context.is_closed():

            threads = [Thread(target=self._process_ticker)]

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            sleep(self.__context.get_property(self._ID, 'interval', 15))

        self.__logger.info('Terminated.')

    def _process_ticker(self):

        try:

            token = self.__context.get_property(self._ID, 'token', None)

            if token is None:
                return

            pairs = self.__context.get_property(self._ID, 'pairs', 'USD_JPY')

            response = self.__context.requests_get(
                self.__endpoint + '/v1/prices?instruments=' + pairs,
                headers={"Authorization": "Bearer " + token}
            )

            values = []

            for price in response.get('prices', {}) if response is not None else []:
                ticker = Ticker()
                ticker.tk_site = self._ID
                ticker.tk_code = price.get('instrument')
                ticker.tk_time = self.__context.parse_iso_timestamp(price.get('time'))
                ticker.tk_ask = price.get('ask')
                ticker.tk_bid = price.get('bid')
                ticker.tk_ltp = None

                values.append(ticker)

            self.__context.save_tickers(values)

            for v in values:
                self.__logger.debug('Ticker : %s', v)

        except Exception as e:

            self.__logger.warn('Ticker Failure : %s - %s', type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = OandaWelder(context)
    target.run()


if __name__ == '__main__':
    main()
