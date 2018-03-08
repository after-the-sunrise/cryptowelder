--
-- Product
--
CREATE TABLE t_product
(
  pr_site VARCHAR(16) NOT NULL,
  pr_code VARCHAR(32) NOT NULL,
  pr_inst VARCHAR(16) NOT NULL,
  pr_fund VARCHAR(16) NOT NULL,
  pr_disp VARCHAR(16) NOT NULL,
  pr_expr TIMESTAMP
);

ALTER TABLE t_product
  ADD CONSTRAINT t_product_0
PRIMARY KEY
  (
    pr_site,
    pr_code
  );

--
-- Evaluation
--
CREATE TABLE t_evaluation
(
  ev_site         VARCHAR(16) NOT NULL,
  ev_unit         VARCHAR(16) NOT NULL,
  ev_ticker_site  VARCHAR(16),
  ev_ticker_code  VARCHAR(32),
  ev_convert_site VARCHAR(16),
  ev_convert_code VARCHAR(32)
);

ALTER TABLE t_evaluation
  ADD CONSTRAINT t_evaluation_0
PRIMARY KEY
  (
    ev_site,
    ev_unit
  );

--
-- Account
--
CREATE TABLE t_account
(
  ac_site VARCHAR(16) NOT NULL,
  ac_acct VARCHAR(16) NOT NULL,
  ac_unit VARCHAR(16) NOT NULL,
  ac_disp VARCHAR(16) NOT NULL
);

ALTER TABLE t_account
  ADD CONSTRAINT i_account_0
PRIMARY KEY
  (
    ac_site,
    ac_acct,
    ac_unit
  );

--
-- Timestamp
--
CREATE TABLE t_timestamp (
  ts_time TIMESTAMP NOT NULL
);

ALTER TABLE t_timestamp
  ADD CONSTRAINT i_timestamp_0
PRIMARY KEY
  (
    ts_time
  );

--
-- Ticker
--
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
    tk_time,
    tk_site,
    tk_code
  );

--
-- Balance
--
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
    bc_time,
    bc_site,
    bc_acct,
    bc_unit
  );

--
-- Position
--
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
    ps_time,
    ps_site,
    ps_code
  );

--
-- Transaction
--
CREATE TABLE t_transaction
(
  tx_site VARCHAR(16) NOT NULL,
  tx_code VARCHAR(32) NOT NULL,
  tx_type VARCHAR(16) NOT NULL,
  tx_acct VARCHAR(16) NOT NULL,
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
    tx_acct,
    tx_oid,
    tx_eid
  );

CREATE INDEX i_transaction_1
  ON t_transaction
  (
    tx_time,
    tx_site,
    tx_code,
    tx_type,
    tx_acct
  );
