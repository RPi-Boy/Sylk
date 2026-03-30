#!/bin/bash
# Rebuilds and explicit tags isolated Runtimes for Sylk Edge Mesh
set -e

# Pre-pull base images to ensure immediate layer availability and caching
echo "--> Pre-pulling base images"
docker pull python:3.11-alpine || true
docker pull node:18-alpine || true

# Python Runtime Tags
echo "--> Building Python Runtime (x86)"
docker build -t sylk-python-runtime:x86 ./python-runtime

# Node.js Runtime Tags 
echo "--> Building Node.js Runtime (x86)"
docker build -t sylk-node-runtime:x86 ./node-runtime

echo "Runtime images are built and tagged properly!"
