#!/bin/sh

ENDPOINT=${1:-http://localhost:8080}

curl -s -XGET -H "Content-type: application/json" -H "Authorization: Key demo-key" ${ENDPOINT}/blackouts/nimbus 
echo

