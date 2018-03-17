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

        count = int(self.__context.get_property(self._ID, 'timestamp', 3))

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

        count = int(self.__context.get_property(self._ID, 'timestamp', 3))

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

        if evaluation.ev_ticker_site is not None and evaluation.ev_ticker_code is not None:

            codes = prices.get(evaluation.ev_ticker_site)

            p = codes.get(evaluation.ev_ticker_code) if codes is not None else None

            if p is None:
                return None

            price = price * p

        if evaluation.ev_convert_site is not None and evaluation.ev_convert_code is not None:

            codes = prices.get(evaluation.ev_convert_site)

            p = codes.get(evaluation.ev_convert_code) if codes is not None else None

            if p is None:
                return None

            price = price * p

        return price

    def process_ticker(self, timestamp):

        try:

            values = self.__context.fetch_tickers(timestamp, include_expired=True)

            prices = defaultdict(lambda: dict())

            for dto in values if values is not None else []:

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

            for dto in values if values is not None else []:

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

    def process_transaction(self, timestamp, prices):

        try:

            metrics = []

            offset = timedelta(minutes=int(self.__context.get_property(self._ID, 'offset', -9 * 60)))

            items = {
                'DAY': timestamp.replace(microsecond=0, second=0, minute=0, hour=0) + offset,
                'MTD': timestamp.replace(microsecond=0, second=0, minute=0, hour=0, day=1) + offset,
                'YTD': timestamp.replace(microsecond=0, second=0, minute=0, hour=0, day=1, month=1) + offset,
            }

            for key, val in items.items():

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

            self.__logger.warn('Transaction : %s : %s', type(e), e.args)


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = MetricWelder(context)
    target.run()


if __name__ == '__main__':
    main()
