from hashlib import sha512
from hmac import new
from threading import Thread, Lock
from time import sleep

from cryptowelder.context import CryptowelderContext, Ticker, Balance, AccountType, UnitType, Transaction, \
    TransactionType


class ZaifWelder:
    _ID = 'zaif'

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://api.zaif.jp')
        self.__lock = Lock()
        self.__thread = Thread(daemon=False, target=self._loop)

    def run(self):

        self.__thread.start()

    def _join(self):

        self.__thread.join()

    def _loop(self, *, default_interval=15):

        self.__logger.info('Processing : %s', self.__endpoint)

        while not self.__context.is_closed():

            codes = self.__context.get_property(self._ID, 'codes', 'btc_jpy,bch_btc,eth_btc').split(',')

            threads = [
                Thread(target=self._process_balance)
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

    def _query_private(self, path, *, parameters={}):

        apikey = self.__context.get_property(self._ID, 'apikey', None)
        secret = self.__context.get_property(self._ID, 'secret', None)

        if apikey is None or secret is None:
            return None

        with self.__lock:
            time = self.__context.get_nonce(self._ID).timestamp()

            data = 'nonce=%.3f&method=%s' % (time, path)

            for k, v in parameters.items():
                data = data + ('&%s=%s' % (k, v))

            digest = new(secret.encode(), data.encode(), sha512).hexdigest()

            headers = {
                "key": apikey,
                "sign": digest
            }

            return self.__context.requests_post(self.__endpoint + '/tapi', headers=headers, data=data)

    def _process_balance(self):

        try:

            response = self._query_private('get_info2')

            if response is None:
                return

            if response.get('success', 1) != 1:
                raise Exception(str(response))

            returns = response.get('return', {})

            timestamp = self.__context.parse_iso_timestamp(returns.get('server_time'))

            values = []

            for currency, amount in returns.get('deposit', {}).items():

                try:
                    unit = UnitType[currency.upper()]
                except KeyError:
                    continue

                value = Balance()
                value.bc_site = self._ID
                value.bc_acct = AccountType.CASH
                value.bc_unit = unit
                value.bc_time = timestamp
                value.bc_amnt = amount

                values.append(value)

            self.__context.save_balances(values)

            for value in values:
                self.__logger.debug('Cash : %s', value)

        except Exception as e:

            self.__logger.warn('Cash Failure : %s - %s', type(e), e.args)

    def _process_trades(self, code, *, count=100):

        try:

            params = {
                'currency_pair': code,
                'count': count,
            }

            while True:

                response = self._query_private('trade_history', parameters=params)

                if response is None:
                    break

                if response.get('success', 1) != 1:
                    raise Exception(str(response))

                trades = response.get('return', {})

                if len(trades) <= 0:
                    break

                values = {}

                for i, t in trades.items():
                    params['end_id'] = min(params.get('end_id', int(i)), int(i) - 1)

                    side = t.get('your_action')  # 'ask' -> sell, 'bid' -> buy, 'both' -> cross
                    side = +1 if side == 'ask' else -1 if side == 'bid' else 0

                    values[i] = Transaction()
                    values[i].tx_site = self._ID
                    values[i].tx_code = code
                    values[i].tx_type = TransactionType.TRADE
                    values[i].tx_acct = AccountType.CASH
                    values[i].tx_oid = str(i)
                    values[i].tx_eid = str(i)
                    values[i].tx_time = self.__context.parse_iso_timestamp(t.get('timestamp'))
                    values[i].tx_inst = -side * t.get('amount')
                    values[i].tx_fund = +side * t.get('amount') * t.get('price') - t.get('fee') + t.get('bonus')

                self.__logger.debug('Transactions : %s - fetched=[%s] id=[%s]', code, len(values), params['end_id'])

                results = self.__context.save_transactions(values.values())

                if len(results) <= 0:
                    break

        except Exception as e:

            self.__logger.warn('Trade Failure : %s - %s', type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = ZaifWelder(context)
    target.run()


if __name__ == '__main__':
    main()
