#!/usr/bin/env python3
import logging
import os
import time
import argparse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from config import DATABASE_URI, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_PATH
from database import Base, engine

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def wait_for_db(max_attempts=10, delay=5):
    """Ожидание доступности базы данных"""
    logger.info(f"Ожидание доступности базы данных на {DB_HOST}:{DB_PORT}...")
    
    # Создаем URI для подключения к postgres (без указания конкретной базы)
    postgres_uri = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"
    
    engine = create_engine(postgres_uri)
    
    for attempt in range(max_attempts):
        try:
            # Проверяем соединение
            with engine.connect() as conn:
                logger.info("Соединение с базой данных установлено")
                return True
        except OperationalError as e:
            logger.warning(f"Попытка {attempt+1}/{max_attempts}: База данных недоступна. {str(e)}")
            if attempt < max_attempts - 1:
                logger.info(f"Повторная попытка через {delay} секунд...")
                time.sleep(delay)
    
    logger.error(f"База данных недоступна после {max_attempts} попыток")
    return False

def create_database():
    """Создает базу данных SQLite"""
    try:
        # Создаем директорию для базы данных, если она не существует
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        print(f"База данных будет создана по пути: {DB_PATH}")
    except Exception as e:
        print(f"Ошибка при создании директории для базы данных: {e}")
        sys.exit(1)

def create_tables():
    """Создает таблицы в базе данных"""
    try:
        Base.metadata.create_all(engine)
        print("Таблицы успешно созданы")
    except Exception as e:
        print(f"Ошибка при создании таблиц: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Инициализация базы данных")
    parser.add_argument("--force", action="store_true", help="Принудительное пересоздание базы данных")
    args = parser.parse_args()

    if args.force and os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print(f"Существующая база данных {DB_PATH} удалена")
        except Exception as e:
            print(f"Ошибка при удалении существующей базы данных: {e}")
            sys.exit(1)

    create_database()
    create_tables()

if __name__ == "__main__":
    main()