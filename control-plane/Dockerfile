FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ app/
COPY frontend/ frontend/
# Initialize dummy analytics DB if not exists
RUN touch sylk_analytics.db

EXPOSE 8000

# Run FastAPI via uvicorn with multi-worker if desired
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
