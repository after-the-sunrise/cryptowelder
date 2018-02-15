from logging import Formatter, StreamHandler, DEBUG, INFO, getLogger
from logging.handlers import TimedRotatingFileHandler, BufferingHandler
from time import sleep

from requests import get, post
from sqlalchemy import create_engine, Column, VARCHAR, TIMESTAMP, DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


class CryptowelderContext:
    BASE = declarative_base()

    def __init__(self, *, logs=None, requests_retry=3, database=None):
        self.__formatter = Formatter(fmt='[%(asctime)-15s][%(levelname)-5s][%(name)s] %(message)s')
        self.__stream_handler = StreamHandler()
        self.__stream_handler.setFormatter(self.__formatter)
        self.__stream_handler.setLevel(DEBUG if logs is None else INFO)
        self.__rotate_handler = TimedRotatingFileHandler(
            logs, when='D', backupCount=7
        ) if logs is not None else BufferingHandler(64)
        self.__rotate_handler.setFormatter(self.__formatter)
        self.__rotate_handler.setLevel(DEBUG)
        self.__logger = self.get_logger(self)
        self.__retry = requests_retry
        self.__engine = create_engine(
            database if database is not None else 'sqlite:///:memory:',
            echo=database is None
        )
        self.__session = sessionmaker(bind=self.__engine)

    def _create_all(self):
        self.BASE.metadata.create_all(bind=self.__engine)

    def get_logger(self, source):
        logger = getLogger(source.__class__.__name__)
        logger.setLevel(DEBUG)
        logger.addHandler(self.__stream_handler)
        logger.addHandler(self.__rotate_handler)
        return logger

    def _request(self, method, *, interval=1):

        result = None

        for i in range(self.__retry + 1):

            try:

                with method() as r:

                    if r.status_code >= 500:  # Server Error

                        url = r.request.url

                        raise Exception(r.status_code, r.reason, r.text, url)

                    if r.ok:

                        result = r.json()

                    else:

                        url = r.request.url

                        self.__logger.warning('[%s:%s] %s - %s', r.status_code, r.reason, r.text, url)

                    break

            except BaseException as e:

                self.__logger.debug('%s : %s', type(e), e.args)

                sleep(interval)

        return result

    def requests_get(self, url, params=None, **kwargs):
        return self._request(lambda: get(url, params=params, **kwargs))

    def requests_post(self, url, data=None, json=None, **kwargs):
        return self._request(lambda: post(url, data=data, json=json, **kwargs))

    def add_transactions(self, transactions):

        session = self.__session()

        candidates = []

        for t in transactions if transactions is not None else []:

            count = session.query(Transaction).filter(
                Transaction.tx_site == t.tx_site,
                Transaction.tx_product == t.tx_product,
                Transaction.tx_id == t.tx_id,
            ).count()

            if count > 0:
                continue

            candidates.append(t)

        if len(candidates) > 0:
            session.add_all(candidates)
            session.commit()

        return candidates


class Transaction(CryptowelderContext.BASE):
    __tablename__ = 't_transaction'

    tx_site = Column(VARCHAR, primary_key=True)
    tx_product = Column(VARCHAR, primary_key=True)
    tx_id = Column(VARCHAR, primary_key=True)
    tx_time = Column(TIMESTAMP)
    tx_inst = Column(DECIMAL)
    tx_fund = Column(DECIMAL)
