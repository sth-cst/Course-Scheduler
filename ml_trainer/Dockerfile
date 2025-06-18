FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Make sure the entrypoint script is executable
RUN chmod +x entrypoint.sh

# Set environment variables
ENV PORT=10000
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# Expose the port
EXPOSE 10000

# Use gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "--workers", "1", "--threads", "8", "--timeout", "0", "api:app"]