import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DATA_DIR = "collected_data"

def ensure_data_dir():
    """Создает директорию для хранения данных, если она не существует."""
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR)
            logger.info(f"Создана директория для данных: {DATA_DIR}")
        except OSError as e:
            logger.error(f"Не удалось создать директорию {DATA_DIR}: {e}")

def save_update_data(update_type: str, data: dict):
    """Сохраняет данные обновления (сообщение, обновление участника и т.д.) в JSON-файл.

    Args:
        update_type: Тип обновления (например, 'message', 'chat_member').
        data: Словарь с данными для сохранения.
    """
    ensure_data_dir()
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H-%M-%S-%f")
    
    # Создаем поддиректорию для типа обновления и даты
    type_dir = os.path.join(DATA_DIR, update_type)
    date_dir = os.path.join(type_dir, date_str)
    os.makedirs(date_dir, exist_ok=True)
    
    # Формируем имя файла
    chat_id = data.get('chat', {}).get('id') or data.get('message', {}).get('chat', {}).get('id')
    update_id = data.get('update_id')
    filename_parts = [time_str]
    if chat_id:
        filename_parts.append(f"chat_{chat_id}")
    if update_id:
        filename_parts.append(f"update_{update_id}")
        
    filename = "__".join(str(p) for p in filename_parts) + ".json"
    filepath = os.path.join(date_dir, filename)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        # logger.debug(f"Данные типа '{update_type}' сохранены в {filepath}")
    except TypeError as e:
        logger.error(f"Ошибка сериализации JSON при сохранении в {filepath}: {e}")
    except IOError as e:
        logger.error(f"Ошибка записи в файл {filepath}: {e}")

def save_raw_update(update_data: dict):
    """Сохраняет полное необработанное обновление от Telegram.
    
    Args:
        update_data: Словарь с данными обновления.
    """
    ensure_data_dir()
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H-%M-%S-%f")
    
    # Директория для сырых обновлений
    raw_dir = os.path.join(DATA_DIR, "raw_updates", date_str)
    os.makedirs(raw_dir, exist_ok=True)
    
    update_id = update_data.get('update_id')
    filename = f"{time_str}__update_{update_id}.json" if update_id else f"{time_str}__update.json"
    filepath = os.path.join(raw_dir, filename)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(update_data, f, ensure_ascii=False, indent=4)
        # logger.debug(f"Сырое обновление {update_id} сохранено в {filepath}")
    except TypeError as e:
        logger.error(f"Ошибка сериализации JSON при сохранении сырого обновления в {filepath}: {e}")
    except IOError as e:
        logger.error(f"Ошибка записи в файл сырого обновления {filepath}: {e}") 