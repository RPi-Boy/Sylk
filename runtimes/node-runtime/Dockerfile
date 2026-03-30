FROM node:18-alpine

WORKDIR /app

# Install explicit dependency (no external package.json needed for this single module script)
# However, caching npm execution is still good practice.
RUN npm install --no-cache express

# Security: Add node user if not exists, or use the built-in 'node' user inside Alpine for node images.
# node:alpine already has a user named 'node'.
USER node

# Copy execution wrapper script over
COPY --chown=node:node server.js .

EXPOSE 5000
CMD ["node", "server.js"]
