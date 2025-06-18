FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Set environment variables
ENV PORT=5000
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# Use shell form of CMD to interpolate the PORT variable
CMD gunicorn --bind "0.0.0.0:${PORT}" --workers 1 --threads 8 --timeout 0 api:app