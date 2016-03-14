#!/bin/sh

ENDPOINT=${1:-http://localhost:8887}

curl -s -XPOST -H "Content-type: application/json" -H "Authorization: Key demo-key" ${ENDPOINT}/alert/nimbus -d '
{
  "resource": "7ad21fa2-8c6d-4002-a29c-da4cfdee073f",
  "event": "HW:FAN:WEAR",
  "group": "Hardware",
  "severity": "major",
  "environment": "Power Plant",
  "service": [
      "Power Generation"
  ],
  "status" : "open",
  "text": "fan not working at optimal level",
  "value": "warning"
}'
echo

