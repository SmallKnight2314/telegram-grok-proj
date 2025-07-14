# Telegram Bot Setup Instructions

## Prerequisites
- Ubuntu server (e.g., Ubuntu 22.04)
- Docker and Docker Compose installed
- Telegram account and a bot created via BotFather
- SMTP server credentials (e.g., Gmail, SendGrid)

## Setup Steps

1. **Create a Telegram Bot**
   - Open Telegram and search for `@BotFather`.
   - Send `/start` and then `/newbot`.
   - Follow prompts to name your bot and get a bot token.
   - Save the token for the next steps.

2. **Prepare Environment Variables**
   - Create a `.env` file in the project directory with the following:
     ```
     TELEGRAM_TOKEN=your_bot_token_here
     SMTP_SERVER=smtp.gmail.com
     SMTP_PORT=587
     EMAIL_SENDER=your_email@gmail.com
     EMAIL_PASSWORD=your_email_password
     EMAIL_RECIPIENT=target_email@example.com
     ```
   - For Gmail, use an App Password if 2FA is enabled (generate at https://myaccount.google.com/security).

3. **Install Docker and Docker Compose**
   - Update package list:
     ```bash
     sudo apt update
     sudo apt install -y docker.io docker-compose
     ```
   - Start and enable Docker:
     ```bash
     sudo systemctl start docker
     sudo systemctl enable docker
     ```

4. **Set Up Project Directory**
   - Create a directory for your project:
     ```bash
     mkdir telegram-bot && cd telegram-bot
     ```
   - Save the provided `telegram_bot.py`, `Dockerfile`, `requirements.txt`, and `docker-compose.yml` files in this directory.

5. **Build and Run the Bot**
   - Build the Docker image:
     ```bash
     docker-compose build
     ```
   - Start the bot:
     ```bash
     docker-compose up -d
     ```

6. **Interact with the Bot**
   - Open Telegram, find your bot, and send `/start`.
   - Follow the prompts to provide your name, email, favorite color, and hobby.
   - The bot will send the form data to the specified email and confirm successful delivery.

7. **Stop the Bot**
   - To stop the bot:
     ```bash
     docker-compose down
     ```

## Notes
- Ensure your SMTP server allows connections from your Ubuntu server's IP.
- If using Gmail, enable "Less secure app access" or use an App Password.
- The bot stores user data temporarily in memory; it’s cleared after submission.
- For production, consider securing the `.env` file and using a more robust SMTP service like SendGrid.