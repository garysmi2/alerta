#!/bin/sh

ENDPOINT=${1:-http://localhost:8887}

curl -s -XPOST -H "Content-type: application/json" -H "Authorization: Key demo-key" ${ENDPOINT}/alert/nimbus -d '
{
  "resource": "Turbo Fan",
  "event": "HW:FAN:WEAR",
  "group": "Hardware",
  "severity": "disaster",
  "environment": "Power Plant",
  "service": [
      "Power Generation"
  ],
  "text": "fan not working at optimal level",
  "value": "warning"
}'
echo

