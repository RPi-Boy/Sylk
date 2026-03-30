#!/bin/bash
# Multi-arch build script snippet
docker buildx build --platform linux/amd64,linux/arm64 -t sylk-runtime:python ./python-runtime --push
docker buildx build --platform linux/amd64,linux/arm64 -t sylk-runtime:node ./node-runtime --push
