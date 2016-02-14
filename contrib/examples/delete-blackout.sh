#!/bin/sh


ENDPOINT=${1:-http://localhost:8080}

curl -s -XDELETE -H "Content-type: application/json" -H "Authorization: Key demo-key" ${ENDPOINT}/blackout/nimbus/1e794916-716e-4f35-89a7-1f115f601649
echo



