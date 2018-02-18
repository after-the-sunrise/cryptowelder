from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from hmac import new
from re import compile
from threading import Thread
from time import sleep

from pytz import utc

from cryptowelder.context import CryptowelderContext, Ticker, Position


class BitflyerWelder:
    _ID = 'bitflyer'
    _ZERO = Decimal('0')
    _SIDE = {'BUY': Decimal('+1'), 'SELL': Decimal('-1')}

    # "yyyy-MM-ddTHH:mm:ss", "yyyy-MM-ddTHH:mm:ss.SSS", "yyyy-MM-ddTHH:mm:ss.SSSZ"
    _TIMEFMT = compile('^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z?$')

    # "BTCJPYddMMMyyyy"
    _FUTURES = compile('^[A-Z]{6}[0-9]{2}[A-Z]{3}[0-9]{4}$')
    _MONTHS = {value: i for i, value in enumerate(
        [None, 'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    )}

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__endpoint = context.get_property(self._ID, 'endpoint', 'https://api.bitflyer.jp')
        self.__interval = context.get_property(self._ID, 'interval', 15)
        self.__apikey = context.get_property(self._ID, 'apikey', None)
        self.__secret = context.get_property(self._ID, 'secret', None)
        self.__thread = Thread(daemon=False, target=self._loop)

    def run(self):

        self.__thread.start()

    def _join(self):

        self.__thread.join()

    def _loop(self):

        self.__logger.info('Endpoint=[%s] Interval=[%s] Key=[%s]', self.__endpoint, self.__interval, self.__apikey)

        while not self.__context.is_closed():

            threads = [
                Thread(target=self._process_market),
                Thread(target=self._process_balance),
            ]

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            sleep(self.__interval)

    def _process_market(self):

        try:

            # [{"product_code": "BTCJPYddMMMyyyy", "alias": "BTCJPY_MAT1WK"}, ...]
            markets = self.__context.requests_get(self.__endpoint + '/v1/markets')

            for market in markets if markets is not None else []:
                code = market.get('product_code', None)

                self._process_ticker(code)

                self._process_position(code)

                self._process_transaction(code)

        except Exception as e:

            self.__logger.warn('Market Failure : %s - %s', type(e), e.args)

    def _process_ticker(self, code):

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

            ticker.tk_time = self._parse_timestamp(json.get('timestamp', None))
            ticker.tk_ask = json.get('best_ask', None)
            ticker.tk_bid = json.get('best_bid', None)
            ticker.tk_ltp = json.get('ltp', None)

        self.__context.save_tickers([ticker])

    def __is_futures(self, code):
        return code is not None and self._FUTURES.match(code)

    def _fetch_special_quotation(self, code):

        if not self.__is_futures(code):
            return None

        json = self.__context.requests_get(self.__endpoint + '/v1/getboardstate?product_code=' + code)

        return json.get('data', json).get('special_quotation', None) if json is not None else None

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

        # "Asia/Tokyo" is 19 minutes off.
        return datetime(year=y, month=m, day=d, hour=16 - 9, minute=0, tzinfo=utc)

    def _parse_timestamp(self, value):

        if value is None or not self._TIMEFMT.match(value):
            return None

        # 01234567890123456789012
        # yyyy-MM-ddTHH:mm:ss.SSS
        stripped = value[:19]

        local = datetime.strptime(stripped, '%Y-%m-%dT%H:%M:%S')

        return local.replace(tzinfo=utc)

    def _query_private(self, path):

        if self.__apikey is None or self.__secret is None:
            return None

        timestamp = str(int(self.__context.get_now().timestamp() * 1000))

        data = timestamp + "GET" + path

        digest = new(str.encode(self.__secret), str.encode(data), sha256).hexdigest()

        headers = {
            "ACCESS-KEY": self.__apikey,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-SIGN": digest,
            "Content-Type": "application/json"
        }

        return self.__context.requests_get(self.__endpoint + path, headers=headers)

    def _process_position(self, code):

        if 'FX_BTC_JPY' != code and not self.__is_futures(code):
            return

        positions = self._query_private('/v1/me/getpositions?product_code=' + code)

        now = self.__context.get_now()
        amount_inst = None
        amount_fund = None

        for position in positions if positions is not None else []:
            # Instrument Position
            sign = self._SIDE.get(position.get('side', None), self._ZERO)
            inst = position.get('size', self._ZERO) * sign
            amount_inst = (amount_inst if amount_inst is not None else self._ZERO) + inst

            # P&L
            pnl = position.get('pnl', self._ZERO)
            swp = position.get('swap_point_accumulate', self._ZERO)
            cmm = position.get('commission', self._ZERO)
            amount_fund = (amount_fund if amount_fund is not None else self._ZERO) + pnl - swp - cmm

        position = Position()
        position.ps_site = self._ID
        position.ps_code = code
        position.ps_time = now
        position.ps_inst = amount_inst
        position.ps_fund = amount_fund

        self.__context.save_positions([position])

    def _process_transaction(self, code):
        pass  # TODO

    def _process_balance(self):
        pass  # TODO


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = BitflyerWelder(context)
    target.run()


if __name__ == '__main__':
    main()
