from threading import Thread
from time import sleep

from cryptowelder.context import CryptowelderContext, Ticker, Balance, AccountType, UnitType


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

    def _loop(self, *, default_interval=15):

        self.__logger.info('Processing : %s', self.__endpoint)

        while not self.__context.is_closed():

            threads = [
                Thread(target=self._process_ticker),
                Thread(target=self._process_balance),
            ]

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            sleep(float(self.__context.get_property(self._ID, 'interval', default_interval)))

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

    def _process_balance(self):

        try:

            token = self.__context.get_property(self._ID, 'token', None)

            if token is None:
                return

            now = self.__context.get_now()

            accounts = self.__context.requests_get(
                self.__endpoint + '/v1/accounts',
                headers={"Authorization": "Bearer " + token}
            )

            values = []

            for account in accounts.get('accounts', {}) if accounts is not None else []:

                details = self.__context.requests_get(
                    self.__endpoint + '/v1/accounts/%s' % account.get('accountId'),
                    headers={"Authorization": "Bearer " + token}
                )

                if details is None:
                    continue

                try:
                    unit = UnitType[details.get('accountCurrency')]
                except KeyError:
                    continue

                value = Balance()
                value.bc_site = self._ID
                value.bc_acct = AccountType.MARGIN
                value.bc_unit = unit
                value.bc_time = now
                value.bc_amnt = details.get('balance')

                values.append(value)

            self.__context.save_balances(values)

            for value in values:
                self.__logger.debug('Balance : %s', value)

        except Exception as e:

            self.__logger.warn('Balance Failure : %s - %s', type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = OandaWelder(context)
    target.run()


if __name__ == '__main__':
    main()
