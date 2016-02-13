#!/bin/sh


ENDPOINT=${1:-http://localhost:8080}

curl -s -XDELETE -H "Content-type: application/json" -H "Authorization: Key demo-key" ${ENDPOINT}/blackout/nimbus/973a75c3-650b-44b5-9888-2c5b2063f0ca
echo



