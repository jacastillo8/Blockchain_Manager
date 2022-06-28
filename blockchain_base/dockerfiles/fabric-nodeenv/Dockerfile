# Copyright IBM Corp. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
ARG NODE_VER=8.11
FROM node:${NODE_VER}-alpine
RUN apk add --no-cache \
	make \
	python \
	g++;
RUN mkdir -p /chaincode/input \
	&& mkdir -p /chaincode/output \
	&& mkdir -p /usr/local/src;
ADD build.sh start.sh /chaincode/
RUN cd /chaincode/output && npm install fabric-shim@~1.4.0
RUN npm rebuild --unsafe-perm
