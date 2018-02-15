DROP TABLE IF EXISTS t_transaction;

CREATE TABLE
  t_transaction
(
  tx_site    VARCHAR(36)    NOT NULL,
  tx_product VARCHAR(36)    NOT NULL,
  tx_id      VARCHAR(36)    NOT NULL,
  tx_time    TIMESTAMP      NOT NULL,
  tx_inst    DECIMAL(20, 8) NOT NULL,
  tx_fund    DECIMAL(20, 8) NOT NULL
);

ALTER TABLE
t_transaction
  ADD CONSTRAINT
  i_transaction_0
PRIMARY KEY (
    tx_site,
    tx_product,
    tx_id
  );

CREATE INDEX
  i_transaction_1
  ON
    t_transaction
    (
      tx_time,
      tx_site,
      tx_product
    );
