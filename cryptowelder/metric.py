from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from threading import Thread
from time import sleep

from cryptowelder.context import CryptowelderContext, Timestamp, Metric


class MetricWelder:
    _ID = 'metric'
    _ONE = Decimal('1.0')
    _HALF = Decimal('0.5')

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__threads = [
            Thread(target=self._wrap, args=(self.process_timestamp, 15)),
            Thread(target=self._wrap, args=(self.process_metric, 30)),
        ]

    def run(self):

        self.__logger.info('Processing : metric')

        for t in self.__threads:
            t.start()

    def join(self):

        for t in self.__threads:
            t.join()

        self.__logger.info('Terminated.')

    def _wrap(self, func, interval):

        while not self.__context.is_closed():

            try:

                func()

            except BaseException as e:

                self.__logger.warn('%s - %s : %s', func.__name__, type(e), e.args)

            sleep(interval)

    def process_timestamp(self):

        count = int(self.__context.get_property(self._ID, 'timestamp_count', 3))

        values = [
            self.__context.get_now().replace(second=0, microsecond=0)
        ]

        while len(values) < count:
            values.append(values[0] - timedelta(minutes=len(values)))

        timestamps = []

        for v in values:
            t = Timestamp()
            t.ts_time = v
            timestamps.append(t)

        self.__context.save_timestamps(timestamps)

    def process_metric(self):

        base = self.__context.get_now().replace(second=0, microsecond=0)

        count = int(self.__context.get_property(self._ID, 'metric_count', 3))

        timestamps = [base - timedelta(minutes=i) for i in range(0, count)]

        threads = []

        for timestamp in timestamps:
            prices = self.process_ticker(timestamp)

            threads.append(Thread(target=self.process_balance, args=(timestamp, prices)))
            threads.append(Thread(target=self.process_position, args=(timestamp, prices)))
            threads.append(Thread(target=self.process_transaction, args=(timestamp, prices)))

        for t in threads:
            t.start()

        for t in threads:
            t.join()

    def calculate_evaluation(self, evaluation, prices):

        if evaluation is None:
            return None

        price = self._ONE

        if evaluation.ev_ticker_site is None or evaluation.ev_ticker_code is None:

            codes = prices.get(evaluation.ev_ticker_site)

            p = codes.get(evaluation.ev_ticker_code) if codes is not None else None

            if p is None:
                return None

            price = price * p

        if evaluation.ev_ticker_site is None or evaluation.ev_ticker_code is None:

            codes = prices.get(evaluation.ev_convert_site)

            p = codes.get(evaluation.ev_convert_code) if codes is not None else None

            if p is None:
                return None

            price = price * p

        return price

    def process_ticker(self, timestamp):

        try:

            tickers = self.__context.fetch_tickers(timestamp, include_expired=True)

            prices = defaultdict(lambda: dict())

            for dto in tickers if tickers is not None else []:

                ticker = dto.ticker

                if ticker.tk_ask is not None and ticker.tk_bid is not None:
                    price = (ticker.tk_ask + ticker.tk_bid) * self._HALF
                else:
                    price = ticker.tk_ltp

                prices[ticker.tk_site][ticker.tk_code] = price

        except BaseException as e:

            self.__logger.warn('Ticker : %s : %s', type(e), e.args)

            return None

        try:

            metrics = []

            for dto in tickers if tickers is not None else []:

                if dto.product is None:
                    continue

                expiry = dto.product.pr_expr

                if expiry is not None and expiry.astimezone(timestamp.tzinfo) < timestamp:
                    continue

                if dto.ticker.tk_ask is not None and dto.ticker.tk_bid is not None:
                    price = (dto.ticker.tk_ask + dto.ticker.tk_bid) * self._HALF
                elif dto.ticker.tk_ltp is not None:
                    price = dto.ticker.tk_ltp
                else:
                    continue

                rate = self.calculate_evaluation(dto.inst, prices)

                if rate is None:
                    continue

                metric = Metric()
                metric.mc_type = 'tk'
                metric.mc_name = dto.product.pr_disp
                metric.mc_time = timestamp
                metric.mc_amnt = price * rate
                metrics.append(metric)

            self.__context.save_metrics(metrics)

        except BaseException as e:

            self.__logger.warn('Ticker : %s : %s', type(e), e.args)

        return prices

    def process_balance(self, timestamp, prices):
        pass  # TODO

    def process_position(self, timestamp, prices):
        pass  # TODO

    def process_transaction(self, timestamp, prices):
        pass  # TODO


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = MetricWelder(context)
    target.run()


if __name__ == '__main__':
    main()
