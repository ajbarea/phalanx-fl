# Dockerfile for FL Execution Framework API
# Enables PyTorch 2.6.0 on Intel Macs via Linux container

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
# Use CPU-only requirements (no CUDA needed for Intel Mac development)
COPY requirements-docker.txt ./requirements.txt

# Install Python dependencies (torch 2.6.0 works on Linux!)
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY config/ ./config/
COPY datasets/ ./datasets/

# Expose API port
EXPOSE 8000

# Run the API server
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
