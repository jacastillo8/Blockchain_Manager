#!/bin/bash

function mongoUp() {
    cd mongo/
    docker-compose -f docker-compose-mongo.yaml up -d
    cd ..
}

function mongoDown() {
    cd mongo/
    docker-compose -f docker-compose-mongo.yaml down
    cd ..
}

if [ "$1" = "-m" ]; then 
  shift
fi
MODE=$1
shift

if [ "${MODE}" == "up" ]; then
    mongoUp
elif [ "${MODE}" == "down" ]; then
    mongoDown
else
    exit 1
fi