#!/bin/bash
# Rebuilds and explicitly tags isolated Multi-Architecture Runtimes for Sylk Edge Mesh
set -e

# Pre-pull base images to ensure immediate layer availability and caching
echo "--> Pre-pulling base images"
docker pull python:3.11-alpine || true
docker pull node:18-alpine || true

# Python Runtime Tags
echo "--> Building Python Runtime (x86 & ARM)"
docker buildx build --platform linux/amd64 -t sylk-python-runtime:x86 --load ./python-runtime
docker buildx build --platform linux/arm64 -t sylk-python-runtime:arm --load ./python-runtime

# Node.js Runtime Tags 
echo "--> Building Node.js Runtime (x86 & ARM)"
docker buildx build --platform linux/amd64 -t sylk-node-runtime:x86 --load ./node-runtime
docker buildx build --platform linux/arm64 -t sylk-node-runtime:arm --load ./node-runtime

echo "Multi-architecture runtime images are built and tagged properly!"
