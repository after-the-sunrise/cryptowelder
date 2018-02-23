--
-- Ticker
--
DROP TABLE IF EXISTS t_ticker;

CREATE TABLE t_ticker
(
  tk_site VARCHAR(16) NOT NULL,
  tk_code VARCHAR(32) NOT NULL,
  tk_time TIMESTAMP   NOT NULL,
  tk_ask  DECIMAL(32, 16),
  tk_bid  DECIMAL(32, 16),
  tk_ltp  DECIMAL(32, 16)
);

ALTER TABLE t_ticker
  ADD CONSTRAINT i_ticker_0
PRIMARY KEY
  (
    tk_site,
    tk_code,
    tk_time
  );

CREATE INDEX i_ticker_1
  ON t_ticker
  (
    tk_time
  );

--
-- Balance
--
DROP TABLE IF EXISTS t_balance;

CREATE TABLE t_balance
(
  bc_site VARCHAR(16) NOT NULL,
  bc_acct VARCHAR(16) NOT NULL,
  bc_unit VARCHAR(16) NOT NULL,
  bc_time TIMESTAMP   NOT NULL,
  bc_amnt DECIMAL(32, 16)
);

ALTER TABLE t_balance
  ADD CONSTRAINT i_balance_0
PRIMARY KEY
  (
    bc_site,
    bc_acct,
    bc_unit,
    bc_time
  );

CREATE INDEX i_balance_1
  ON t_balance
  (
    bc_time
  );

--
-- Position
--
DROP TABLE IF EXISTS t_position;

CREATE TABLE t_position
(
  ps_site VARCHAR(16) NOT NULL,
  ps_code VARCHAR(32) NOT NULL,
  ps_time TIMESTAMP   NOT NULL,
  ps_inst DECIMAL(32, 16),
  ps_fund DECIMAL(32, 16)
);

ALTER TABLE t_position
  ADD CONSTRAINT i_position_0
PRIMARY KEY
  (
    ps_site,
    ps_code,
    ps_time
  );

CREATE INDEX i_position_1
  ON t_position
  (
    ps_time
  );

--
-- Transaction
--
DROP TABLE IF EXISTS t_transaction;

CREATE TABLE t_transaction
(
  tx_site VARCHAR(16) NOT NULL,
  tx_code VARCHAR(32) NOT NULL,
  tx_type VARCHAR(16) NOT NULL,
  tx_oid  VARCHAR(64) NOT NULL,
  tx_eid  VARCHAR(64) NOT NULL,
  tx_time TIMESTAMP   NOT NULL,
  tx_inst DECIMAL(32, 16),
  tx_fund DECIMAL(32, 16)
);

ALTER TABLE t_transaction
  ADD CONSTRAINT i_transaction_0
PRIMARY KEY
  (
    tx_site,
    tx_code,
    tx_type,
    tx_oid,
    tx_eid
  );

CREATE INDEX i_transaction_1
  ON t_transaction
  (
    tx_time
  );
