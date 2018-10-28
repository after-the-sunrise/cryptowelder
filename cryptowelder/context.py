from collections import defaultdict
from collections import namedtuple
from configparser import ConfigParser
from datetime import datetime, timedelta
from decimal import Decimal
from enum import auto, Enum
from json import loads
from logging import Formatter, StreamHandler, DEBUG, INFO, getLogger
from logging.handlers import TimedRotatingFileHandler, BufferingHandler
from math import nan
from os import path
from re import compile
from threading import Lock
from time import sleep

from prometheus_client import Gauge, start_http_server
from pytz import utc
from requests import get, post, exceptions
from sqlalchemy import create_engine, Column, String, DateTime, Numeric, Integer, Enum as Type, and_, or_, func, cast
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, aliased
from sqlalchemy.sql import functions


class CryptowelderContext:
    ENTITY_BASE = declarative_base()

    _SECTION = 'context'
    _FORMAT_ISO = compile('^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z?$')
    _FORMAT_UNX = compile('^[0-9]+(\\.[0-9]+)?$')
    _ZERO = Decimal('0')

    def __init__(self, *, config=None, read_only=True, debug=True, echo=False):
        # Read-only for testing
        self.__read_only = read_only

        # Configuration
        self.__config = self._create_config([config])

        # Logging
        logger = self.get_property(self._SECTION, 'log_path', 'logs/cryptowelder.log')

        formatter = Formatter('[%(asctime)-15s][%(levelname)-5s][%(name)s] %(message)s')
        self.__stream_handler = StreamHandler()
        self.__stream_handler.setFormatter(formatter)
        self.__stream_handler.setLevel(DEBUG if debug else INFO)
        self.__rotate_handler = TimedRotatingFileHandler(
            logger,
            when=self.get_property(self._SECTION, 'log_roll', 'D'),
            backupCount=int(self.get_property(self._SECTION, 'log_bkup', 7))
        ) if path.exists(path.dirname(logger)) else BufferingHandler(64)
        self.__rotate_handler.setFormatter(formatter)
        self.__rotate_handler.setLevel(DEBUG)
        self.__logger = self.get_logger(self)
        self.__logger.info('Logger : %s', logger)
        self.__logger.info('Config : %s', config)

        # Database
        database = self.get_property(self._SECTION, 'database', 'sqlite:///:memory:')
        self.__engine = create_engine(database, echo=echo)
        self.__session = scoped_session(sessionmaker(bind=self.__engine))
        self.__logger.info('Database : %s (read_only=%s)', database, read_only)

        # Cache
        self.__nonce_lock = defaultdict(lambda: Lock())
        self.__nonce_time = {}

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
        return self.get_property(self._SECTION, 'closed', None) is not None

    def get_now(self):
        return datetime.now(tz=utc)

    def get_nonce(self, key, *, delta=timedelta(milliseconds=1)):

        while True:

            with self.__nonce_lock[key]:

                current = self.get_now()

                previous = self.__nonce_time.get(key)

                if previous is not None and previous >= current - delta:
                    continue

                self.__nonce_time[key] = current

                return current

    def parse_iso_timestamp(self, value):
        return self._parse_iso_timestamp(value)

    @classmethod
    def _parse_iso_timestamp(cls, value):

        if value is None:
            return None

        if isinstance(value, str):

            if cls._FORMAT_UNX.match(value):
                return datetime.fromtimestamp(float(value), tz=utc)

            if cls._FORMAT_ISO.match(value):
                # 01234567890123456789012
                # yyyy-MM-ddTHH:mm:ss.SSS
                stripped = value[:19]

                local = datetime.strptime(stripped, '%Y-%m-%dT%H:%M:%S')

                return local.replace(tzinfo=utc)

            return None

        return datetime.fromtimestamp(float(value), tz=utc)

    def launch_prometheus(self, *, method=start_http_server):

        host = self.get_property(self._SECTION, 'prometheus_host', 'localhost')
        port = self.get_property(self._SECTION, 'prometheus_port', '20000')
        self.get_logger(self).info('Prometheus : %s:%s', host, port)

        method(int(port), addr=host)

    @staticmethod
    def _parse(json):

        if json is None or json == '':
            return None

        return loads(json, parse_float=Decimal)

    def _request(self, method, *, label='N/A'):

        attempt = int(self.get_property(self._SECTION, "request_retry", 2)) + 1

        count = 0

        while True:

            count = count + 1

            try:

                with method() as r:

                    if r.ok:
                        return self._parse(r.text)

                    self.__logger.debug('[%s %s][%s/%s] %s', r.status_code, r.reason, count, attempt, label)

                    if r.status_code < 500 or count >= attempt:
                        raise Exception(
                            r.status_code,
                            r.reason,
                            label,
                            r.text.replace('\r', '').replace('\n', '') if r.text is not None else ''
                        )

            except exceptions.RequestException as e:

                self.__logger.debug('[%s][%s/%s] %s', type(e).__name__, count, attempt, label)

                raise Exception(label) from e

            sleep(float(self.get_property(self._SECTION, "request_sleep", 3.0)))

    def requests_get(self, url, params=None, **kwargs):

        kwargs.setdefault('timeout', int(self.get_property(self._SECTION, "request_timeout", 60)))

        return self._request(lambda: get(url, params=params, **kwargs), label=url)

    def requests_post(self, url, data=None, json=None, **kwargs):

        kwargs.setdefault('timeout', int(self.get_property(self._SECTION, "request_timeout", 60)))

        return self._request(lambda: post(url, data=data, json=json, **kwargs), label=url)

    def _truncate_datetime(self, source):

        forward = source + timedelta(seconds=59, microseconds=999999)

        return datetime(
            year=forward.year,
            month=forward.month,
            day=forward.day,
            hour=forward.hour,
            minute=forward.minute,
            tzinfo=forward.tzinfo
        ).astimezone(utc)

    def _create_all(self):
        self.ENTITY_BASE.metadata.create_all(bind=self.__engine)

    def _is_read_only(self):
        return self.__read_only

    def save_products(self, products):

        candidates = {}

        session = self.__session()

        try:

            for p in products if products is not None else []:

                if self._is_read_only():
                    self.__logger.debug("Skipping : %s", p)
                    continue

                if p is None:
                    continue

                first = session.query(Product).filter(
                    Product.pr_site == p.pr_site,
                    Product.pr_code == p.pr_code,
                ).first()

                if first is not None:
                    continue  # Skip Existing

                value = Product()
                value.pr_site = p.pr_site
                value.pr_code = p.pr_code
                value.pr_inst = p.pr_inst
                value.pr_fund = p.pr_fund
                value.pr_disp = p.pr_disp
                value.pr_expr = p.pr_expr.astimezone(utc) if p.pr_expr is not None else None

                candidates[p] = value

            if len(candidates) > 0:
                session.add_all(candidates.values())
                session.commit()

        except BaseException as e:

            self.__logger.error('Product - %s : %s', type(e), e.args)

            session.rollback()

            raise e

        finally:

            session.close()

        return candidates.keys()

    def save_evaluations(self, evaluations):

        candidates = {}

        session = self.__session()

        try:

            for candidate in evaluations if evaluations is not None else []:

                if self._is_read_only():
                    self.__logger.debug("Skipping : %s", candidate)
                    continue

                if candidate is None:
                    continue

                first = session.query(Evaluation).filter(
                    Evaluation.ev_site == candidate.ev_site,
                    Evaluation.ev_unit == candidate.ev_unit,
                ).first()

                if first is not None:
                    continue  # Skip Existing

                value = Evaluation()
                value.ev_site = candidate.ev_site
                value.ev_unit = candidate.ev_unit
                value.ev_ticker_site = candidate.ev_ticker_site
                value.ev_ticker_code = candidate.ev_ticker_code
                value.ev_convert_site = candidate.ev_convert_site
                value.ev_convert_code = candidate.ev_convert_code

                candidates[candidate] = value

            if len(candidates) > 0:
                session.add_all(candidates.values())
                session.commit()

        except BaseException as e:

            self.__logger.error('Evaluation - %s : %s', type(e), e.args)

            session.rollback()

            raise e

        finally:

            session.close()

        return candidates.keys()

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

            self.__logger.error('Ticker - %s : %s', type(e), e.args)

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

            self.__logger.error('Balance - %s : %s', type(e), e.args)

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

            self.__logger.error('Position - %s : %s', type(e), e.args)

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

                # TODO: Optimize by querying in batches.
                first = session.query(Transaction).filter(
                    Transaction.tx_site == t.tx_site,
                    Transaction.tx_code == t.tx_code,
                    Transaction.tx_type == t.tx_type,
                    Transaction.tx_acct == t.tx_acct,
                    Transaction.tx_oid == t.tx_oid,
                    Transaction.tx_eid == t.tx_eid,
                ).first()

                if first is not None:
                    continue  # Skip Existing

                truncated = Transaction()
                truncated.tx_site = t.tx_site
                truncated.tx_code = t.tx_code
                truncated.tx_type = t.tx_type
                truncated.tx_acct = t.tx_acct
                truncated.tx_oid = t.tx_oid
                truncated.tx_eid = t.tx_eid
                truncated.tx_time = t.tx_time.astimezone(utc)
                truncated.tx_inst = t.tx_inst
                truncated.tx_fund = t.tx_fund

                candidates[t] = truncated

            if len(candidates) > 0:
                session.add_all(candidates.values())
                session.commit()

        except BaseException as e:

            self.__logger.error('Transaction - %s : %s', type(e), e.args)

            session.rollback()

            raise e

        finally:

            session.close()

        return candidates.keys()

    def save_metrics(self, metrics, *,
                     gauge=Gauge('metric', 'Saved metric values', ('type', 'name'))
                     ):

        merged = []

        session = self.__session()

        try:

            for m in metrics if metrics is not None else []:

                if self._is_read_only():
                    self.__logger.debug("Skipping : %s", m)
                    continue

                if m is None:
                    continue

                value = Metric()
                value.mc_type = m.mc_type
                value.mc_time = m.mc_time.astimezone(utc)
                value.mc_name = m.mc_name
                value.mc_amnt = m.mc_amnt

                session.merge(value)

                merged.append(m)

            if len(merged) > 0:
                session.commit()

            for m in merged:
                g = m.mc_amnt if m.mc_amnt is not None else nan
                gauge.labels(m.mc_type, m.mc_name).set(g)

        except BaseException as e:

            self.__logger.error('Metric - %s : %s', type(e), e.args)

            session.rollback()

            raise e

        finally:

            session.close()

        return merged

    def delete_metrics(self, cutoff_time, *, exclude_minutes=None):

        session = self.__session()

        try:

            if self._is_read_only():

                self.__logger.debug("Skipping delete : cutoff=[%s], exclude=[%s]", cutoff_time, str(exclude_minutes))

                count = 0

            else:

                filters = [Metric.mc_time < cutoff_time]

                if exclude_minutes is not None and len(exclude_minutes) > 0:
                    filters.append(
                        cast(
                            func.extract('minute', Metric.mc_time),
                            Integer
                        ).notin_(exclude_minutes)
                    )

                count = session.query(Metric).filter(*filters).delete(synchronize_session='fetch')

                if count > 0:
                    session.commit()

        except BaseException as e:

            self.__logger.error('Delete - %s : %s', type(e), e.args)

            session.rollback()

            raise e

        finally:

            session.close()

        return count

    def fetch_tickers(self, time, *, include_expired=False):

        session = self.__session()

        try:

            latest = session.query(
                Ticker.tk_site,
                Ticker.tk_code,
                functions.max(Ticker.tk_time).label('tk_time')
            ).filter(
                Ticker.tk_time <= time,
                or_(
                    and_(Ticker.tk_ask.isnot(None), Ticker.tk_ask != self._ZERO),
                    and_(Ticker.tk_bid.isnot(None), Ticker.tk_bid != self._ZERO),
                    and_(Ticker.tk_ltp.isnot(None), Ticker.tk_ltp != self._ZERO),
                )
            ).group_by(
                Ticker.tk_site,
                Ticker.tk_code,
            ).subquery()

            inst = aliased(Evaluation, name='ev_inst')
            fund = aliased(Evaluation, name='ev_fund')

            results = session.query(
                Ticker, Product, inst, fund
            ).join(latest, and_(
                Ticker.tk_site == latest.c.tk_site,
                Ticker.tk_code == latest.c.tk_code,
                Ticker.tk_time == latest.c.tk_time,
            )).join(Product, and_(
                Product.pr_site == Ticker.tk_site,
                Product.pr_code == Ticker.tk_code,
                or_(
                    Product.pr_expr.is_(None),
                    Product.pr_expr >= time,
                    include_expired,
                ),
            )).outerjoin(inst, and_(
                inst.ev_site == Product.pr_site,
                inst.ev_unit == Product.pr_inst,
            )).outerjoin(fund, and_(
                fund.ev_site == Product.pr_site,
                fund.ev_unit == Product.pr_fund,
            )).all()

        finally:

            session.close()

        dto = namedtuple('TickerDto', ('ticker', 'product', 'inst', 'fund'))

        return [dto(*r) for r in results]

    def fetch_balances(self, time):

        session = self.__session()

        try:

            latest = session.query(
                Balance.bc_site,
                Balance.bc_acct,
                Balance.bc_unit,
                functions.max(Balance.bc_time).label('bc_time')
            ).filter(
                Balance.bc_time <= time
            ).group_by(
                Balance.bc_site,
                Balance.bc_acct,
                Balance.bc_unit,
            ).subquery()

            results = session.query(
                Balance, Account, Evaluation
            ).join(latest, and_(
                Balance.bc_site == latest.c.bc_site,
                Balance.bc_acct == latest.c.bc_acct,
                Balance.bc_unit == latest.c.bc_unit,
                Balance.bc_time == latest.c.bc_time,
            )).join(Account, and_(
                Account.ac_site == Balance.bc_site,
                Account.ac_acct == Balance.bc_acct,
                Account.ac_unit == Balance.bc_unit,
            )).join(Evaluation, and_(
                Evaluation.ev_site == Balance.bc_site,
                Evaluation.ev_unit == Balance.bc_unit,
            )).all()

        finally:

            session.close()

        dto = namedtuple('BalanceDto', ('balance', 'account', 'evaluation'))

        return [dto(*r) for r in results]

    def fetch_positions(self, time):

        session = self.__session()

        try:

            latest = session.query(
                Position.ps_site,
                Position.ps_code,
                functions.max(Position.ps_time).label('ps_time')
            ).filter(
                Position.ps_time <= time
            ).group_by(
                Position.ps_site,
                Position.ps_code,
            ).subquery()

            inst = aliased(Evaluation, name='ev_inst')
            fund = aliased(Evaluation, name='ev_fund')

            results = session.query(
                Position, Product, inst, fund
            ).join(latest, and_(
                Position.ps_site == latest.c.ps_site,
                Position.ps_code == latest.c.ps_code,
                Position.ps_time == latest.c.ps_time,
            )).join(Product, and_(
                Product.pr_site == Position.ps_site,
                Product.pr_code == Position.ps_code,
                or_(
                    Product.pr_expr.is_(None),
                    Product.pr_expr >= time,
                ),
            )).outerjoin(inst, and_(
                inst.ev_site == Product.pr_site,
                inst.ev_unit == Product.pr_inst,
            )).outerjoin(fund, and_(
                fund.ev_site == Product.pr_site,
                fund.ev_unit == Product.pr_fund,
            )).all()

        finally:

            session.close()

        dto = namedtuple('PositionDto', ('position', 'product', 'inst', 'fund'))

        return [dto(*r) for r in results]

    def fetch_transactions(self, start_time, end_time):

        session = self.__session()

        try:

            transactions = session.query(
                Transaction.tx_site,
                Transaction.tx_code,
                functions.count(Transaction.tx_time).label('tx_size'),
                functions.min(Transaction.tx_time).label('tx_time_min'),
                functions.max(Transaction.tx_time).label('tx_time_max'),
                functions.sum(Transaction.tx_inst).label('tx_net_inst'),
                functions.sum(Transaction.tx_fund).label('tx_net_fund'),
                functions.sum(func.abs(Transaction.tx_inst)).label('tx_grs_inst'),
                functions.sum(func.abs(Transaction.tx_fund)).label('tx_grs_fund'),
            ).filter(
                Transaction.tx_time >= start_time,
                Transaction.tx_time < end_time
            ).group_by(
                Transaction.tx_site,
                Transaction.tx_code,
            ).subquery()

            inst = aliased(Evaluation, name='ev_inst')
            fund = aliased(Evaluation, name='ev_fund')

            results = session.query(
                transactions, Product, inst, fund
            ).join(Product, and_(
                Product.pr_site == transactions.c.tx_site,
                Product.pr_code == transactions.c.tx_code,
            )).outerjoin(inst, and_(
                inst.ev_site == Product.pr_site,
                inst.ev_unit == Product.pr_inst,
            )).outerjoin(fund, and_(
                fund.ev_site == Product.pr_site,
                fund.ev_unit == Product.pr_fund,
            )).all()

        finally:

            session.close()

        dto = namedtuple('TransactionDto', (
            'tx_site', 'tx_code', 'tx_size', 'tx_time_min', 'tx_time_max',
            'tx_net_inst', 'tx_net_fund', 'tx_grs_inst', 'tx_grs_fund',
            'product', 'ev_inst', 'ev_fund'
        ))

        return [dto(*r) for r in results]


