#! /bin/bash

readarray -t PEERS <<< $(docker container ls | awk 'match($2, /peer[0-9]+/) {print substr($2, RSTART, RLENGTH)}'); declare -p PEERS
readarray -t ORGS <<< $(docker container ls | awk 'match($2, /org[0-9]+/) {print substr($2, RSTART, RLENGTH)}'); declare -p ORGS
# Stopping chaincode containers
docker container stop $(docker container ls | awk '($2 ~ /dev-peer[0-9]+/) {print $1}')
# Removing chaincode containers
docker container rm $(docker container ls | awk '($2 ~ /dev-peer[0-9]+/) {print $1}')
docker rmi $(docker images | awk '($1 ~ /dev-peer[0-9]+/) {print $1}')