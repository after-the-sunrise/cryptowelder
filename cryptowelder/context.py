from configparser import ConfigParser
from datetime import datetime
from decimal import Decimal
from enum import auto, Enum
from json import loads
from logging import Formatter, StreamHandler, DEBUG, INFO, getLogger
from logging.handlers import TimedRotatingFileHandler, BufferingHandler
from os import path
from time import sleep

import prometheus_client
from pytz import timezone, utc
from requests import get, post
from sqlalchemy import create_engine, Column, String, DateTime, Numeric, Enum as Type
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session


class CryptowelderContext:
    SECTION = 'context'
    TIMEZONE = timezone("Asia/Tokyo")
    ENTITY_BASE = declarative_base()

    def __init__(self, *, read_only=True, config=None, debug=True):
        # Read-only for testing
        self.__read_only = read_only

        # Configuration
        self.__config = self._create_config([config])

        # Logging
        logger = self.get_property(self.SECTION, 'log_path', 'logs/cryptowelder.log')

        formatter = Formatter('[%(asctime)-15s][%(levelname)-5s][%(name)s] %(message)s')
        self.__stream_handler = StreamHandler()
        self.__stream_handler.setFormatter(formatter)
        self.__stream_handler.setLevel(DEBUG if debug else INFO)
        self.__rotate_handler = TimedRotatingFileHandler(
            logger,
            when=self.get_property(self.SECTION, 'log_roll', 'D'),
            backupCount=int(self.get_property(self.SECTION, 'log_bkup', 7))
        ) if path.exists(path.dirname(logger)) else BufferingHandler(64)
        self.__rotate_handler.setFormatter(formatter)
        self.__rotate_handler.setLevel(DEBUG)
        self.__logger = self.get_logger(self)
        self.__logger.info('Logger : %s', logger)
        self.__logger.info('Config : %s', config)

        # Database
        database = self.get_property(self.SECTION, 'database', 'sqlite:///:memory:')
        self.__engine = create_engine(database)
        self.__session = scoped_session(sessionmaker(bind=self.__engine))
        self.__logger.info('Database : %s (read_only=%s)', database, read_only)

    def _create_config(self, paths):

        config = ConfigParser()

        expanded = [path.expanduser(p) for p in paths if p is not None]

        exists = [p for p in expanded if path.exists(p)]

        config.read(exists, 'UTF-8')

        return config

    def set_property(self, section, key, value):

        if section not in self.__config:
            self.__config.add_section(section)

        self.__config[section][key] = value

    def get_property(self, section, key, default_value=None):

        if section not in self.__config:
            return default_value

        return self.__config[section].get(key, default_value)

    def get_logger(self, source):
        logger = getLogger(source.__class__.__name__)
        logger.setLevel(DEBUG)
        logger.addHandler(self.__stream_handler)
        logger.addHandler(self.__rotate_handler)
        return logger

    def is_closed(self):
        return self.get_property(self.SECTION, 'closed', None) is not None

    def get_now(self):
        return datetime.now(tz=utc)

    def launch_prometheus(self, *, method=prometheus_client.start_http_server):

        host = self.get_property(self.SECTION, 'prometheus_host', 'localhost')
        port = self.get_property(self.SECTION, 'prometheus_port', '20000')
        self.get_logger(self).info('Prometheus : %s:%s', host, port)

        method(int(port), addr=host)

    @staticmethod
    def _parse(json):
        return loads(json, parse_float=Decimal)

    def _request(self, method):

        attempt = int(self.get_property(self.SECTION, "request_retry", 1)) + 1

        result = None

        for i in range(attempt):

            try:

                with method() as r:

                    if r.status_code >= 500:  # Server Error

                        url = r.request.url

                        raise Exception(r.status_code, r.reason, r.text, url)

                    if r.ok:

                        result = self._parse(r.text)

                    else:

                        url = r.request.url

                        self.__logger.warning('[%s:%s] %s - %s', r.status_code, r.reason, r.text, url)

                    break

            except BaseException as e:

                self.__logger.debug('%s : %s', type(e), e.args)

                sleep(float(self.get_property(self.SECTION, "request_sleep", 1.0)))

        return result

    def requests_get(self, url, params=None, **kwargs):
        return self._request(lambda: get(url, params=params, **kwargs))

    def requests_post(self, url, data=None, json=None, **kwargs):
        return self._request(lambda: post(url, data=data, json=json, **kwargs))

    def _truncate_datetime(self, source):

        return datetime(
            year=source.year,
            month=source.month,
            day=source.day,
            hour=source.hour,
            minute=source.minute,
            tzinfo=source.tzinfo
        ).astimezone(self.TIMEZONE)

    def _create_all(self):
        self.ENTITY_BASE.metadata.create_all(bind=self.__engine)

    def _is_read_only(self):
        return self.__read_only

    def save_tickers(self, tickers):

        merged = []

        session = self.__session()

        try:

            for t in tickers if tickers is not None else []:

                if self._is_read_only():
                    self.__logger.debug("Skipping : %s", t)
                    continue

                if t is None:
                    continue

                truncated = Ticker()
                truncated.tk_site = t.tk_site
                truncated.tk_code = t.tk_code
                truncated.tk_time = self._truncate_datetime(t.tk_time)
                truncated.tk_ask = t.tk_ask
                truncated.tk_bid = t.tk_bid
                truncated.tk_ltp = t.tk_ltp

                session.merge(truncated)

                merged.append(t)

            if len(merged) > 0:
                session.commit()

        except BaseException as e:

            session.rollback()

            raise e

        finally:

            session.close()

        return merged

    def save_balances(self, balances):

        merged = []

        session = self.__session()

        try:

            for b in balances if balances is not None else []:

                if self._is_read_only():
                    self.__logger.debug("Skipping : %s", b)
                    continue

                if b is None:
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

        except BaseException as e:

            session.rollback()

            raise e

        finally:

            session.close()

        return merged

    def save_positions(self, positions):

        merged = []

        session = self.__session()

        try:

            for p in positions if positions is not None else []:

                if self._is_read_only():
                    self.__logger.debug("Skipping : %s", p)
                    continue

                if p is None:
                    continue

                truncated = Position()
                truncated.ps_site = p.ps_site
                truncated.ps_code = p.ps_code
                truncated.ps_time = self._truncate_datetime(p.ps_time)
                truncated.ps_inst = p.ps_inst
                truncated.ps_fund = p.ps_fund

                session.merge(truncated)

                merged.append(p)

            if len(merged) > 0:
                session.commit()

        except BaseException as e:

            session.rollback()

            raise e

        finally:

            session.close()

        return merged

    def save_transactions(self, transactions):

        candidates = {}

        session = self.__session()

        try:

            for t in transactions if transactions is not None else []:

                if self._is_read_only():
                    self.__logger.debug("Skipping : %s", t)
                    continue

                if t is None:
                    continue

                first = session.query(Transaction).filter(
                    Transaction.tx_site == t.tx_site,
                    Transaction.tx_code == t.tx_code,
                    Transaction.tx_type == t.tx_type,
                    Transaction.tx_id == t.tx_id,
                ).first()

                if first is not None:
                    continue  # Skip Existing

                truncated = Transaction()
                truncated.tx_site = t.tx_site
                truncated.tx_code = t.tx_code
                truncated.tx_type = t.tx_type
                truncated.tx_id = t.tx_id
                truncated.tx_time = t.tx_time.astimezone(self.TIMEZONE)
                truncated.tx_inst = t.tx_inst
                truncated.tx_fund = t.tx_fund

                candidates[t] = truncated

            if len(candidates) > 0:
                session.add_all(candidates.values())
                session.commit()

        except BaseException as e:

            session.rollback()

            raise e

        finally:

            session.close()

        return candidates.keys()


