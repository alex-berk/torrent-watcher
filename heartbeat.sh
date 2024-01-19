#! /bin/bash

source ./health-check.sh
if [ $? -eq 0 ]; then
   curl "https://uptime.betterstack.com/api/v1/heartbeat/$HEARTBEAT_KEY"  
fi