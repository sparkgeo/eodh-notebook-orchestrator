# Build stage
FROM python:3.13-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache \
    expat \
    gdal \
    gdal-dev \
    gcc \
    g++ \
    musl-dev \
    python3-dev \
    linux-headers \
    && rm -rf /var/cache/apk/*

COPY ./requirements.txt /app

# Install Python packages (this will compile rasterio and other packages)
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.13-alpine AS runtime

WORKDIR /app

# Install only runtime dependencies (no build tools)
RUN apk add --no-cache \
    expat \
    gdal \
    && rm -rf /var/cache/apk/*

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY ./*.py /app
COPY ./create_qlr/ /app/create_qlr/

# Expose port
EXPOSE 8000

# Set environment variables
ENV LOG_LEVEL=INFO
ENV LOG_REQUESTS=true
ENV LOG_REQUEST_BODY=false

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

