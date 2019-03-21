from base64 import b64encode
from decimal import Decimal
from hashlib import sha256
from hmac import new
from threading import Thread, Lock
from time import sleep
from urllib import parse

from cryptowelder.context import CryptowelderContext, Ticker, UnitType, Balance, AccountType, Transaction, \
    TransactionType


class HuobiJapanWelder:
    _ID = 'huobijp'
    _ZERO = Decimal('0')
    _SIDE = {'buy': Decimal('+1'), 'sell': Decimal('-1')}

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://api-cloud.huobi.co.jp')
        self.__lock = Lock()
        self.__thread = Thread(daemon=False, target=self._loop)

    def run(self):

        self.__thread.start()

    def _join(self):

        self.__thread.join()

    def _loop(self, *, default_interval=20):

        self.__logger.info('Processing : %s', self.__endpoint)

        while not self.__context.is_closed():

            threads = []

            accounts = self.__context.get_property(self._ID, 'accounts', '').split(',')

            for account in accounts:
                threads.append(Thread(target=self._process_balance, args=(account,)))

            symbols = self.__context.get_property(self._ID, 'symbols', 'btcjpy').split(',')

            for symbol in symbols:
                threads.append(Thread(target=self._process_ticker, args=(symbol,)))
                threads.append(Thread(target=self._process_transaction, args=(symbol,)))

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            sleep(float(self.__context.get_property(self._ID, 'interval', default_interval)))

        self.__logger.info('Terminated.')

    def _process_ticker(self, symbol):

        try:

            now = self.__context.get_now()

            value = self.__context.requests_get(
                self.__endpoint + '/market/detail/merged?symbol=' + symbol)

            if value is None or "tick" not in value:
                return

            ticker = Ticker()
            ticker.tk_site = self._ID
            ticker.tk_code = symbol
            ticker.tk_time = self.__context.parse_iso_timestamp(value.get('ts') / 1000.0)
            ticker.tk_ask = value.get('tick').get('ask', [None])[0]
            ticker.tk_bid = value.get('tick').get('bid', [None])[0]
            ticker.tk_ltp = value.get('tick').get('close')

            self.__context.save_tickers([ticker])

            self.__logger.debug('Ticker : %s - %s', symbol, ticker)

        except Exception as e:

            self.__logger.warn('Ticker Failure - %s : %s - %s', symbol, type(e), e.args)

    def _query_private(self, path, *, parameters={}):

        apikey = self.__context.get_property(self._ID, 'apikey', None)
        secret = self.__context.get_property(self._ID, 'secret', None)

        if apikey is None or secret is None:
            return None

        copied = dict(parameters)
        copied['AccessKeyId'] = apikey
        copied['SignatureMethod'] = 'HmacSHA256'
        copied['SignatureVersion'] = '2'
        copied['Timestamp'] = self.__context.get_now().strftime('%Y-%m-%dT%H:%M:%S')
        joined = '&'.join(sorted([k + '=' + parse.quote(str(v).encode('UTF-8')) for k, v in copied.items()]))

        hmac_data = '\n'.join(('GET', parse.urlparse(self.__endpoint).netloc, path, joined))
        hmac_byte = new(str.encode(secret), str.encode(hmac_data), sha256).digest()
        hmac_b64s = b64encode(hmac_byte).decode('UTF-8')

        target = path + '?' + joined + '&Signature=' + parse.quote(hmac_b64s)

        headers = {
            'Content-Type': 'application/json'
        }

        return self.__context.requests_get(self.__endpoint + target, headers=headers)

    def _process_balance(self, account):

        try:

            now = self.__context.get_now()

            response = self._query_private('/v1/account/accounts/' + account + '/balance')

            if response is None or response.get('status') != 'ok' or 'data' not in response:
                return

            amounts = {}

            for balance in response.get('data').get('list', []):

                ccy = balance.get('currency')

                try:
                    unit = UnitType[ccy.upper()]
                except KeyError:
                    continue

                amounts[unit] = amounts.get(unit, self._ZERO) + Decimal(balance.get('balance', '0'))

            values = []

            for unit, amount in amounts.items():
                value = Balance()
                value.bc_site = self._ID
                value.bc_acct = AccountType.CASH
                value.bc_unit = unit
                value.bc_time = now
                value.bc_amnt = amount
                values.append(value)

            self.__context.save_balances(values)

            for value in values:
                self.__logger.debug('Balance : [%s] %s', account, value)

        except Exception as e:

            self.__logger.warn('Balance Failure : [%s] %s - %s', account, type(e), e.args)

    def _process_transaction(self, symbol):

        try:

            parameters = {'symbol': symbol}

            while True:

                response = self._query_private('/v1/order/matchresults', parameters=parameters)

                if response is None or response.get('status') != 'ok' or 'data' not in response:
                    break

                values = []

                for trade in response.get('data', []):
                    side_flag = trade.get('type', 'n/a').split('-')[0].lower()
                    side_sign = self._SIDE.get(side_flag, self._ZERO)

                    fee_base = self._ZERO  # Decimal(trade.get('filled-fees', "0"))
                    amt_base = Decimal(trade.get('filled-amount')) * side_sign
                    amt_quote = Decimal(trade.get('price')) * amt_base * -1

                    value = Transaction()
                    value.tx_site = self._ID
                    value.tx_code = symbol
                    value.tx_type = TransactionType.TRADE
                    value.tx_acct = AccountType.CASH
                    value.tx_oid = str(trade.get('order-id'))
                    value.tx_eid = str(trade.get('id'))
                    value.tx_time = self.__context.parse_iso_timestamp(trade.get('created-at') / 1000)
                    value.tx_inst = amt_base - fee_base
                    value.tx_fund = amt_quote

                    values.append(value)

                self.__logger.debug('Transactions : %s - fetched=[%s] end=[%s]', symbol, len(values),
                                    parameters.get('from'))

                results = self.__context.save_transactions(values)

                if len(results) <= 0:
                    break

                parameters['from'] = min([Decimal(t.get('id')) for t in response.get('data', [])])

        except Exception as e:

            self.__logger.warn('Transaction Failure - %s : %s - %s', symbol, type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = HuobiJapanWelder(context)
    target.run()


if __name__ == '__main__':
    main()
