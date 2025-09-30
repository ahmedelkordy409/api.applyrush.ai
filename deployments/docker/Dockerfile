# JobHire.AI Enterprise Backend - Production Dockerfile

# Use Python 3.11 slim as base image for smaller size and security
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r jobhire && useradd -r -g jobhire jobhire

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements-enterprise.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-enterprise.txt

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/

# Create necessary directories
RUN mkdir -p /app/logs /app/data && \
    chown -R jobhire:jobhire /app

# Switch to non-root user
USER jobhire

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Default command
CMD ["python", "-m", "src.jobhire.main"]


# Development stage
FROM base as development

USER root

# Install development dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-cov \
    black \
    isort \
    mypy \
    pre-commit

# Install debugging tools
RUN apt-get update && apt-get install -y \
    vim \
    htop \
    && rm -rf /var/lib/apt/lists/*

USER jobhire

# Override command for development
CMD ["python", "-m", "src.jobhire.main", "--reload"]


# Production stage
FROM base as production

# Copy only necessary files for production
COPY --from=base /app /app

# Set production environment
ENV APP_ENVIRONMENT=production

# Use gunicorn for production
CMD ["gunicorn", "src.jobhire.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--preload", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]