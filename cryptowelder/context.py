from datetime import datetime
from decimal import Decimal
from enum import auto, Enum
from json import loads
from logging import Formatter, StreamHandler, DEBUG, INFO, getLogger
from logging.handlers import TimedRotatingFileHandler, BufferingHandler
from time import sleep

from pytz import timezone
from requests import get, post
from sqlalchemy import create_engine, Column, String, DateTime, Numeric, Enum as Type
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session


class CryptowelderContext:
    BASE = declarative_base()
    ZONE = timezone("Asia/Tokyo")

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
        self.__session = scoped_session(sessionmaker(bind=self.__engine))

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

                        result = loads(r.text, parse_float=Decimal)

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

    def _truncate_datetime(self, input):

        return datetime(
            year=input.year,
            month=input.month,
            day=input.day,
            hour=input.hour,
            minute=input.minute,
            tzinfo=input.tzinfo
        ).astimezone(self.ZONE)

    def save_tickers(self, tickers):

        merged = []

        session = self.__session()

        try:

            for t in tickers if tickers is not None else []:

                if t is None or t.tk_site is None or t.tk_product is None or t.tk_time is None:
                    continue

                truncated = Ticker()
                truncated.tk_site = t.tk_site
                truncated.tk_product = t.tk_product
                truncated.tk_time = self._truncate_datetime(t.tk_time)
                truncated.tk_ask = t.tk_ask
                truncated.tk_bid = t.tk_bid
                truncated.tk_ltp = t.tk_ltp

                session.merge(truncated)

                merged.append(t)

            if len(merged) > 0:
                session.commit()

        finally:

            session.close()

        return merged

    def save_balances(self, balances):

        merged = []

        session = self.__session()

        try:

            for b in balances if balances is not None else []:

                if b is None or b.bc_site is None or b.bc_acct is None \
                        or b.bc_unit is None or b.bc_time is None or b.bc_amnt is None:
                    continue

                truncated = Balance()
                truncated.bc_site = b.bc_site
                truncated.bc_acct = b.bc_acct
                truncated.bc_unit = b.bc_unit
                truncated.bc_time = self._truncate_datetime(b.bc_time)
                truncated.bc_amnt = b.bc_amnt

                session.merge(truncated)

                merged.append(b)

            if len(merged) > 0:
                session.commit()

        finally:

            session.close()

        return merged

    def save_transactions(self, transactions):

        candidates = {}

        session = self.__session()

        try:

            for t in transactions if transactions is not None else []:

                if t is None or t.tx_site is None or t.tx_product is None or t.tx_id is None \
                        or t.tx_time is None or t.tx_inst is None or t.tx_fund is None:
                    continue

                first = session.query(Transaction).filter(
                    Transaction.tx_site == t.tx_site,
                    Transaction.tx_product == t.tx_product,
                    Transaction.tx_id == t.tx_id,
                ).first()

                if first is not None:
                    continue  # Skip Existing

                truncated = Transaction()
                truncated.tx_site = t.tx_site
                truncated.tx_product = t.tx_product
                truncated.tx_id = t.tx_id
                truncated.tx_time = t.tx_time.astimezone(self.ZONE)
                truncated.tx_inst = t.tx_inst
                truncated.tx_fund = t.tx_fund

                candidates[t] = truncated

            if len(candidates) > 0:
                session.add_all(candidates.values())
                session.commit()

        finally:

            session.close()

        return candidates.keys()


class AccountType(Enum):
    CASH = auto()
    MARGIN = auto()


class UnitType(Enum):
    QTY = auto()
    JPY = auto()
    BTC = auto()


class Ticker(CryptowelderContext.BASE):
    __tablename__ = "t_ticker"
    tk_site = Column(String, primary_key=True)
    tk_product = Column(String, primary_key=True)
    tk_time = Column(DateTime, primary_key=True)
    tk_ask = Column(Numeric)
    tk_bid = Column(Numeric)
    tk_ltp = Column(Numeric)


class Balance(CryptowelderContext.BASE):
    __tablename__ = "t_balance"
    bc_site = Column(String, primary_key=True)
    bc_acct = Column(Type(AccountType), primary_key=True)
    bc_unit = Column(Type(UnitType), primary_key=True)
    bc_time = Column(DateTime, primary_key=True)
    bc_amnt = Column(Numeric, nullable=False)


class Transaction(CryptowelderContext.BASE):
    __tablename__ = 't_transaction'
    tx_site = Column(String, primary_key=True)
    tx_product = Column(String, primary_key=True)
    tx_id = Column(String, primary_key=True)
    tx_time = Column(DateTime, nullable=False)
    tx_inst = Column(Numeric, nullable=False)
    tx_fund = Column(Numeric, nullable=False)
