--
-- Products
--
TRUNCATE TABLE t_product;

INSERT INTO t_product (pr_site, pr_code, pr_inst, pr_fund, pr_disp, pr_expr)
VALUES ('binance', 'BTCUSDT', 'BTC', 'USD', 'BNC BTC', NULL),
       ('bitbank', 'btc_jpy', 'BTC', 'JPY', 'BBK BTC', NULL),
       ('bitfinex', 'btcusd', 'BTC', 'USD', 'BFN BTC', NULL),
       ('bitflyer', 'BTC_JPY', 'BTC', 'JPY', 'BFL BTC', NULL),
       ('bitflyer', 'ETH_BTC', 'ETH', 'BTC', 'BFL ETH', NULL),
       ('bitflyer', 'BCH_BTC', 'BCH', 'BTC', 'BFL BCH', NULL),
       ('bitflyer', 'FX_BTC_JPY', 'BFX', 'JPY', 'BFL BFX', NULL),
       ('bitmex', 'XBTUSD', 'BTC', 'USD', 'BMX XBT', NULL),
       ('bitpoint', 'BTC_JPY', 'BTC', 'JPY', 'BPT BTC', NULL),
       ('btcbox', 'btc', 'BTC', 'JPY', 'BOX BTC', NULL),
       ('coincheck', 'btc_jpy', 'BTC', 'JPY', 'CCK BTC', NULL),
       ('fisco', 'btc_jpy', 'BTC', 'JPY', 'FSC BTC', NULL),
       ('oanda', 'USD_JPY', 'USD', 'JPY', 'OND USD', NULL),
       ('polonex', 'USDT_BTC', 'BTC', 'USD', 'PLX BTC', NULL),
       ('quoinex', 'BTCJPY', 'BTC', 'JPY', 'QNX BTC', NULL),
       ('zaif', 'btc_jpy', 'BTC', 'JPY', 'ZIF BTC', NULL);

--
-- Evaluation
--
TRUNCATE TABLE t_evaluation;

INSERT INTO t_evaluation (ev_site, ev_unit, ev_ticker_site, ev_ticker_code, ev_convert_site, ev_convert_code)
VALUES ('binance', 'USD', 'oanda', 'USD_JPY', NULL, NULL),
       ('binance', 'BTC', 'bitflyer', 'BTC_JPY', NULL, NULL),
       ('bitbank', 'JPY', NULL, NULL, NULL, NULL),
       ('bitbank', 'BTC', 'bitbank', 'btc_jpy', NULL, NULL),
       ('bitfinex', 'USD', 'oanda', 'USD_JPY', NULL, NULL),
       ('bitfinex', 'BTC', 'bitflyer', 'BTC_JPY', NULL, NULL),
       ('bitflyer', 'JPY', NULL, NULL, NULL, NULL),
       ('bitflyer', 'BTC', 'bitflyer', 'BTC_JPY', NULL, NULL),
       ('bitflyer', 'BFX', 'bitflyer', 'FX_BTC_JPY', NULL, NULL),
       ('bitflyer', 'ETH', 'bitflyer', 'ETH_BTC', 'bitflyer', 'BTC_JPY'),
       ('bitflyer', 'BCH', 'bitflyer', 'BCH_BTC', 'bitflyer', 'BTC_JPY'),
       ('bitmex', 'USD', 'oanda', 'USD_JPY', NULL, NULL),
       ('bitmex', 'BTC', 'bitflyer', 'BTC_JPY', NULL, NULL),
       ('bitpoint', 'JPY', NULL, NULL, NULL, NULL),
       ('bitpoint', 'BTC', 'bitpoint', 'BTC_JPY', NULL, NULL),
       ('btcbox', 'JPY', NULL, NULL, NULL, NULL),
       ('btcbox', 'BTC', 'btcbox', 'btc', NULL, NULL),
       ('coincheck', 'JPY', NULL, NULL, NULL, NULL),
       ('coincheck', 'BTC', 'coincheck', 'btc_jpy', NULL, NULL),
       ('fisco', 'JPY', NULL, NULL, NULL, NULL),
       ('fisco', 'BTC', 'fisco', 'btc_jpy', NULL, NULL),
       ('oanda', 'JPY', NULL, NULL, NULL, NULL),
       ('oanda', 'USD', 'oanda', 'USD_JPY', NULL, NULL),
       ('poloniex', 'USD', 'oanda', 'USD_JPY', NULL, NULL),
       ('poloniex', 'BTC', 'bitflyer', 'BTC_JPY', NULL, NULL),
       ('quoinex', 'JPY', NULL, NULL, NULL, NULL),
       ('quoinex', 'BTC', 'quoinex', 'BTCJPY', NULL, NULL),
       ('zaif', 'JPY', NULL, NULL, NULL, NULL),
       ('zaif', 'BTC', 'zaif', 'btc_jpy', NULL, NULL);

