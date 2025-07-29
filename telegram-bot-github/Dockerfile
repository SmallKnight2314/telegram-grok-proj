FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config/ ./config/
COPY src/ ./src/
COPY telegram_bot.py .


# Install a lightweight init system (recommended for Python apps)
RUN apt-get update && apt-get install -y --no-install-recommends dumb-init && \
    rm -rf /var/lib/apt/lists/*

# Use dumb-init as entrypoint to properly handle signals
ENTRYPOINT ["dumb-init", "--"]

# Wrap the Python command in a shell to trap SIGTERM
CMD ["sh", "-c", "trap 'echo \"Shutting down gracefully...\"; exit 0' SIGTERM; python telegram_bot.py"]
