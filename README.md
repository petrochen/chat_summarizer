# Chat Summarizer Bot

A Telegram bot for collecting messages from chats and generating brief summaries of discussions using YandexGPT.

## Functionality

- Saving all messages from Telegram chats to a SQLite database
- Tracking connections between messages and topics
- Restoring topic structure when the bot is added to an existing chat
- Generating brief summaries of discussions using YandexGPT (in development)
- Support for various media types and reactions

## Technologies

- Python 3.9+
- python-telegram-bot v22.0
- SQLAlchemy
- YandexGPT API
- SQLite

## Installation and Launch

1. Clone the repository:
```bash
git clone https://github.com/your_username/chat_summarizer.git
cd chat_summarizer
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

3. Create a `.env` file based on `.env.example` and fill in the required variables:
```bash
cp .env.example .env
# Fill in BOT_TOKEN and other environment variables
```

4. Start the bot:
```bash
python main.py
```

## Project Structure

- `main.py` - entry point of the program
- `telegram_bot.py` - main bot class and message handlers
- `models.py` - SQLAlchemy data models
- `database.py` - database connection setup
- `crud.py` - functions for working with the database
- `yandex_gpt_summarizer.py` - summary generation using YandexGPT
- `config.py` - loading configuration from `.env`
- `command_handlers.py` - bot command handlers 