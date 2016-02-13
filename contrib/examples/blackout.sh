#!/bin/sh

ENDPOINT=${1:-http://localhost:8080}

curl -s -XPOST -H "Content-type: application/json" -H "Authorization: Key demo-key" ${ENDPOINT}/blackout -d '
{
  "tenant" : "nimbus",
  "resource": "host678:eth0",
  "event": "HW:NIC:FAILED",
  "group": "Hardware",
  "severity": "major",
  "environment": "Production",
  "service": [
      "Network"
  ],
  "text": "Network interface eth0 is down.",
  "value": "error"
}'
echo

