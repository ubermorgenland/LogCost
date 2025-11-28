# LogCost Sidecar - Lightweight monitoring image for Kubernetes deployments
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install only runtime dependencies (no dev tools)
COPY pyproject.toml README.md ./
COPY logcost ./logcost

# Install in production mode
RUN pip install --no-cache-dir -e . && \
    rm -rf /root/.cache/pip

# Copy sidecar script
COPY sidecar.py ./

# Create directories for stats and history
RUN mkdir -p /var/log/logcost/history

# Run as non-root user for security
RUN useradd -m -u 1000 logcost && \
    chown -R logcost:logcost /app /var/log/logcost

USER logcost

# Health check
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('/var/log/logcost/stats.json') or os.path.exists('/var/log/logcost/history') else 1)"

# Default command runs sidecar
CMD ["python", "sidecar.py"]
