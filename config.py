import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Токен бота, полученный от @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

# ID канала, куда будут публиковаться саммари
# Формат: @channel_name или числовой ID
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_summary_channel")

# Время, когда будет создаваться ежедневный саммари (в формате UTC)
SUMMARY_TIME = os.getenv("SUMMARY_TIME", "18:00")

# Минимальное количество сообщений для создания саммари
MIN_MESSAGES = int(os.getenv("MIN_MESSAGES", "5"))

# API-ключ Yandex GPT
YANDEX_GPT_API_KEY = os.getenv("YANDEX_GPT_API_KEY", "YOUR_YANDEX_GPT_API_KEY")

# URL API Yandex GPT
YANDEX_GPT_API_URL = os.getenv("YANDEX_GPT_API_URL", "https://llm.api.cloud.yandex.net/llm/v1/completion")

# Модель Yandex GPT
YANDEX_GPT_MODEL = os.getenv("YANDEX_GPT_MODEL", "yandexgpt-lite")

# Настройки повторных попыток
RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))

# Параметры логирования
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
