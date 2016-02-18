#!/bin/sh

#3f724eb9-ad0c-4eae-9f93-6477e83311b6


ENDPOINT="http://localhost:8887"
id=$1
target="${ENDPOINT}/alert/nimbus/"$1
curl -s -XDELETE -H "Content-type: application/json" -H "Authorization: Key demo-key" ${target}    
echo



