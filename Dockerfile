# Backend Dockerfile - Django REST Framework Application
# Multi-stage build for optimized production image

# Stage 1: Base Python image
FROM python:3.12-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: Dependencies
FROM base AS dependencies

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies including gunicorn for production
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn

# Stage 3: Production
FROM base AS production

# Copy installed packages from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Create a non-root user for security
RUN addgroup --gid 1001 --system appgroup \
    && adduser --uid 1001 --system --gid 1001 appuser

# Copy application code
COPY . .

# Create media directory and set permissions
RUN mkdir -p /app/media /app/staticfiles \
    && chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/')" || exit 1

# Default command - collect static files and run gunicorn
CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate --noinput && gunicorn spices_backend.wsgi:application --bind 0.0.0.0:8000 --workers 3 --threads 2"]
