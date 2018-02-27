--
-- t_product
--
TRUNCATE TABLE t_product;

INSERT INTO t_product (pr_site, pr_code, pr_inst, pr_fund, pr_disp, pr_expr)
VALUES
  ('bitbank', 'btc_jpy', 'BTC', 'JPY', 'BBK BTC', NULL),
  ('bitfinex', 'btcusd', 'BTC', 'USD', 'BFN BTC', NULL),
  ('bitflyer', 'BTC_JPY', 'BTC', 'JPY', 'BFL BTC', NULL),
  ('bitflyer', 'ETH_BTC', 'ETH', 'BTC', 'BFL ETH', NULL),
  ('bitflyer', 'BCH_BTC', 'BCH', 'BTC', 'BFL BCH', NULL),
  ('bitflyer', 'FX_BTC_JPY', 'BTC', 'JPY', 'BFL BFX', NULL),
  ('bitmex', 'XBTUSD', 'BTC', 'USD', 'BMX XBT', NULL),
  ('btcbox', 'btc', 'BTC', 'JPY', 'BOX BTC', NULL),
  ('coincheck', 'btc_jpy', 'BTC', 'JPY', 'CCK BTC', NULL),
  ('oanda', 'USD_JPY', 'USD', 'JPY', 'OND USD', NULL),
  ('polonex', 'USDT_BTC', 'BTC', 'USD', 'PLX BTC', NULL),
  ('quoinex', 'BTCJPY', 'BTC', 'JPY', 'QNX BTC', NULL),
  ('zaif', 'btc_jpy', 'BTC', 'JPY', 'ZIF BTC', NULL);

--
-- t_evaluation
--
TRUNCATE TABLE t_evaluation;

INSERT INTO t_evaluation (ev_site, ev_acct, ev_unit, ev_disp, ev_ticker_site, ev_ticker_code, ev_convert_site, ev_convert_code)
VALUES
  ('bitbank', 'CASH', 'JPY', 'BBK JPY', NULL, NULL, NULL, NULL),
  ('bitbank', 'CASH', 'BTC', 'BBK BTC', 'bitbank', 'btc_jpy', NULL, NULL),
  ('bitfinex', 'CASH', 'USD', 'BFN USD', 'oanda', 'USD_JPY', NULL, NULL),
  ('bitflyer', 'CASH', 'JPY', 'BFL JPY', NULL, NULL, NULL, NULL),
  ('bitflyer', 'CASH', 'BTC', 'BFL BTC', 'bitflyer', 'BTC_JPY', NULL, NULL),
  ('bitflyer', 'MARGIN', 'JPY', 'BFL JPYC', NULL, NULL, NULL, NULL),
  ('bitflyer', 'MARGIN', 'BTC', 'BFL BTCC', 'bitflyer', 'BTC_JPY', NULL, NULL),
  ('bitflyer', 'CASH', 'ETH', 'BFL ETH', 'bitflyer', 'ETH_BTC', 'bitflyer', 'BTC_JPY'),
  ('bitflyer', 'CASH', 'BCH', 'BFL BCH', 'bitflyer', 'BCH_BTC', 'bitflyer', 'BTC_JPY'),
  ('bitmex', 'MARGIN', 'USD', 'BMX USD', 'oanda', 'USD_JPY', NULL, NULL),
  ('bitmex', 'MARGIN', 'BTC', 'BMX XBT', 'bitflyer', 'BTC_JPY', NULL, NULL),
  ('btcbox', 'CASH', 'JPY', 'BOX JPY', NULL, NULL, NULL, NULL),
  ('btcbox', 'CASH', 'BTC', 'BOX BTC', 'btcbox', 'btc', NULL, NULL),
  ('coincheck', 'CASH', 'JPY', 'CCK JPY', NULL, NULL, NULL, NULL),
  ('coincheck', 'CASH', 'BTC', 'CCK BTC', 'coincheck', 'btc_jpy', NULL, NULL),
  ('poloniex', 'CASH', 'USD', 'PLX USD', 'oanda', 'USD_JPY', NULL, NULL),
  ('quoinex', 'CASH', 'JPY', 'QNX JPY', NULL, NULL, NULL, NULL),
  ('quoinex', 'CASH', 'BTC', 'QNX BTC', 'quoinex', 'BTCJPY', NULL, NULL),
  ('zaif', 'CASH', 'JPY', 'ZIF JPY', NULL, NULL, NULL, NULL),
  ('zaif', 'CASH', 'BTC', 'ZIF BTC', 'zaif', 'btc_jpy', NULL, NULL);
