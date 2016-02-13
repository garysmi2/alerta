#!/bin/sh

#3f724eb9-ad0c-4eae-9f93-6477e83311b6


ENDPOINT=${1:-http://localhost:8080}

curl -s -XDELETE -H "Content-type: application/json" -H "Authorization: Key demo-key" ${ENDPOINT}/alert/nimbus/3f724eb9-ad0c-4eae-9f93-6477e83311b6
echo



