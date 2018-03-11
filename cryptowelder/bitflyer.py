from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from hmac import new
from re import compile
from threading import Thread
from time import sleep

from pytz import utc

from cryptowelder.context import CryptowelderContext, \
    Product, Ticker, Position, Balance, AccountType, UnitType, Transaction, TransactionType


class BitflyerWelder:
    _ID = 'bitflyer'
    _ZERO = Decimal('0')
    _SIDE = {'BUY': Decimal('+1'), 'SELL': Decimal('-1')}

    # "BTCJPYddMMMyyyy"
    _FUTURES = compile('^[A-Z]{6}[0-9]{2}[A-Z]{3}[0-9]{4}$')
    _MONTHS = {value: i for i, value in enumerate(
        [None, 'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    )}

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = self.__context.get_property(self._ID, 'endpoint', 'https://api.bitflyer.jp')
        self.__thread = Thread(daemon=False, target=self._loop)

    def run(self):

        self.__thread.start()

    def _join(self):

        self.__thread.join()

    def _loop(self):

        self.__logger.info('Processing : %s', self.__endpoint)

        while not self.__context.is_closed():

            threads = [
                Thread(target=self._process_markets),
                Thread(target=self._process_cash),
                Thread(target=self._process_margin),
            ]

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            sleep(float(self.__context.get_property(self._ID, 'interval', 15)))

        self.__logger.info('Terminated.')

    def _process_markets(self):

        try:

            # [{"product_code": "BTCJPYddMMMyyyy", "alias": "BTCJPY_MAT1WK"}, ...]
            markets = self.__context.requests_get(self.__endpoint + '/v1/markets')

            threads = []

            codes = []

            for market in markets if markets is not None else []:
                code = market.get('product_code')

                codes.append(code)

                threads.append(Thread(target=self._process_product, args=(code,)))

                threads.append(Thread(target=self._process_ticker, args=(code,)))

                threads.append(Thread(target=self._process_position, args=(code,)))

                threads.append(Thread(target=self._process_transaction, args=(code,)))

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            self.__logger.debug('Markets : %s', codes)

        except Exception as e:

            self.__logger.warn('Market Failure : %s - %s', type(e), e.args)

    def _process_product(self, code):

        try:

            expiry = self._parse_expiry(code)

            if expiry is None:
                return

            product = Product()
            product.pr_site = self._ID
            product.pr_code = code
            product.pr_inst = code
            product.pr_fund = UnitType.JPY.name
            product.pr_disp = 'BF %s' % expiry.strftime('%Y%m%d')
            product.pr_expr = expiry

            self.__context.save_products([product])

            self.__logger.debug('Product : %s - %s', code, product)

        except Exception as e:

            self.__logger.warn('Product Failure - %s : %s - %s', code, type(e), e.args)

    def _process_ticker(self, code):

        try:

            special_quotation = self._fetch_special_quotation(code)

            ticker = Ticker()
            ticker.tk_site = self._ID
            ticker.tk_code = code

            if special_quotation is not None:

                ticker.tk_time = self._parse_expiry(code)
                ticker.tk_ask = None
                ticker.tk_bid = None
                ticker.tk_ltp = special_quotation

            else:

                json = self.__context.requests_get(self.__endpoint + '/v1/ticker?product_code=' + code)
                json = json if json is not None else {}

                ticker.tk_time = self.__context.parse_iso_timestamp(json.get('timestamp'))
                ticker.tk_ask = json.get('best_ask')
                ticker.tk_bid = json.get('best_bid')
                ticker.tk_ltp = json.get('ltp')

            self.__context.save_tickers([ticker])

            self.__logger.debug('Ticker : %s - %s', code, ticker)

        except Exception as e:

            self.__logger.warn('Ticker Failure - %s : %s - %s', code, type(e), e.args)

    def __is_futures(self, code):
        return code is not None and self._FUTURES.match(code)

    def _fetch_special_quotation(self, code):

        if not self.__is_futures(code):
            return None

        json = self.__context.requests_get(self.__endpoint + '/v1/getboardstate?product_code=' + code)

        return json.get('data', json).get('special_quotation') if json is not None else None

    def _parse_expiry(self, code):

        if not self.__is_futures(code):
            return None

        # BTCJPYddMMMyyyy
        # 012345678901234
        d = code[6:8]
        m = code[8:11]
        y = code[11:15]

        # MMM -> MM
        d = int(d)
        m = self._MONTHS.get(m)
        y = int(y)

        if m is None:
            return None

        # Avoid using "Asia/Tokyo", pytz (2018.3) is 19 minutes off.
        return datetime(year=y, month=m, day=d, hour=16 - 9, minute=0, tzinfo=utc)

    def _query_private(self, path):

        apikey = self.__context.get_property(self._ID, 'apikey', None)
        secret = self.__context.get_property(self._ID, 'secret', None)

        if apikey is None or secret is None:
            return None

        timestamp = str(int(self.__context.get_now().timestamp() * 1000))

        data = timestamp + "GET" + path

        digest = new(str.encode(secret), str.encode(data), sha256).hexdigest()

        headers = {
            "ACCESS-KEY": apikey,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-SIGN": digest,
            "Content-Type": "application/json"
        }

        return self.__context.requests_get(self.__endpoint + path, headers=headers)

    def _process_position(self, code):

        try:

            if 'FX_BTC_JPY' != code and not self.__is_futures(code):
                return

            now = self.__context.get_now()
            amount_inst = self._ZERO
            amount_fund = self._ZERO

            positions = self._query_private('/v1/me/getpositions?product_code=' + code)

            for position in positions if positions is not None else []:
                # Instrument Position
                sign = self._SIDE.get(position.get('side'), self._ZERO)
                inst = position.get('size', self._ZERO) * sign
                amount_inst = amount_inst + inst

                # P&L
                pnl = position.get('pnl', self._ZERO)
                swp = position.get('swap_point_accumulate', self._ZERO)
                cmm = position.get('commission', self._ZERO)
                amount_fund = amount_fund + pnl - swp - cmm

            position = Position()
            position.ps_site = self._ID
            position.ps_code = code
            position.ps_time = now
            position.ps_inst = amount_inst
            position.ps_fund = amount_fund

            self.__context.save_positions([position])

            self.__logger.debug('Position : %s - %s', code, position)

        except Exception as e:

            self.__logger.warn('Position Failure - %s : %s - %s', code, type(e), e.args)

    def _process_transaction(self, code):

        try:

            is_cash = 'FX_BTC_JPY' != code and not self.__is_futures(code)

            limit = int(self.__context.get_property(self._ID, 'tx_limit', 100))

            sequence = None

            while True:

                path = '/v1/me/getexecutions?count=%s&product_code=%s' % (limit, code)

                if sequence is not None:
                    path = path + '&before=%s' % sequence

                executions = self._query_private(path)

                values = []

                for execution in executions if executions is not None else []:
                    exec_id = execution.get('id')  # Self-cross has same ids.
                    exec_od = execution.get('child_order_id')
                    exec_ts = execution.get('exec_date')
                    exec_sd = execution.get('side')
                    exec_in = execution.get('size')
                    exec_px = execution.get('price')
                    exec_cm = execution.get('commission', self._ZERO)

                    sequence = exec_id if sequence is None else min(exec_id, sequence)

                    value = Transaction()
                    value.tx_site = self._ID
                    value.tx_code = code
                    value.tx_type = TransactionType.TRADE
                    value.tx_acct = AccountType.CASH if is_cash else AccountType.MARGIN
                    value.tx_oid = exec_od
                    value.tx_eid = str(exec_id)
                    value.tx_time = self.__context.parse_iso_timestamp(exec_ts)
                    value.tx_inst = (exec_in * self._SIDE[exec_sd]) - exec_cm
                    value.tx_fund = (exec_in * self._SIDE[exec_sd]) * exec_px * -1

                    values.append(value)

                self.__logger.debug('Transactions : %s - fetched=[%s] sequence=[%s]', code, len(values), sequence)

                results = self.__context.save_transactions(values)

                if len(results) <= 0:
                    break

        except Exception as e:

            self.__logger.warn('Transaction Failure - %s : %s - %s', code, type(e), e.args)

    def _process_cash(self):
        self._process_balance('/v1/me/getbalance', AccountType.CASH)

    def _process_margin(self):
        self._process_balance('/v1/me/getcollateralaccounts', AccountType.MARGIN)

    def _process_balance(self, path, account_type):

        try:

            now = self.__context.get_now()

            balances = self._query_private(path)

            values = []

            for balance in balances if balances is not None else []:

                ccy = balance.get('currency_code')

                try:
                    unit = UnitType[ccy]
                except KeyError:
                    continue

                value = Balance()
                value.bc_site = self._ID
                value.bc_acct = account_type
                value.bc_unit = unit
                value.bc_time = now
                value.bc_amnt = balance.get('amount')

                values.append(value)

            self.__context.save_balances(values)

            for value in values:
                self.__logger.debug('Balance : %s - %s', account_type.name, value)

        except Exception as e:

            self.__logger.warn('Balance Failure - %s : %s - %s', account_type, type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = BitflyerWelder(context)
    target.run()


def main_historical():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = BitflyerWelder(context)

    maturity = datetime(year=2017, month=4, day=28)

    while maturity < datetime.now():
        y = maturity.strftime('%Y')
        m = [k for k, v in BitflyerWelder._MONTHS.items() if v == maturity.month][0]
        d = maturity.strftime('%d')

        product = 'BTCJPY%s%s%s' % (d, m, y)
        target._process_ticker(product)
        target._process_transaction(product)

        maturity = maturity + timedelta(days=7)


if __name__ == '__main__':
    main()
