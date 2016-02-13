#!/bin/sh


ENDPOINT=${1:-http://localhost:8080}

curl -s -XDELETE -H "Content-type: application/json" -H "Authorization: Key demo-key" ${ENDPOINT}/heartbeat/nimbus/7b0e19c6-b4c7-4579-b2fa-0b5829f47930
echo



