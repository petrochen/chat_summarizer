import logging
from config import BOT_TOKEN, CHANNEL_ID
from telegram_bot import ChatSummarizerBot

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    # Инициализируем бота
    bot = ChatSummarizerBot(BOT_TOKEN, CHANNEL_ID)
    
    # Запускаем бота
    logger.info("Chat Summarizer Bot запущен")
    bot.run()

if __name__ == "__main__":
    main()
