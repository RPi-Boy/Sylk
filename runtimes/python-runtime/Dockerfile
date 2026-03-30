FROM python:3.11-alpine

WORKDIR /app
# Install any minimal deps first to leverage caching
RUN pip install --no-cache-dir flask

# Create a non-root user for security
RUN adduser -D sylkuser
USER sylkuser

COPY server.py .

EXPOSE 5000
CMD ["python", "server.py"]
