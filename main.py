import logging
from config import BOT_TOKEN, CHANNEL_ID, LOG_LEVEL
from telegram_bot import ChatDataCollectorBot

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=LOG_LEVEL.upper()
)
logger = logging.getLogger(__name__)

def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
        logger.error("Необходимо указать BOT_TOKEN в .env файле")
        return
    if not CHANNEL_ID:
        logger.error("Необходимо указать CHANNEL_ID в .env файле")
        return

    bot = ChatDataCollectorBot(BOT_TOKEN, CHANNEL_ID)
    logger.info("Chat Data Collector Bot запущен")
    bot.run()

if __name__ == '__main__':
    main()
