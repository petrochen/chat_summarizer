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
        logger.error("Необходимо указать BOT_TOKEN в .env файле")
        return
    if not CHANNEL_ID:
        logger.error("Необходимо указать CHANNEL_ID в .env файле")
        return

    try:
        create_tables()
    except Exception as e:
        logger.error(f"Не удалось создать таблицы базы данных: {e}")
        return

    try:
        bot = ChatSummarizerBot(BOT_TOKEN, CHANNEL_ID)
        logger.info("Chat Summarizer Bot (DB version) запущен")
        bot.run()
    except Exception as e:
        logger.exception(f"Критическая ошибка при запуске бота: {e}")

if __name__ == '__main__':
    main()
