--
-- Create users. (Replace the passwords below !!!)
--
CREATE USER cryptowelder WITH PASSWORD 'SomePassword1';

CREATE USER grafana WITH PASSWORD 'SomePassword2';

--
-- Setup database.
--
CREATE DATABASE cryptowelder WITH OWNER = cryptowelder;

ALTER DATABASE cryptowelder SET TIMEZONE TO 'UTC';

SELECT pg_reload_conf();

--
-- Grant permissions. (Re-execute after creating tables and views.)
--
GRANT USAGE ON SCHEMA public TO grafana;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana;
