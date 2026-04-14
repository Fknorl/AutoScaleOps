# ═══════════════════════════════════════════════════════════════════════════
# AI Predictor Dockerfile - AutoScaleOps
# ═══════════════════════════════════════════════════════════════════════════
#
# Purpose: Containerize AI prediction engine with Auto-ARIMA
# Base Image: Python 3.11 slim
#

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for numerical libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy predictor code
COPY predictor.py .

# Create non-root user for security
RUN useradd -m -u 1000 aiuser && chown -R aiuser:aiuser /app
USER aiuser

# Environment variables (can be overridden)
ENV PROMETHEUS_URL=http://127.0.0.1:9090
ENV PUSHGATEWAY_URL=http://127.0.0.1:9091
ENV POD_CAPACITY_THRESHOLD=100
ENV SAFETY_BUFFER_PODS=2
ENV FALSE_ALARM_TIMEOUT=300
ENV FORECAST_HORIZON=5
ENV CI_LEVEL=0.95
ENV SOURCE_METRIC=http_requests_total
ENV PREDICTION_METRIC=predicted_rps_30min

# Run predictor
CMD ["python", "-u", "predictor.py"]