class AccountType(Enum):
    FUND = auto()
    CASH = auto()
    MARGIN = auto()


class UnitType(Enum):
    QTY = auto()
    JPY = auto()
    USD = auto()
    BTC = auto()
    BCH = auto()
    ETH = auto()
    ETC = auto()
    LTC = auto()


class TransactionType(Enum):
    TRADE = auto()
    SWAP = auto()


class BaseEntity:
    @staticmethod
    def _to_string(value):
        if isinstance(value, dict):
            return str({BaseEntity._to_string(k): BaseEntity._to_string(v) for k, v in value.items()})

        if isinstance(value, Enum):
            return value.name

        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d %H:%M:%S.%f %Z')

        return str(value)


class Product(CryptowelderContext.ENTITY_BASE, BaseEntity):
    __tablename__ = "t_product"
    pr_site = Column(String, primary_key=True)
    pr_code = Column(String, primary_key=True)
    pr_inst = Column(String)
    pr_fund = Column(String)
    pr_disp = Column(String)
    pr_expr = Column(DateTime)

    def __str__(self):
        return BaseEntity._to_string({
            'table': self.__tablename__,
            'site': self.pr_site,
            'code': self.pr_code,
            'inst': self.pr_inst,
            'fund': self.pr_fund,
            'disp': self.pr_disp,
            'expr': self.pr_expr,
        })


