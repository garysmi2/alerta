#!/bin/sh

ENDPOINT=${1:-http://localhost:8080}

curl -s -XPOST -H "Content-type: application/json" -H "Authorization: Key demo-key" ${ENDPOINT}/heartbeat -d '
{
  "tenant" : "nimbus",
  "id": "testID",
  "origin" : "testOrigin",
  "tags" : ["tag1","tag2","tag2"],
  "type" : "Heartbeat",
  "timeout" : 10000

}'
echo

