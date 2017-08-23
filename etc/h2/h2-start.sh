#!/bin/bash

pushd "`dirname "$0"`" > /dev/null || exit $?

if [ ! -d "data" ]; then
  mkdir "data" || exit $?
fi

if [ ! -d "logs" ]; then
  mkdir "logs" || exit $?
fi

if [ "`ps -ef | grep java | grep cryptowelder`" == "" ]; then

  nohup \
    java \
    -server \
    -Xms256m \
    -Xmx256m \
    -XX:+UseParallelGC \
    -XX:+UseParallelOldGC \
    -Xloggc:logs/h2-gc.log \
    -XX:+PrintGCDetails \
    -XX:+PrintGCDateStamps \
    -XX:+UseGCLogFileRotation \
    -XX:NumberOfGCLogFiles=9 \
    -XX:GCLogFileSize=10M \
    -XX:HeapDumpPath=logs/h2-heap_`date +%Y%m%d_%H%M%S`.log \
    -XX:+HeapDumpOnOutOfMemoryError \
    -jar \
    "`find . -name "h2-*.jar"`" \
    -baseDir "`pwd`/data" \
    -tcp \
    -tcpPort "49092" \
    -tcpPassword "cryptowelder" \
    -ifExists \
   > logs/h2-console.log 2>&1 & > logs/h2-nohup.log 2>&1

  sleep 1

  cat logs/h2-console.log

else

  echo "Server already started."

fi

popd > /dev/null 2>&1
