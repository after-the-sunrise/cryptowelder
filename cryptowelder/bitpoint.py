from threading import Thread
from time import sleep

from cryptowelder.context import CryptowelderContext, Ticker, Balance, AccountType, UnitType


class BitpointWelder:
    _ID = 'bitpoint'
    _TOKEN = 'access_token'
    _SUCCESS = '0'
    _FAILURE = '1'

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://public.bitpoint.co.jp')
        self.__thread = Thread(daemon=False, target=self._loop)
        self.__token = None

    def run(self):

        self.__thread.start()

    def _join(self):

        self.__thread.join()

    def _loop(self, *, default_interval=15):

        self.__logger.info('Processing : %s', self.__endpoint)

        while not self.__context.is_closed():

            token = self._fetch_token()

            threads = [
                Thread(target=self._process_cash, args=(token,)),
                Thread(target=self._process_coin, args=(token,)),
            ]

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            sleep(float(self.__context.get_property(self._ID, 'interval', default_interval)))

        self.__logger.info('Terminated.')

    def _fetch_token(self, *, force=False):

        token = self.__token

        if token is None or force:

            token = None

            apiKey = self.__context.get_property(self._ID, 'apikey', None)
            secret = self.__context.get_property(self._ID, 'secret', None)

            if apiKey is not None and secret is not None:

                params = {
                    'username': apiKey,
                    'password': secret
                }

                try:

                    response = self.__context.requests_get(self.__endpoint + '/bpj-api/login', params=params)

                    if response is None:
                        raise Exception(response)

                    token = response.get('access_token')

                    self.__logger.debug('Token Success : %s - %s (force=%s)', apiKey, token, force)

                except Exception as e:

                    self.__logger.warn('Token Failure - %s : %s - %s', apiKey, type(e), e.args)

            self.__token = token

        return token

    def _process_cash(self, token, *, retry=True):

        if token is None:
            return

        try:

            params = {
                self._TOKEN: token
            }

            headers = {
                'Content-Type': 'application/json'
            }

            path = self.__endpoint + '/bpj-api/rc_balance_list'

            now = self.__context.get_now()

            response = self.__context.requests_post(path, params=params, headers=headers, json={})

            if response is None:
                return

            if response.get('resultCode', self._FAILURE) != self._SUCCESS:
                raise Exception(response)

            values = []

            for balance in response.get('rcBalanceList', []):

                currency = balance.get('currencyCd')

                try:
                    unit = UnitType[currency.upper()]
                except KeyError:
                    continue

                value = Balance()
                value.bc_site = self._ID
                value.bc_acct = AccountType.CASH
                value.bc_unit = unit
                value.bc_time = now
                value.bc_amnt = balance.get('cashBalance')

                values.append(value)

            self.__context.save_balances(values)

            for value in values:
                self.__logger.debug('Cash : %s', value)

        except Exception as e:

            if retry:

                token = self._fetch_token(force=True)

                self._process_cash(token, retry=False)

            else:

                self.__logger.warn('Cash Failure : %s - %s', type(e), e.args)

    def _process_coin(self, token, *, retry=True):

        if token is None:
            return

        try:

            params = {
                self._TOKEN: token
            }

            headers = {
                'Content-Type': 'application/json'
            }

            path = self.__endpoint + '/bpj-api/vc_balance_list'

            json = {
                "calcCurrencyCd": self.__context.get_property(self._ID, 'calc', 'JPY'),
                "currencyCdList": self.__context.get_property(self._ID, 'coins', 'BTC').split(',')
            }

            now = self.__context.get_now()

            response = self.__context.requests_post(path, params=params, headers=headers, json=json)

            if response is None:
                return

            if response.get('resultCode', self._FAILURE) != self._SUCCESS:
                raise Exception(response)

            balances = []

            tickers = []

            for entry in response.get('vcBalanceList', []):

                currency1 = entry.get('currencyCd1')
                currency2 = entry.get('currencyCd2')

                try:
                    unit1 = UnitType[currency1.upper()]
                except KeyError:
                    continue

                try:
                    unit2 = UnitType[currency2.upper()]
                except KeyError:
                    continue

                balance = Balance()
                balance.bc_site = self._ID
                balance.bc_acct = AccountType.CASH
                balance.bc_unit = unit1
                balance.bc_time = now
                balance.bc_amnt = entry.get('nominal')
                balances.append(balance)

                ticker = Ticker()
                ticker.tk_site = self._ID
                ticker.tk_code = unit1.name + '_' + unit2.name
                ticker.tk_time = now
                ticker.tk_ltp = entry.get('valuationPrice')
                tickers.append(ticker)

            self.__context.save_balances(balances)

            for balance in balances:
                self.__logger.debug('Coin : %s', balance)

            self.__context.save_tickers(tickers)

            for ticker in tickers:
                self.__logger.debug('Tick : %s', ticker)

        except Exception as e:

            if retry:

                token = self._fetch_token(force=True)

                self._process_coin(token, retry=False)

            else:

                self.__logger.warn('Coin Failure : %s - %s', type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = BitpointWelder(context)
    target.run()


if __name__ == '__main__':
    main()
