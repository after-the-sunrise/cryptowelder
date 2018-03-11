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
        t1.tk_time = (
          SELECT max(tk_time)
          FROM t_ticker
          WHERE tk_site = e.ev_ticker_site AND tk_code = e.ev_ticker_code AND tk_time <= t.ts_time
        )
    LEFT OUTER JOIN
    t_ticker t2
      ON
        t2.tk_site = e.ev_convert_site
        AND
        t2.tk_code = e.ev_convert_code
        AND
        t2.tk_time = (
          SELECT max(tk_time)
          FROM t_ticker
          WHERE tk_site = e.ev_convert_site AND tk_code = e.ev_convert_code AND tk_time <= t.ts_time
        );

CREATE OR REPLACE VIEW v_product AS
  SELECT
    ts.*,
    pr.*,
    ei.ev_rate AS "ev_inst",
    ef.ev_rate AS "ev_fund"
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

CREATE OR REPLACE VIEW v_ticker AS
  SELECT
    t.*,
    p.*,
    COALESCE((t.tk_ask + t.tk_bid) * 0.5, t.tk_ltp) * p.ev_fund AS tk_mtm
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

CREATE OR REPLACE VIEW v_balance AS
  SELECT
    e.*,
    a.*,
    b.*,
    b.bc_amnt * e.ev_rate AS ev_amnt
  FROM
    v_evaluation e
    JOIN
    t_balance b
      ON
        b.bc_site = e.ev_site
        AND
        b.bc_unit = e.ev_unit
        AND
        b.bc_time = (
          SELECT max(bc_time)
          FROM t_balance
          WHERE bc_site = e.ev_site AND bc_unit = e.ev_unit AND bc_time <= e.ts_time
        )
    LEFT OUTER JOIN
    t_account a
      ON
        a.ac_site = b.bc_site
        AND
        a.ac_acct = b.bc_acct
        AND
        a.ac_unit = b.bc_unit;

CREATE OR REPLACE VIEW v_position AS
  SELECT
    pr.*,
    ps.*,
    ps.ps_inst * pr.ev_inst AS "ps_amnt_inst",
    ps.ps_fund * pr.ev_fund AS "ps_amnt_fund"
  FROM
    v_product pr
    LEFT OUTER JOIN
    t_position ps
      ON
        ps.ps_site = pr.pr_site
        AND
        ps.ps_code = pr.pr_code
        AND
        ps.ps_time = (
          SELECT max(ps_time)
          FROM t_position
          WHERE ps_site = pr.pr_site AND ps_code = pr.pr_code AND ps_time <= pr.ts_time
        )
  WHERE
    pr.pr_expr IS NULL
    OR
    pr.pr_expr >= ps.ps_time;

CREATE OR REPLACE VIEW v_transaction AS
  SELECT
    cast(
        (p.ts_time + INTERVAL '9 hour') AT TIME ZONE 'Asia/Tokyo' AS DATE
    )                               AS "ts_date",
    p.ts_time,
    p.pr_site,
    p.pr_code,
    sum(t.tx_inst)                  AS "tx_net_inst",
    sum(t.tx_fund)                  AS "tx_net_fund",
    sum(abs(t.tx_inst))             AS "tx_grs_inst",
    sum(abs(t.tx_fund))             AS "tx_grs_fund",
    sum(t.tx_inst) * p.ev_inst      AS "ev_net_inst",
    sum(t.tx_fund) * p.ev_fund      AS "ev_net_fund",
    sum(abs(t.tx_inst)) * p.ev_inst AS "ev_grs_inst",
    sum(abs(t.tx_fund)) * p.ev_fund AS "ev_grs_fund"
  FROM
    v_product p
    LEFT OUTER JOIN
    t_transaction t
      ON
        t.tx_site = p.pr_site
        AND
        t.tx_code = p.pr_code
        AND
        t.tx_time <= p.ts_time
        AND
        cast((t.tx_time + INTERVAL '9 hour') AT TIME ZONE 'Asia/Tokyo' AS DATE)
        =
        cast((p.ts_time + INTERVAL '9 hour') AT TIME ZONE 'Asia/Tokyo' AS DATE)
  GROUP BY
    p.ts_time,
    p.pr_site,
    p.pr_code,
    p.ev_inst,
    p.ev_fund;