--
-- Accounts
--
TRUNCATE TABLE t_account;

INSERT INTO t_account (ac_site, ac_acct, ac_unit, ac_disp)
VALUES ('binance', 'CASH', 'USD', 'BNC USD'),
       ('binance', 'CASH', 'BTC', 'BNC BTC'),
       ('bitbank', 'FUND', 'JPY', 'BBK JPYF'),
       ('bitbank', 'CASH', 'JPY', 'BBK JPY'),
       ('bitbank', 'CASH', 'BTC', 'BBK BTC'),
       ('bitfinex', 'CASH', 'USD', 'BFN USD'),
       ('bitfinex', 'CASH', 'BTC', 'BFN BTC'),
       ('bitflyer', 'FUND', 'JPY', 'BFL JPYF'),
       ('bitflyer', 'CASH', 'JPY', 'BFL JPY'),
       ('bitflyer', 'CASH', 'BTC', 'BFL BTC'),
       ('bitflyer', 'MARGIN', 'JPY', 'BFL JPYC'),
       ('bitflyer', 'MARGIN', 'BTC', 'BFL BTCC'),
       ('bitflyer', 'CASH', 'ETH', 'BFL ETH'),
       ('bitflyer', 'CASH', 'BCH', 'BFL BCH'),
       ('bitmex', 'MARGIN', 'USD', 'BMX USD'),
       ('bitmex', 'MARGIN', 'BTC', 'BMX XBT'),
       ('bitpoint', 'FUND', 'JPY', 'BPT JPYF'),
       ('bitpoint', 'CASH', 'JPY', 'BPT JPY'),
       ('bitpoint', 'CASH', 'BTC', 'BPT BTC'),
       ('btcbox', 'FUND', 'JPY', 'BOX JPYF'),
       ('btcbox', 'CASH', 'JPY', 'BOX JPY'),
       ('btcbox', 'CASH', 'BTC', 'BOX BTC'),
       ('coincheck', 'FUND', 'JPY', 'CCK JPYF'),
       ('coincheck', 'CASH', 'JPY', 'CCK JPY'),
       ('coincheck', 'CASH', 'BTC', 'CCK BTC'),
       ('fisco', 'FUND', 'JPY', 'FSC JPYF'),
       ('fisco', 'CASH', 'JPY', 'FSC JPY'),
       ('fisco', 'CASH', 'BTC', 'FSC BTC'),
       ('poloniex', 'CASH', 'USD', 'PLX USD'),
       ('poloniex', 'CASH', 'BTC', 'PLX BTC'),
       ('oanda', 'FUND', 'JPY', 'OND JPYF'),
       ('oanda', 'MARGIN', 'JPY', 'OND JPY'),
       ('oanda', 'MARGIN', 'USD', 'OND USD'),
       ('quoinex', 'FUND', 'JPY', 'QNX JPYF'),
       ('quoinex', 'CASH', 'JPY', 'QNX JPY'),
       ('quoinex', 'CASH', 'BTC', 'QNX BTC'),
       ('zaif', 'FUND', 'JPY', 'ZIF JPYF'),
       ('zaif', 'CASH', 'JPY', 'ZIF JPY'),
       ('zaif', 'CASH', 'BTC', 'ZIF BTC');
