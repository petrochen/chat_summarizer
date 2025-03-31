#!/usr/bin/env python3
import logging
import os
import argparse
from database import create_tables, engine # Импортируем функцию создания таблиц
from config import DB_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main(force=False):
    """Инициализация базы данных: создание файла и таблиц."""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir)
            logger.info(f"Создана директория для БД: {db_dir}")
        except OSError as e:
            logger.error(f"Не удалось создать директорию {db_dir}: {e}")
            return False

    if force and os.path.exists(DB_PATH):
        try:
            logger.warning(f"Удаление существующей базы данных: {DB_PATH}")
            os.remove(DB_PATH)
            logger.info(f"Существующая база данных удалена.")
        except Exception as e:
            logger.error(f"Ошибка при удалении существующей базы данных: {e}")
            return False
    
    # Проверяем соединение перед созданием таблиц
    try:
        connection = engine.connect()
        connection.close()
        logger.info("Соединение с движком БД успешно.")
    except Exception as e:
         logger.error(f"Не удалось подключиться к движку БД: {e}")
         return False
         
    # Создаем таблицы
    try:
        create_tables() # Вызываем функцию создания таблиц из database.py
        return True
    except Exception as e:
        # Ошибка уже логируется в create_tables
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Инициализация базы данных SQLite.")
    parser.add_argument(
        "--force", 
        action="store_true", 
        help="Принудительно удалить и пересоздать файл базы данных перед созданием таблиц."
    )
    args = parser.parse_args()

    logger.info("Запуск инициализации базы данных...")
    if main(args.force):
        logger.info("Инициализация базы данных успешно завершена.")
    else:
        logger.error("Ошибка во время инициализации базы данных.")
        exit(1) 