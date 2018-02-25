from threading import Thread
from time import sleep

from cryptowelder.context import CryptowelderContext, Ticker


class BitmexWelder:
    _ID = 'bitmex'

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://www.bitmex.com')
        self.__thread = Thread(daemon=False, target=self._loop)

    def run(self):

        self.__thread.start()

    def _join(self):

        self.__thread.join()

    def _loop(self):

        self.__logger.info('Processing : %s', self.__endpoint)

        while not self.__context.is_closed():

            threads = [
                Thread(target=self._process_ticker)
            ]

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            sleep(float(self.__context.get_property(self._ID, 'interval', 15)))

        self.__logger.info('Terminated.')

    def _process_ticker(self):

        try:

            response = self.__context.requests_get(self.__endpoint + '/api/v1/instrument/activeAndIndices')

            if response is None:
                return

            values = []

            codes = self.__context.get_property(
                self._ID, 'codes', '.BXBT'
            ).split(',')

            references = self.__context.get_property(
                self._ID, 'references', '.BXBT,.BXBT30M,.ETHXBT30M,.BCHXBT30M'
            ).split(',')

            for instrument in response:

                code = instrument.get('symbol')

                reference = instrument.get('referenceSymbol')

                state = instrument.get('state')

                if (
                        code is None or code not in codes
                ) and (
                        reference is None or reference not in references or state == 'Unlisted'
                ):
                    continue

                ticker = Ticker()
                ticker.tk_site = self._ID
                ticker.tk_code = code
                ticker.tk_time = self.__context.parse_iso_timestamp(instrument.get('timestamp'))
                ticker.tk_ask = instrument.get('askPrice')
                ticker.tk_bid = instrument.get('bidPrice')
                ticker.tk_ltp = instrument.get('lastPrice')

                values.append(ticker)

            self.__context.save_tickers(values)

            for v in values:
                self.__logger.debug('Ticker : %s', v)

        except Exception as e:

            self.__logger.warn('Ticker Failure : %s - %s', type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = BitmexWelder(context)
    target.run()


if __name__ == '__main__':
    main()
