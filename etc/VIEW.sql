-- Drop views first for dependency issues.
DROP VIEW IF EXISTS v_ratio_cash_btc;
DROP VIEW IF EXISTS v_asset;
DROP VIEW IF EXISTS v_position;
DROP VIEW IF EXISTS v_balance;
DROP VIEW IF EXISTS v_ticker;

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
CREATE VIEW v_ticker AS
  SELECT
    t.*,
    p.*,
    e.*,
    COALESCE((t.tk_ask + t.tk_bid) * 0.5, t.tk_ltp)
    *
    CASE WHEN e.ev_ticker_site IS NOT NULL
      THEN COALESCE((t1.tk_ask + t1.tk_bid) * 0.5, t1.tk_ltp)
    ELSE 1 END
    *
    CASE WHEN e.ev_convert_site IS NOT NULL
      THEN COALESCE((t2.tk_ask + t2.tk_bid) * 0.5, t2.tk_ltp)
    ELSE 1 END
      AS tk_mtm
  FROM
    t_ticker t
    JOIN
    t_product p
      ON p.pr_site = t.tk_site
         AND
         p.pr_code = t.tk_code
    JOIN
    t_evaluation e
      ON
        e.ev_site = p.pr_site
        AND
        e.ev_unit = p.pr_fund
    LEFT OUTER JOIN
    t_ticker t1
      ON
        t1.tk_site = e.ev_ticker_site
        AND
        t1.tk_code = e.ev_ticker_code
        AND
        t1.tk_time = t.tk_time
    LEFT OUTER JOIN
    t_ticker t2
      ON
        t2.tk_site = e.ev_convert_site
        AND
        t2.tk_code = e.ev_convert_code
        AND
        t2.tk_time = t.tk_time;

--
-- Balance with amounts converted to evaluation unit.
--
CREATE VIEW v_balance AS
  SELECT
    e.ev_disp,
    b.bc_site,
    b.bc_acct,
    b.bc_unit,
    b.bc_time,
    b.bc_amnt,
    b.bc_amnt
    * CASE WHEN e.ev_ticker_site IS NOT NULL
      THEN COALESCE((t1.tk_ask + t1.tk_bid) * 0.5, t1.tk_ltp)
      ELSE 1 END
    * CASE WHEN e.ev_convert_site IS NOT NULL
      THEN COALESCE((t2.tk_ask + t2.tk_bid) * 0.5, t2.tk_ltp)
      ELSE 1 END
      AS "amount"
  FROM
    t_evaluation e
    LEFT OUTER JOIN
    t_balance b
      ON
        b.bc_site = e.ev_site
        AND
        b.bc_acct = e.ev_acct
        AND
        b.bc_unit = e.ev_unit
    LEFT OUTER JOIN
    t_ticker t1
      ON
        t1.tk_site = e.ev_ticker_site
        AND
        t1.tk_code = e.ev_ticker_code
        AND
        t1.tk_time = b.bc_time
    LEFT OUTER JOIN
    t_ticker t2
      ON
        t2.tk_site = e.ev_convert_site
        AND
        t2.tk_code = e.ev_convert_code
        AND
        t2.tk_time = b.bc_time;

--
-- Position with funding amount converted to evaluation unit.
--
CREATE VIEW v_position AS
  SELECT
    pr.pr_disp,
    ps.ps_site,
    ps.ps_code,
    pr.pr_inst,
    ps.ps_time,
    ps.ps_inst,
    ps.ps_fund
    * CASE WHEN ev.ev_ticker_site IS NOT NULL
      THEN COALESCE((t1.tk_ask + t1.tk_bid) * 0.5, t1.tk_ltp)
      ELSE 1 END
    * CASE WHEN ev.ev_convert_site IS NOT NULL
      THEN COALESCE((t2.tk_ask + t2.tk_bid) * 0.5, t2.tk_ltp)
      ELSE 1 END
      AS "amount"
  FROM
    t_position ps
    JOIN
    t_product pr
      ON
        pr.pr_site = ps.ps_site
        AND
        pr.pr_code = ps.ps_code
        AND
        (
          pr.pr_expr IS NULL
          OR
          pr.pr_expr < ps.ps_time
        )
    JOIN
    t_evaluation ev
      ON
        ev.ev_site = pr.pr_site
        AND
        ev.ev_acct = 'MARGIN'
        AND
        ev.ev_unit = pr.pr_fund
    LEFT OUTER JOIN
    t_ticker t1
      ON
        t1.tk_site = ev.ev_ticker_site
        AND
        t1.tk_code = ev.ev_ticker_code
        AND
        t1.tk_time = ps.ps_time
    LEFT OUTER JOIN
    t_ticker t2
      ON
        t2.tk_site = ev.ev_convert_site
        AND
        t2.tk_code = ev.ev_convert_code
        AND
        t2.tk_time = ps.ps_time;

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
CREATE VIEW v_asset AS
  SELECT
    bc_time AS "time",
    ev_disp AS "metric",
    amount
  FROM
    v_balance
  UNION
  SELECT
    ps_time AS "time",
    pr_disp AS "metric",
    amount
  FROM
    v_position;

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
CREATE VIEW v_exposure AS
  SELECT
    bc_time AS "time",
    ev_disp AS "metric",
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
CREATE VIEW v_ratio_cash_btc AS
  SELECT
    b1.bc_site            AS "metric",
    b1.bc_time            AS "time",
    b1.amount / b2.amount AS "ratio"
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
