import logging
from config import BOT_TOKEN, CHANNEL_ID, LOG_LEVEL
from telegram_bot import ChatSummarizerBot
from database import create_tables

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=LOG_LEVEL.upper()
)
logger = logging.getLogger(__name__)

def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
        logger.error("BOT_TOKEN must be specified in the .env file")
        return
    if not CHANNEL_ID:
        logger.error("CHANNEL_ID must be specified in the .env file")
        return

    try:
        create_tables()
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        return

    try:
        bot = ChatSummarizerBot(BOT_TOKEN, CHANNEL_ID)
        logger.info("Chat Summarizer Bot (DB version) started")
        bot.run()
    except Exception as e:
        logger.exception(f"Critical error starting the bot: {e}")

if __name__ == '__main__':
    main()
