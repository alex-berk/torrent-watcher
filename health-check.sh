#! /bin/bash

LOG_FOLDER=logs
LOG_HEALTH_FLAG="search_torrent ran"
TIME_THRESHOLD=$(date --date "8 hours ago" +'%s')

LOG_FILE="$LOG_FOLDER/$(ls -t "$LOG_FOLDER" | head -n 1)"
FRESHEST_LOG=$(tac $LOG_FILE | grep -m1 "$LOG_HEALTH_FLAG" | cut -d "|" -f 1)
FRESHEST_LOG_DATE=$(date -d "$FRESHEST_LOG" +"%s")

if [ -z "$FRESHEST_LOG" ];
then
        echo "healthcheck: couldn't fetch log timestamp"
        exit 1
fi

if [ "$TIME_THRESHOLD" -gt "$FRESHEST_LOG_DATE" ];
then
        echo "healthcheck: freshest timestamp is too old"
        exit 1
fi
