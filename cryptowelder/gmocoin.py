from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from hmac import new
from threading import Thread, Lock
from time import sleep
from urllib.parse import urlencode

from cryptowelder.context import CryptowelderContext, Ticker, Balance, AccountType, UnitType, Transaction, \
    TransactionType


class GmoCoinWelder:
    _ID = 'gmocoin'
    _ZERO = Decimal('0')
    _SIDE = {'BUY': Decimal('+1'), 'SELL': Decimal('-1')}

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

            codes = self.__context.get_property(self._ID, 'codes', 'BTC,ETH').split(',')

            threads = [
                Thread(target=self._process_assets),
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
                now = self.__context.get_nonce(self._ID, delta=timedelta(seconds=2))
                response = self.__context.requests_get(self.__endpoint + '/public/v1/ticker?symbol=' + code);

            if response is None or response.get('status', None) != 0 or not isinstance(response.get('data'), list):
                raise Exception(str(response))

            values = []

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

                values.append(ticker)

                self.__logger.debug('Ticker : %s - %s', code, ticker)

            self.__context.save_tickers(values)

        except Exception as e:

            self.__logger.warn('Ticker Failure - %s : %s - %s', code, type(e), e.args)

    def _query_private(self, path, *, query='', body=''):

        apikey = self.__context.get_property(self._ID, 'apikey', None)
        secret = self.__context.get_property(self._ID, 'secret', None)

        if apikey is None or secret is None:
            return None

        with self.__lock:
            time = str(int(self.__context.get_nonce(self._ID, delta=timedelta(seconds=2)).timestamp() * 1000))

            payload = ''.join([time, 'GET', path, body])

            digest = new(secret.encode(), payload.encode(), sha256).hexdigest()

            headers = {
                "API-KEY": apikey,
                "API-TIMESTAMP": time,
                "API-SIGN": digest
            }

            return self.__context.requests_get(self.__endpoint + '/private' + path + query, headers=headers, data=body)

    def _process_assets(self):

        try:

            now = self.__context.get_now()

            response = self._query_private('/v1/account/assets')

            if response is None or response.get('status', None) != 0 or not isinstance(response.get('data'), list):
                raise Exception(str(response))

            values = []

            for asset in response.get('data'):

                try:
                    unit = UnitType[asset.get('symbol', '').upper()]
                except KeyError:
                    continue

                value = Balance()
                value.bc_site = self._ID
                value.bc_acct = AccountType.CASH
                value.bc_unit = unit
                value.bc_time = now
                value.bc_amnt = asset.get('amount')

                values.append(value)

            self.__context.save_balances(values)

            for value in values:
                self.__logger.debug('Asset : %s', value)

        except Exception as e:

            self.__logger.warn('Assets Failure : %s - %s', type(e), e.args)

    def _process_trades(self, code, *, count=100, page=1):

        try:

            params = {
                'symbol': code,
                'count': count,
                'page': page
            }

            while True:

                response = self._query_private('/v1/latestExecutions', query='?' + urlencode(params));

                if response is None or response.get('status', None) != 0 or not isinstance(response.get('data'), dict):
                    raise Exception(str(response))

                values = []

                for execution in response.get('data').get('list', []):
                    sign = self._SIDE.get(execution.get('side'), self._ZERO)
                    prce = Decimal(execution.get('price', '0'))
                    size = Decimal(execution.get('size', '0'))
                    comm = Decimal(execution.get('fee', '0'))

                    value = Transaction()
                    value.tx_site = self._ID
                    value.tx_code = execution.get('symbol')
                    value.tx_type = TransactionType.TRADE
                    value.tx_acct = AccountType.CASH if '_' not in code else AccountType.MARGIN
                    value.tx_oid = str(execution.get('orderId'))
                    value.tx_eid = str(execution.get('executionId'))
                    value.tx_time = self.__context.parse_iso_timestamp(execution.get('timestamp'))
                    value.tx_inst = size * +sign
                    value.tx_fund = size * -sign * prce - comm

                    values.append(value)

                self.__logger.debug('Transactions : %s - fetched=[%s] page=[%s]', code, len(values), params['page'])

                results = self.__context.save_transactions(values)

                if len(results) <= 0:
                    break

                params['page'] = params['page'] + 1

        except Exception as e:

            self.__logger.warn('Transaction Failure : %s - %s - %s', code, type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = GmoCoinWelder(context)
    target.run()


if __name__ == '__main__':
    main()
