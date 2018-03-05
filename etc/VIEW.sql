--
-- Shortcut for evaluation rate.
--
CREATE OR REPLACE VIEW v_evaluation AS
  SELECT
    t.*,
    e.*,
    CASE WHEN e.ev_ticker_site IS NOT NULL
      THEN COALESCE((t1.tk_ask + t1.tk_bid) * 0.5, t1.tk_ltp)
    ELSE 1 END
    *
    CASE WHEN e.ev_convert_site IS NOT NULL
      THEN COALESCE((t2.tk_ask + t2.tk_bid) * 0.5, t2.tk_ltp)
    ELSE 1 END
      AS ev_rate
  FROM
    t_timestamp t
    CROSS JOIN
    t_evaluation e
    LEFT OUTER JOIN
    t_ticker t1
      ON
        t1.tk_site = e.ev_ticker_site
        AND
        t1.tk_code = e.ev_ticker_code
        AND
        t1.tk_time = t.ts_time
    LEFT OUTER JOIN
    t_ticker t2
      ON
        t2.tk_site = e.ev_convert_site
        AND
        t2.tk_code = e.ev_convert_code
        AND
        t2.tk_time = t.ts_time;

--
-- Shortcut for product instrument and funding evaluation.
--
CREATE OR REPLACE VIEW v_product AS
  SELECT
    ts.*,
    pr.*,
    ei.ev_rate AS "ev_rate_inst",
    ef.ev_rate AS "ev_rate_fund"
  FROM
    t_timestamp ts
    CROSS JOIN
    t_product pr
    LEFT OUTER JOIN
    v_evaluation ei
      ON
        ei.ts_time = ts.ts_time
        AND
        ei.ev_site = pr.pr_site
        AND
        ei.ev_unit = pr.pr_inst
    LEFT OUTER JOIN
    v_evaluation ef
      ON
        ef.ts_time = ts.ts_time
        AND
        ef.ev_site = pr.pr_site
        AND
        ef.ev_unit = pr.pr_fund;

--
-- Tickers with evaluation price.
--
-- [Grafana]
-- SELECT pr_disp AS metric, tk_time AS time, tk_mtm AS price FROM v_ticker
--   WHERE $__timeFilter(tk_time)
--   AND pr_inst = 'BTC' ORDER BY tk_time, pr_disp
--
-- [Actual]
-- SELECT pr_disp AS metric, tk_time AS time, tk_mtm AS price FROM v_ticker
--   WHERE extract(epoch from tk_time)
--     BETWEEN extract(epoch from now() - INTERVAL '1 day') AND extract(epoch from now())
--   AND pr_inst = 'BTC' ORDER BY time, metric
--
CREATE OR REPLACE VIEW v_ticker AS
  SELECT
    t.*,
    p.*,
    COALESCE((t.tk_ask + t.tk_bid) * 0.5, t.tk_ltp) * p.ev_rate_fund AS tk_mtm
  FROM
    t_ticker t
    LEFT OUTER JOIN
    v_product p
      ON
        p.pr_site = t.tk_site
        AND
        p.pr_code = t.tk_code
        AND
        p.ts_time = t.tk_time;

--
-- Ticker ratio with evaluation price.
--
-- [Grafana]
-- SELECT time, metric, ratio FROM v_ticker_ratio
--   WHERE $__timeFilter(time)
--   ORDER BY time, metric
--
-- [Actual]
-- SELECT time, metric, ratio FROM v_ticker_ratio
--   WHERE extract(epoch from time)
--     BETWEEN extract(epoch from now() - INTERVAL '1 day') AND extract(epoch from now())
--   ORDER BY time, metric
--
CREATE OR REPLACE VIEW v_ticker_ratio AS
  WITH w_ticker AS (
      SELECT *
      FROM v_ticker
  )
  SELECT
    t1.tk_time                AS "time",
    t1.pr_disp                AS "metric",
    t1.tk_mtm / t2.tk_mtm - 1 AS "ratio"
  FROM
    w_ticker t1,
    w_ticker t2
  WHERE
    t1.tk_time = t2.tk_time
    AND
    t1.pr_inst = 'BTC'
    AND
    t2.tk_site = 'bitflyer' AND t2.tk_code = 'BTC_JPY';

--
-- Balance with amounts converted to evaluation unit.
--
CREATE OR REPLACE VIEW v_balance AS
  SELECT
    b.*,
    a.*,
    e.*,
    b.bc_amnt * e.ev_rate AS ev_amnt
  FROM
    t_balance b
    LEFT OUTER JOIN
    t_account a
      ON
        b.bc_site = a.ac_site
        AND
        b.bc_acct = a.ac_acct
        AND
        b.bc_unit = a.ac_unit
    LEFT OUTER JOIN
    v_evaluation e
      ON
        b.bc_site = e.ev_site
        AND
        b.bc_unit = e.ev_unit
        AND
        b.bc_time = e.ts_time;

--
-- Position with funding amount converted to evaluation unit.
--
CREATE OR REPLACE VIEW v_position AS
  SELECT
    p.*,
    t.*,
    p.ps_inst * t.ev_rate_inst AS "ps_eval_inst",
    p.ps_fund * t.ev_rate_fund AS "ps_eval_fund"
  FROM
    t_position p
    LEFT OUTER JOIN
    v_ticker t
      ON
        p.ps_site = t.tk_site
        AND
        p.ps_code = t.tk_code
        AND
        p.ps_time = t.tk_time;

