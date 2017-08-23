#!/bin/bash

pushd "`dirname "$0"`" > /dev/null || exit $?

java -jar "`find . -name "h2-*.jar"`" -tcpShutdown "tcp://localhost:49092" -tcpPassword "cryptowelder"

sleep 1

ps -ef | grep java | grep "cryptowelder"

popd > /dev/null 2>&1
