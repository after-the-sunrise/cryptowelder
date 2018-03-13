from datetime import timedelta
from threading import Thread
from time import sleep

from cryptowelder.context import CryptowelderContext, Timestamp


class MetricWelder:
    _ID = 'metric'

    def __init__(self, context):
        self.__context = context
        self.__logger = context.get_logger(self)
        self.__threads = [
            Thread(target=self._wrap, args=(self.process_timestamp, 15))
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


def main():
    context = CryptowelderContext(config='~/.cryptowelder', debug=True)
    context.launch_prometheus()

    target = MetricWelder(context)
    target.run()


if __name__ == '__main__':
    main()
