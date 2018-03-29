from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from threading import Thread
from time import sleep

from pytz import utc

from cryptowelder.context import CryptowelderContext, Metric


class MetricWelder:
    _ID = 'metric'
    _ONE = Decimal('1.0')
    _HALF = Decimal('0.5')
    _ZERO = Decimal('0.0')

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__threads = [
            Thread(target=self._wrap, args=(self.process_metric, 30)),
            Thread(target=self._wrap, args=(self.purge_metric, 3600)),
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

    def process_metric(self):
        self.process_metrics(self.__context.get_now())

    def process_metrics(self, base_time, *, default_count=3):

        count = int(self.__context.get_property(self._ID, 'timestamp', default_count))

        timestamps = [base_time.replace(second=0, microsecond=0) - timedelta(minutes=i) for i in range(0, count)]

        self.__logger.debug('Metrics : %s', [t.strftime('%Y-%m-%d %H:%M') for t in timestamps])

        threads = []

        for timestamp in timestamps:
            prices = self.process_ticker(timestamp)
            threads.append(Thread(target=self.process_balance, args=(timestamp, prices)))
            threads.append(Thread(target=self.process_position, args=(timestamp, prices)))
            threads.append(Thread(target=self.process_transaction_trade, args=(timestamp, prices)))
            threads.append(Thread(target=self.process_transaction_volume, args=(timestamp, prices)))

        for t in threads:
            t.start()

        for t in threads:
            t.join()

    def calculate_evaluation(self, evaluation, prices):

        if evaluation is None:
            return None

        price = self._ONE

        if evaluation.ev_ticker_site is not None and evaluation.ev_ticker_code is not None:

            codes = prices.get(evaluation.ev_ticker_site)

            p = codes.get(evaluation.ev_ticker_code) if codes is not None else None

            if p is None or p == self._ZERO:
                return None

            price = price * p

        if evaluation.ev_convert_site is not None and evaluation.ev_convert_code is not None:

            codes = prices.get(evaluation.ev_convert_site)

            p = codes.get(evaluation.ev_convert_code) if codes is not None else None

            if p is None or p == self._ZERO:
                return None

            price = price * p

        return price

    def process_ticker(self, timestamp):

        prices = None

        try:

            values = self.__context.fetch_tickers(timestamp, include_expired=True)

            prices = defaultdict(lambda: dict())

            for dto in values if values is not None else []:

                ticker = dto.ticker
                ask = ticker.tk_ask if ticker.tk_ask != self._ZERO else None
                bid = ticker.tk_bid if ticker.tk_bid != self._ZERO else None
                ltp = ticker.tk_ltp if ticker.tk_ltp != self._ZERO else None

                price = None

                if ask is not None and bid is not None:
                    price = (ask + bid) * self._HALF

                if price is None:
                    price = ask

                if price is None:
                    price = bid

                if price is None:
                    price = ltp

                prices[ticker.tk_site][ticker.tk_code] = price

            metrics = []

            threshold_minutes = self.__context.get_property(self._ID, 'ticker_threshold', 3)

            threshold_cutoff = timestamp - timedelta(minutes=int(threshold_minutes))

            for dto in values if values is not None else []:

                if dto.ticker.tk_time.replace(tzinfo=threshold_cutoff.tzinfo) < threshold_cutoff:
                    continue

                price = prices[dto.ticker.tk_site][dto.ticker.tk_code]

                if price is None or price == self._ZERO or dto.product is None:
                    continue

                expiry = dto.product.pr_expr

                if expiry is not None and expiry.astimezone(timestamp.tzinfo) < timestamp:
                    continue

                rate = self.calculate_evaluation(dto.fund, prices)

                if rate is None:
                    continue

                metric = Metric()
                metric.mc_type = 'ticker'
                metric.mc_name = dto.product.pr_disp
                metric.mc_time = timestamp
                metric.mc_amnt = price * rate
                metrics.append(metric)

            self.__context.save_metrics(metrics)

        except BaseException as e:

            self.__logger.warn('Ticker : %s : %s', type(e), e.args)

        return prices

    def process_balance(self, timestamp, prices):

        try:

            metrics = []

            values = self.__context.fetch_balances(timestamp)

            for dto in values if values is not None else []:

                amount = dto.balance.bc_amnt

                rate = self.calculate_evaluation(dto.evaluation, prices)

                if dto.account is None or amount is None or rate is None:
                    continue

                metric = Metric()
                metric.mc_type = 'balance'
                metric.mc_name = dto.account.ac_disp
                metric.mc_time = timestamp
                metric.mc_amnt = amount * rate
                metrics.append(metric)

            self.__context.save_metrics(metrics)

        except BaseException as e:

            self.__logger.warn('Balance : %s : %s', type(e), e.args)

    def process_position(self, timestamp, prices):

        try:

            metrics = []

            values = self.__context.fetch_positions(timestamp)

            for dto in values if values is not None else []:

                amount = dto.position.ps_fund

                rate = self.calculate_evaluation(dto.fund, prices)

                if dto.product is None or amount is None or rate is None:
                    continue

                metric = Metric()
                metric.mc_type = 'position@upl'
                metric.mc_name = dto.product.pr_disp
                metric.mc_time = timestamp
                metric.mc_amnt = amount * rate
                metrics.append(metric)

            for dto in values if values is not None else []:

                amount = dto.position.ps_inst

                rate = self.calculate_evaluation(dto.inst, prices)

                if dto.product is None or amount is None or rate is None:
                    continue

                metric = Metric()
                metric.mc_type = 'position@qty'
                metric.mc_name = dto.product.pr_disp
                metric.mc_time = timestamp
                metric.mc_amnt = amount * rate
                metrics.append(metric)

            self.__context.save_metrics(metrics)

        except BaseException as e:

            self.__logger.warn('Position : %s : %s', type(e), e.args)

    def process_transaction_trade(self, timestamp, prices):

        try:

            metrics = []

            offset = timedelta(minutes=int(self.__context.get_property(self._ID, 'offset', 9 * 60)))

            t = timestamp + offset

            windows = {
                'DAY': t.replace(microsecond=0, second=0, minute=0, hour=0) - offset,
                'MTD': t.replace(microsecond=0, second=0, minute=0, hour=0, day=1) - offset,
                'YTD': t.replace(microsecond=0, second=0, minute=0, hour=0, day=1, month=1) - offset,
            }

            for key, val in windows.items():

                values = self.__context.fetch_transactions(val, timestamp)

                for dto in values if values is not None else []:

                    inst_qty = dto.tx_net_inst
                    fund_qty = dto.tx_net_fund

                    inst_rate = self.calculate_evaluation(dto.ev_inst, prices)
                    fund_rate = self.calculate_evaluation(dto.ev_fund, prices)

                    if dto.product is None \
                            or inst_qty is None or fund_qty is None \
                            or inst_rate is None or fund_rate is None:
                        continue

                    metric = Metric()
                    metric.mc_type = 'trade@' + key
                    metric.mc_name = dto.product.pr_disp
                    metric.mc_time = timestamp
                    metric.mc_amnt = (inst_qty * inst_rate) + (fund_qty * fund_rate)
                    metrics.append(metric)

            self.__context.save_metrics(metrics)

        except BaseException as e:

            self.__logger.warn('Transaction (trade) : %s : %s', type(e), e.args)

    def process_transaction_volume(self, timestamp, prices):

        try:

            metrics = []

            windows = {
                '12H': timestamp - timedelta(hours=12),
                '01D': timestamp - timedelta(hours=24),
                '30D': timestamp - timedelta(days=30),
            }

            for key, val in windows.items():

                values = self.__context.fetch_transactions(val, timestamp)

                for dto in values if values is not None else []:

                    amount = dto.tx_grs_fund

                    rate = self.calculate_evaluation(dto.ev_fund, prices)

                    if dto.product is None or amount is None or rate is None:
                        continue

                    metric = Metric()
                    metric.mc_type = 'volume@' + key
                    metric.mc_name = dto.product.pr_disp
                    metric.mc_time = timestamp
                    metric.mc_amnt = amount * rate
                    metrics.append(metric)

            self.__context.save_metrics(metrics)

        except BaseException as e:

            self.__logger.warn('Transaction (volume) : %s : %s', type(e), e.args)

    def purge_metric(self, *, intervals=(

            # [0] Older than 5+ years, delete all.
            (1984, tuple()),

            # [1] Older than 1+ month, hourly interval.
            (42, tuple([0])),

            # [2] Older than 1 week, 30 minutes interval.
            (7, tuple(i * 30 for i in range(0, 2))),

            # [3] Older than 2 days, 15 minutes interval.
            (2, tuple(i * 15 for i in range(0, 4))),

            # [4] Older than 1 day, 5 minutes interval.
            (1, tuple(i * 5 for i in range(0, 12))),

    )):

        now = self.__context.get_now()

        for idx, entry in enumerate(intervals):

            days = self.__context.get_property(self._ID, 'purge_%s' % idx, entry[0])

            if days is None:
                continue

            cutoff = now - timedelta(days=max(int(days), 1))

            count = self.__context.delete_metrics(cutoff, exclude_minutes=entry[1])

            self.__logger.debug('Purged [%s] cutoff=%s count=%s', idx, cutoff, count)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = MetricWelder(context)
    target.run()


def main_historical():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = MetricWelder(context)

    timestamp = context.get_now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    while True:

        if timestamp >= datetime.now().astimezone(utc):
            break

        target.process_metrics(timestamp, default_count=1)

        timestamp = timestamp + timedelta(minutes=60)


if __name__ == '__main__':
    main()
