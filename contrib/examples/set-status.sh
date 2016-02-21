#!/bin/sh

#3f724eb9-ad0c-4eae-9f93-6477e83311b6


ENDPOINT=${1:-http://localhost:8887}

curl -s -XPOST -H "Content-type: application/json" -H "Authorization: Key demo-key" ${ENDPOINT}/alert/nimbus/70969e9e-fd22-45e2-8877-be4044a5f70f/status -d '
{
  "status": "ack",
  "text": "status updated to ack by garysmi"
}'
echo



