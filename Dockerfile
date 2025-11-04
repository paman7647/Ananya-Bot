# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies (ffmpeg for audio processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire application code
COPY src/ ./src/
COPY launch_bot.py .
COPY start.sh .

# Create necessary directories
RUN mkdir -p logs backups

# Make scripts executable
RUN chmod +x start.sh launch_bot.py

# Create non-root user for security (optional for some platforms)
RUN useradd --create-home --shell /bin/bash botuser && \
    chown -R botuser:botuser /app
USER botuser

# Health check for web server
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Expose port (use PORT env var for cloud platforms)
EXPOSE ${PORT:-8080}

# Run web server (bot will be started by bot_control)
# Use PORT environment variable for cloud platform compatibility
CMD uvicorn src.web.app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
