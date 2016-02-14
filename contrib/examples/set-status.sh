#!/bin/sh

#3f724eb9-ad0c-4eae-9f93-6477e83311b6


ENDPOINT=${1:-http://localhost:8080}

curl -s -XPOST -H "Content-type: application/json" -H "Authorization: Key demo-key" ${ENDPOINT}/alert/nimbus/3d32cfeb-cca9-4c2f-ab10-f02e899efd20/status -d '
{
  "status": "banana"
}'
echo



