#!/usr/bin/env bash

pushd "`dirname "$0"`" > /dev/null

  if [ ! -d logs ]; then
    mkdir logs
  fi

  nohup python cryptowelder.py > logs/cryptowelder-console.log 2>&1 &

popd > /dev/null
