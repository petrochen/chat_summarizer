import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from config import DATABASE_URI

logger = logging.getLogger(__name__)

# Создаем движок SQLAlchemy
try:
    engine = create_engine(DATABASE_URI, echo=False) # echo=True для отладки SQL-запросов
except Exception as e:
    logger.error(f"Ошибка при создании движка SQLAlchemy: {e}")
    raise

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Создаем базовый класс для моделей
Base = declarative_base()

def get_db():
    """Зависимость для получения сессии базы данных."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Создает все таблицы в базе данных."""
    try:
        logger.info("Создание таблиц базы данных...")
        Base.metadata.create_all(bind=engine)
        logger.info("Таблицы успешно созданы.")
    except Exception as e:
        logger.error(f"Ошибка при создании таблиц: {e}")
        raise 