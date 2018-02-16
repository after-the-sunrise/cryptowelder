DROP TABLE IF EXISTS t_ticker;

CREATE TABLE t_ticker
(
  tk_site    VARCHAR(36) NOT NULL,
  tk_product VARCHAR(36) NOT NULL,
  tk_time    TIMESTAMP   NOT NULL,
  tk_ask     DECIMAL(20, 8),
  tk_bid     DECIMAL(20, 8),
  tk_ltp     DECIMAL(20, 8)
);

ALTER TABLE t_ticker
  ADD CONSTRAINT i_ticker_0
PRIMARY KEY
  (
    tk_site,
    tk_product,
    tk_time
  );

CREATE INDEX i_ticker_1
  ON t_ticker
  (
    tk_time
  );


DROP TABLE IF EXISTS t_transaction;

CREATE TABLE t_transaction
(
  tx_site    VARCHAR(36)    NOT NULL,
  tx_product VARCHAR(36)    NOT NULL,
  tx_id      VARCHAR(36)    NOT NULL,
  tx_time    TIMESTAMP      NOT NULL,
  tx_inst    DECIMAL(20, 8) NOT NULL,
  tx_fund    DECIMAL(20, 8) NOT NULL
);

ALTER TABLE t_transaction
  ADD CONSTRAINT i_transaction_0
PRIMARY KEY
  (
    tx_site,
    tx_product,
    tx_id
  );

CREATE INDEX i_transaction_1
  ON t_transaction
  (
    tx_time
  );

DROP TABLE IF EXISTS t_balance;

CREATE TABLE t_balance
(
  bc_site VARCHAR(36) NOT NULL,
  bc_acct VARCHAR(36) NOT NULL,
  bc_unit VARCHAR(36) NOT NULL,
  bc_time TIMESTAMP   NOT NULL,
  bc_amnt VARCHAR(36) NOT NULL
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
