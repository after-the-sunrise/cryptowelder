#!/usr/bin/env bash

#
# psql -d cryptowelder -c "`sh timestamp.sh`"
#

PREFIX="
WITH v_timestamp AS (
    SELECT date_trunc('minute', now() - UNNEST(
        ARRAY [
            INTERVAL '0 minute'"

CONTENT=""

for i in `seq 60`
do
  CONTENT="${CONTENT},
            INTERVAL '$i minute'"
done

SUFFIX="
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
  );"

echo -n "${PREFIX}${CONTENT}${SUFFIX}"
