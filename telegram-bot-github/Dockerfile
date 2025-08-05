# Use lightweight Python 3.11 base image
FROM python:3.11-slim

# Set working directory to /app
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files, including tmp/ directory for media storage
COPY . .

# Install dumb-init for proper signal handling
RUN apt-get update && apt-get install -y --no-install-recommends dumb-init && \
    rm -rf /var/lib/apt/lists/*

# Use dumb-init as entrypoint to handle signals (e.g., SIGTERM) gracefully
ENTRYPOINT ["dumb-init", "--"]

# Run the bot directly, leveraging dumb-init for signal handling
CMD ["python", "telegram_bot.py"]

# Wrap the Python command in a shell to trap SIGTERM
CMD ["sh", "-c", "trap 'echo \"Shutting down gracefully...\"; exit 0' SIGTERM; python telegram_bot.py"]