class Evaluation(CryptowelderContext.ENTITY_BASE, BaseEntity):
    __tablename__ = "t_evaluation"
    ev_site = Column(String, primary_key=True)
    ev_unit = Column(String, primary_key=True)
    ev_ticker_site = Column(String)
    ev_ticker_code = Column(String)
    ev_convert_site = Column(String)
    ev_convert_code = Column(String)

    def __str__(self):
        return BaseEntity._to_string({
            'table': self.__tablename__,
            'site': self.ev_site,
            'unit': self.ev_unit,
            't_site': self.ev_ticker_site,
            't_code': self.ev_ticker_code,
            'c_site': self.ev_convert_site,
            'c_code': self.ev_convert_code,
        })


class Account(CryptowelderContext.ENTITY_BASE, BaseEntity):
    __tablename__ = "t_account"
    ac_site = Column(String, primary_key=True)
    ac_acct = Column(String, primary_key=True)
    ac_unit = Column(String, primary_key=True)
    ac_disp = Column(String)

    def __str__(self):
        return BaseEntity._to_string({
            'table': self.__tablename__,
            'site': self.ac_site,
            'acct': self.ac_acct,
            'unit': self.ac_unit,
            'disp': self.ac_disp,
        })


class Ticker(CryptowelderContext.ENTITY_BASE, BaseEntity):
    __tablename__ = "t_ticker"
    tk_site = Column(String, primary_key=True)
    tk_code = Column(String, primary_key=True)
    tk_time = Column(DateTime, primary_key=True)
    tk_ask = Column(Numeric)
    tk_bid = Column(Numeric)
    tk_ltp = Column(Numeric)

    def __str__(self):
        return BaseEntity._to_string({
            'table': self.__tablename__,
            'site': self.tk_site,
            'code': self.tk_code,
            'time': self.tk_time,
            'ask': self.tk_ask,
            'bid': self.tk_bid,
            'ltp': self.tk_ltp,
        })


