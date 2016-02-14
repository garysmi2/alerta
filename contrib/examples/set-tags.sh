#!/bin/sh



ENDPOINT=${1:-http://localhost:8080}

curl -s -XPOST -H "Content-type: application/json" -H "Authorization: Key demo-key" ${ENDPOINT}/alert/nimbus/3d32cfeb-cca9-4c2f-ab10-f02e899efd20/tag -d '
{
  "status": "closed",
  "tags" : ["blah1","blah2"]
}'
echo



