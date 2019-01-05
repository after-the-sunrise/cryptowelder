from decimal import Decimal
from hashlib import sha256
from hmac import new
from threading import Thread, Lock
from time import sleep
from urllib import parse

from cryptowelder.context import CryptowelderContext, Ticker, Transaction, Balance, AccountType, UnitType, \
    TransactionType


class BitbankWelder:
    _ID = 'bitbank'
    _SIDE = {'buy': Decimal('+1'), 'sell': Decimal('-1')}

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://api.bitbank.cc')
        self.__lock = Lock()
        self.__thread = Thread(daemon=False, target=self._loop)

    def run(self):

        self.__thread.start()

    def _join(self):

        self.__thread.join()

    def _loop(self, *, default_interval=20):

        self.__logger.info('Processing : %s', self.__endpoint)

        while not self.__context.is_closed():

            threads = [
                Thread(target=self._process_balance),
            ]

            pairs = self.__context.get_property(
                self._ID, 'pairs', 'btc_jpy,eth_btc,bcc_btc,bcc_jpy,ltc_btc'
            ).split(',')

            for pair in pairs:
                threads.append(Thread(target=self._process_ticker, args=(pair,)))
                threads.append(Thread(target=self._process_transaction, args=(pair,)))

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            sleep(float(self.__context.get_property(self._ID, 'interval', default_interval)))

        self.__logger.info('Terminated.')

    def _process_ticker(self, pair):

        try:

            now = self.__context.get_now()

            response = self.__context.requests_get('https://public.bitbank.cc/%s/ticker' % pair)

            if response is None:
                return

            if response.get('success', 1) != 1:
                raise Exception(str(response))

            data = response.get('data', {})

            ticker = Ticker()
            ticker.tk_site = self._ID
            ticker.tk_code = pair
            ticker.tk_time = now
            ticker.tk_ask = data.get('sell')
            ticker.tk_bid = data.get('buy')
            ticker.tk_ltp = data.get('last')

            self.__context.save_tickers([ticker])

            self.__logger.debug('Ticker : %s - %s', pair, ticker)

        except Exception as e:

            self.__logger.warn('Ticker Failure - %s : %s - %s', pair, type(e), e.args)

    def _query_private(self, path):

        apikey = self.__context.get_property(self._ID, 'apikey', None)
        secret = self.__context.get_property(self._ID, 'secret', None)

        if apikey is None or secret is None:
            return None

        with self.__lock:
            timestamp = str(int(self.__context.get_nonce(self._ID).timestamp() * 1000))

            data = timestamp + path

            digest = new(str.encode(secret), str.encode(data), sha256).hexdigest()

            headers = {
                "ACCESS-KEY": apikey,
                "ACCESS-NONCE": timestamp,
                "ACCESS-SIGNATURE": digest,
                "Accept": "application/json"
            }

            return self.__context.requests_get(self.__endpoint + path, headers=headers)

    def _process_transaction(self, pair):

        try:

            headers = {
                'pair': pair,
                'count': '100',
                'order': 'desc',
            }

            while True:

                response = self._query_private('/v1/user/spot/trade_history?' + parse.urlencode(headers))

                if response is None:
                    break

                if response.get('success', 1) != 1:
                    raise Exception(str(response))

                trades = response.get('data', {}).get('trades', [])

                values = []

                for trade in trades:
                    amt_base = Decimal(trade.get('amount')) * self._SIDE[trade.get('side')]
                    amt_quote = Decimal(trade.get('price')) * amt_base * -1
                    fee_base = Decimal(trade.get('fee_amount_base', "0"))
                    fee_quote = Decimal(trade.get('fee_amount_quote', "0"))

                    value = Transaction()
                    value.tx_site = self._ID
                    value.tx_code = pair
                    value.tx_type = TransactionType.TRADE
                    value.tx_acct = AccountType.CASH
                    value.tx_oid = str(trade.get('order_id'))
                    value.tx_eid = str(trade.get('trade_id'))
                    value.tx_time = self.__context.parse_iso_timestamp(trade.get('executed_at') / 1000)
                    value.tx_inst = amt_base - fee_base
                    value.tx_fund = amt_quote - fee_quote

                    values.append(value)

                self.__logger.debug('Transactions : %s - fetched=[%s] end=[%s]',
                                    pair, len(values), headers.get('end'))

                results = self.__context.save_transactions(values)

                if len(results) <= 0:
                    break

                headers['end'] = min([trade.get('executed_at') for trade in trades])

        except Exception as e:

            self.__logger.warn('Transaction Failure - %s : %s - %s', pair, type(e), e.args)

    def _process_balance(self):

        try:

            now = self.__context.get_now()

            response = self._query_private('/v1/user/assets')

            if response is None:
                return

            if response.get('success', 1) != 1:
                raise Exception(str(response))

            values = []

            for asset in response.get('data', {}).get('assets', {}):

                ccy = asset.get('asset')

                try:
                    unit = UnitType[ccy.upper()]
                except KeyError:
                    continue

                value = Balance()
                value.bc_site = self._ID
                value.bc_acct = AccountType.CASH
                value.bc_unit = unit
                value.bc_time = now
                value.bc_amnt = asset.get('onhand_amount')

                values.append(value)

            self.__context.save_balances(values)

            for value in values:
                self.__logger.debug('Balance : %s', value)

        except Exception as e:

            self.__logger.warn('Balance Failure : %s - %s', type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = BitbankWelder(context)
    target.run()


if __name__ == '__main__':
    main()