class Balance(CryptowelderContext.ENTITY_BASE, BaseEntity):
    __tablename__ = "t_balance"
    bc_site = Column(String, primary_key=True)
    bc_acct = Column(Type(AccountType), primary_key=True)
    bc_unit = Column(Type(UnitType), primary_key=True)
    bc_time = Column(DateTime, primary_key=True)
    bc_amnt = Column(Numeric)

    def __str__(self):
        return BaseEntity._to_string({
            'table': self.__tablename__,
            'site': self.bc_site,
            'account': self.bc_acct,
            'unit': self.bc_unit,
            'time': self.bc_time,
            'amount': self.bc_amnt,
        })


class Position(CryptowelderContext.ENTITY_BASE, BaseEntity):
    __tablename__ = "t_position"
    ps_site = Column(String, primary_key=True)
    ps_code = Column(String, primary_key=True)
    ps_time = Column(DateTime, primary_key=True)
    ps_inst = Column(Numeric)
    ps_fund = Column(Numeric)

    def __str__(self):
        return BaseEntity._to_string({
            'table': self.__tablename__,
            'site': self.ps_site,
            'code': self.ps_code,
            'time': self.ps_time,
            'instrument': self.ps_inst,
            'funding': self.ps_fund,
        })


class Transaction(CryptowelderContext.ENTITY_BASE, BaseEntity):
    __tablename__ = 't_transaction'
    tx_site = Column(String, primary_key=True)
    tx_code = Column(String, primary_key=True)
    tx_type = Column(Type(TransactionType), primary_key=True)
    tx_acct = Column(Type(AccountType), primary_key=True)
    tx_oid = Column(String, primary_key=True)
    tx_eid = Column(String, primary_key=True)
    tx_time = Column(DateTime, nullable=False)
    tx_inst = Column(Numeric)
    tx_fund = Column(Numeric)

    def __str__(self):
        return BaseEntity._to_string({
            'table': self.__tablename__,
            'site': self.tx_site,
            'code': self.tx_code,
            'type': self.tx_type,
            'acct': self.tx_acct,
            'oid': self.tx_oid,
            'eid': self.tx_eid,
            'time': self.tx_time,
            'instrument': self.tx_inst,
            'funding': self.tx_fund,
        })


class Metric(CryptowelderContext.ENTITY_BASE, BaseEntity):
    __tablename__ = 't_metric'
    mc_type = Column(String, primary_key=True)
    mc_time = Column(DateTime, primary_key=True)
    mc_name = Column(String, primary_key=True)
    mc_amnt = Column(Numeric)

    def __str__(self):
        return BaseEntity._to_string({
            'table': self.__tablename__,
            'type': self.mc_type,
            'time': self.mc_time,
            'name': self.mc_name,
            'amnt': self.mc_amnt,
        })
