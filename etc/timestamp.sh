#!/usr/bin/env bash

#
# psql -d cryptowelder -c "`sh timestamp.sh`"
#

printf "
WITH v_timestamp AS (
    SELECT date_trunc('minute', now() - UNNEST(
        ARRAY [
            INTERVAL '0 minute'"

for i in `seq 1 60`
do
  printf ",
            INTERVAL '$i minute'"
done

printf "
        ])) AS vt_time
)
INSERT INTO
  t_timestamp (
    ts_time
  )
  SELECT vt_time
  FROM
    v_timestamp
  WHERE NOT EXISTS(
      SELECT *
      FROM
        t_timestamp
      WHERE
        ts_time = vt_time
  );
"
