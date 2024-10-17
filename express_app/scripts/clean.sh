#!/bin/bash

function removeChains() {
    echo
    echo "##########################################################"
    echo "################### Removing All Chains #####################"
    echo "##########################################################"
    rm -rf ../blockchain_base/chains/bc_*
}

# Destroy Blockchain and containers
function clean() {
    removeChains
    clearContainers
    docker network rm $(docker network ls -qf name=net) # net is defined in every .env file as project name for simplicity
    removeUnwantedImages
    echo 
}

function removeUnwantedImages() {
      #DOCKER_IMAGE_IDS=$(docker images | awk '($1 ~ /dev-peer.*-$"CONTRACT"-.*/) {print $3}')
  DOCKER_IMAGE_IDS=$(docker images | awk -v pat=dev-peer.*-$CONTRACT-.* '($1 ~ pat) {print $3}')
  if [ -z "$DOCKER_IMAGE_IDS" -o "$DOCKER_IMAGE_IDS" == " " ]; then
    echo "---- No images available for deletion ----"
  else
    docker rmi -f $DOCKER_IMAGE_IDS
  fi
}

function clearContainers() {
    docker container rm -f $(docker container ls -aq) && docker volume rm $(docker volume ls -q)
    docker volume rm $(docker volume ls -qf dangling=true)
    CONTAINER_IDS=$(docker ps -a | awk -v pat=dev-peer.*.$CONTRACT..* '($2 ~ /dev-peer.*."$CONTRACT".*/) {print $1}')
    echo $CONTAINER_IDS
    if [ -z "$CONTAINER_IDS" -o "$CONTAINER_IDS" == " " ]; then
        echo "---- No containers available for deletion ----"
    else
        docker rm -f $CONTAINER_IDS
    fi
}

CONTRACT='.*'
while getopts "c:" opt; do
  case "$opt" in
  c)
    CONTRACT=$OPTARG
    ;;
  esac
done
clean