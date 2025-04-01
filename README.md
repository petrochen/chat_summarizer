# Chat Summarizer Bot

Telegram-бот для сбора сообщений из чатов и генерации краткого резюме обсуждений с помощью YandexGPT.

## Функциональность

- Сохранение всех сообщений из Telegram чатов в базу данных SQLite
- Отслеживание связей между сообщениями и топиками
- Восстановление структуры топиков при добавлении бота в существующий чат
- Генерация краткого резюме дискуссий с использованием YandexGPT (в разработке)
- Поддержка различных типов медиа и реакций

## Технологии

- Python 3.9+
- python-telegram-bot v22.0
- SQLAlchemy
- YandexGPT API
- SQLite

## Установка и запуск

1. Клонировать репозиторий:
```bash
git clone https://github.com/ваш_пользователь/chat_summarizer.git
cd chat_summarizer
```

2. Создать виртуальное окружение и установить зависимости:
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

3. Создать файл `.env` на основе `.env.example` и заполнить необходимые переменные:
```bash
cp .env.example .env
# Заполните BOT_TOKEN и другие переменные окружения
```

4. Запустить бота:
```bash
python main.py
```

## Структура проекта

- `main.py` - входная точка программы
- `telegram_bot.py` - основной класс бота и обработчики сообщений
- `models.py` - модели данных SQLAlchemy
- `database.py` - настройка соединения с базой данных
- `crud.py` - функции для работы с базой данных
- `yandex_gpt_summarizer.py` - генерация резюме с помощью YandexGPT
- `config.py` - загрузка конфигурации из `.env`
- `command_handlers.py` - обработчики команд бота 