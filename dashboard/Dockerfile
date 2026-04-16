# ═══════════════════════════════════════════════════════════════════════════
# Dashboard Dockerfile - AutoScaleOps
# ═══════════════════════════════════════════════════════════════════════════
#
# Purpose: Containerize Streamlit dashboard with professional UI
# Base Image: Python 3.11 slim
#

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy dashboard code
COPY dashboard.py .

# Create directory for state persistence
RUN mkdir -p /app/.dashboard_state

# Create non-root user for security
RUN useradd -m -u 1000 dashuser && chown -R dashuser:dashuser /app
USER dashuser

# Expose Streamlit port
EXPOSE 8501

# Environment variables
ENV PROMETHEUS_HOST=127.0.0.1
ENV PROMETHEUS_PORT=9090
ENV PUSHGATEWAY_HOST=127.0.0.1
ENV PUSHGATEWAY_PORT=9091
ENV APP_HOST=127.0.0.1
ENV APP_PORT=8080

# Run Streamlit
CMD ["streamlit", "run", "dashboard.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
