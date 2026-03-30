FROM python:3.11-alpine

WORKDIR /app
COPY server.py .

# Install any minimal deps
RUN pip install flask

EXPOSE 5000
CMD ["python", "server.py"]