--
-- Shortcut for Grafana to fetch all assets in evaluation unit.
--
-- [Grafana]
-- SELECT time, metric, SUM(amount) FROM v_asset
--   WHERE $__timeFilter(time)
--   GROUP BY time, metric ORDER BY time, metric
--
-- [Actual]
-- SELECT time, metric, SUM(amount) FROM v_asset
--   WHERE extract(epoch from time) BETWEEN extract(epoch from now() - INTERVAL '1 day') AND extract(epoch from now())
--   GROUP BY time, metric ORDER BY time, metric
--
CREATE OR REPLACE VIEW v_asset AS
  SELECT
    bc_time AS "time",
    ac_disp AS "metric",
    ev_amnt AS "amount"
  FROM
    v_balance
  WHERE
    ac_disp IS NOT NULL
  UNION
  SELECT
    ps_time      AS "time",
    pr_disp      AS "metric",
    ps_eval_fund AS "amount"
  FROM
    v_position
  WHERE
    pr_disp IS NOT NULL;

--
-- Shortcut for Grafana to fetch all exposures.
--
-- [Grafana]
-- SELECT time, metric, amount FROM v_exposure
--   WHERE $__timeFilter(time)
--   AND unit = 'BTC' ORDER BY time, metric
--
-- [Actual]
-- SELECT time, metric, amount FROM v_exposure
--   WHERE extract(epoch from time) BETWEEN extract(epoch from now() - INTERVAL '1 day') AND extract(epoch from now())
--   AND unit = 'BTC' ORDER BY time, metric
--
CREATE OR REPLACE VIEW v_exposure AS
  SELECT
    bc_time AS "time",
    ac_disp AS "metric",
    bc_unit AS "unit",
    bc_amnt AS "amount"
  FROM
    v_balance
  UNION
  SELECT
    ps_time AS "time",
    pr_disp AS "metric",
    pr_inst AS "unit",
    ps_inst AS "amount"
  FROM
    v_position;

--
-- Cash amount ratio of BTC / JPY.
--
-- [Grafana]
-- SELECT time, ratio FROM v_ratio_cash_btc WHERE metric = 'bitflyer'
-- AND $__timeFilter(time)
-- ORDER BY time
--
-- [Actual]
-- SELECT time, ratio FROM v_ratio_cash_btc WHERE metric = 'bitflyer'
-- AND extract(epoch from time) BETWEEN extract(epoch from now() - INTERVAL '1 day') AND extract(epoch from now())
-- ORDER BY time
--
CREATE OR REPLACE VIEW v_ratio_cash_btc AS
  SELECT
    b1.bc_site              AS "metric",
    b1.bc_time              AS "time",
    b1.ev_amnt / b2.ev_amnt AS "ratio"
  FROM
    v_balance b1,
    v_balance b2
  WHERE
    b1.bc_site = b2.bc_site
    AND
    b1.bc_time = b2.bc_time
    AND
    (b1.bc_acct, b2.bc_acct) = ('CASH', 'CASH')
    AND
    (b1.bc_unit, b2.bc_unit) = ('BTC', 'JPY');

--
-- Transactions aggregated per timestamp.
-- TODO : FX evaluation price.
--
CREATE OR REPLACE VIEW v_transaction AS
  SELECT
    pr.ts_time,
    pr.pr_site,
    pr.pr_code,
    pr.pr_disp,
    pr.ev_rate_inst,
    pr.ev_rate_fund,
    sum(abs(tx.tx_inst))                   AS tx_grs_inst,
    sum(abs(tx.tx_fund))                   AS tx_grs_fund,
    sum(tx.tx_inst)                        AS tx_net_inst,
    sum(tx.tx_fund)                        AS tx_net_fund,
    sum(abs(tx.tx_inst * pr.ev_rate_inst)) AS tx_amnt_grs_inst,
    sum(abs(tx.tx_fund * pr.ev_rate_fund)) AS tx_amnt_grs_fund,
    sum(tx.tx_inst * pr.ev_rate_inst)      AS tx_amnt_net_inst,
    sum(tx.tx_fund * pr.ev_rate_fund)      AS tx_amnt_net_fund,
    count(tx.*)                            AS tx_count
  FROM
    v_product pr
    LEFT OUTER JOIN
    t_transaction tx
      ON
        cast((tx.tx_time + INTERVAL '9 hour') AT TIME ZONE 'Asia/Tokyo' AS DATE)
        =
        cast((pr.ts_time + INTERVAL '9 hour') AT TIME ZONE 'Asia/Tokyo' AS DATE)
        AND
        date_trunc('minute', tx.tx_time) <= pr.ts_time
        AND
        tx.tx_site = pr.pr_site
        AND
        tx.tx_code = pr.pr_code
        AND
        tx.tx_type = 'TRADE'
  WHERE
    cast(extract(MINUTE FROM pr.ts_time) AS INTEGER) % 15 = 0
  GROUP BY
    pr.ts_time,
    pr.pr_site,
    pr.pr_code,
    pr.pr_disp,
    pr.ev_rate_inst,
    pr.ev_rate_fund
  HAVING
    count(tx.*) > 0;