class AccountType(Enum):
    CASH = auto()
    MARGIN = auto()


class UnitType(Enum):
    QTY = auto()
    JPY = auto()
    USD = auto()
    BTC = auto()


class TransactionType(Enum):
    TRADE = auto()
    SWAP = auto()


class Ticker(CryptowelderContext.ENTITY_BASE):
    __tablename__ = "t_ticker"
    tk_site = Column(String, primary_key=True)
    tk_code = Column(String, primary_key=True)
    tk_time = Column(DateTime, primary_key=True)
    tk_ask = Column(Numeric)
    tk_bid = Column(Numeric)
    tk_ltp = Column(Numeric)

    def __str__(self):
        return str({
            'table': self.__tablename__,
            'site': self.tk_site,
            'code': self.tk_code,
            'time': self.tk_time,
            'ask': self.tk_ask,
            'bid': self.tk_bid,
            'ltp': self.tk_ltp,
        })


class Balance(CryptowelderContext.ENTITY_BASE):
    __tablename__ = "t_balance"
    bc_site = Column(String, primary_key=True)
    bc_acct = Column(Type(AccountType), primary_key=True)
    bc_unit = Column(Type(UnitType), primary_key=True)
    bc_time = Column(DateTime, primary_key=True)
    bc_amnt = Column(Numeric)

    def __str__(self):
        return str({
            'table': self.__tablename__,
            'site': self.bc_site,
            'account': self.bc_acct,
            'unit': self.bc_unit,
            'time': self.bc_time,
            'amount': self.bc_amnt,
        })


class Position(CryptowelderContext.ENTITY_BASE):
    __tablename__ = "t_position"
    ps_site = Column(String, primary_key=True)
    ps_code = Column(String, primary_key=True)
    ps_time = Column(DateTime, primary_key=True)
    ps_inst = Column(Numeric)
    ps_fund = Column(Numeric)

    def __str__(self):
        return str({
            'table': self.__tablename__,
            'site': self.ps_site,
            'code': self.ps_code,
            'time': self.ps_time,
            'instrument': self.ps_inst,
            'funding': self.ps_fund,
        })


class Transaction(CryptowelderContext.ENTITY_BASE):
    __tablename__ = 't_transaction'
    tx_site = Column(String, primary_key=True)
    tx_code = Column(String, primary_key=True)
    tx_type = Column(Type(TransactionType), primary_key=True)
    tx_id = Column(String, primary_key=True)
    tx_time = Column(DateTime, nullable=False)
    tx_inst = Column(Numeric)
    tx_fund = Column(Numeric)

    def __str__(self):
        return str({
            'table': self.__tablename__,
            'site': self.tx_site,
            'code': self.tx_code,
            'type': self.tx_type,
            'id': self.tx_id,
            'time': self.tx_time,
            'instrument': self.tx_inst,
            'funding': self.tx_fund,
        })
