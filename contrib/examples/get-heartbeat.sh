#!/bin/sh

ENDPOINT=${1:-http://localhost:8080}

curl -s -XGET -H "Content-type: application/json" -H "Authorization: Key demo-key" ${ENDPOINT}/heartbeat/nimbus/53d9550a-b5b2-4990-b9a8-c9c0fc5acf6d 
echo

