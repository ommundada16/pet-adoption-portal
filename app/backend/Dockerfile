FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so Docker can cache this layer when only code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py db.py ./

# Run as a normal user instead of root (safer if the app is ever compromised)
RUN useradd --system --uid 10001 appuser && mkdir -p /app/uploads && chown -R appuser /app
USER appuser

EXPOSE 5000

# gunicorn is a production web server (Flask's built-in one is for development only).
# One worker with several threads keeps the Prometheus counters in a single process.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "app:app"]
