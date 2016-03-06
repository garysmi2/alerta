#!/bin/sh

ENDPOINT=${1:-http://localhost:8887}

curl -s -XPOST -H "Content-type: application/json" -H "Authorization: Key demo-key" ${ENDPOINT}/alert/nimbus -d '
{
  "resource": "aac0d57e-4c16-4fd5-bb9b-61aed803a703",
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

