import logging
import json
import requests
import time
from collections import Counter
import re
from config import YANDEX_GPT_API_KEY, YANDEX_GPT_API_URL, YANDEX_GPT_MODEL, RETRY_ATTEMPTS, RETRY_DELAY

logger = logging.getLogger(__name__)

class YandexGPTSummarizer:
    """Класс для создания саммари сообщений с использованием Yandex GPT"""
    
    def __init__(self):
        """Инициализация summarizer"""
        # Слова, которые следует игнорировать при анализе
        self.stop_words = {"и", "в", "на", "с", "по", "к", "у", "за", "из", "о", "что", "как", "а", "то", 
                           "так", "но", "не", "да", "для", "этот", "вот", "от", "был", "бы"}
        
        # Заголовки для API запросов к Yandex GPT
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {YANDEX_GPT_API_KEY}"
        }
    
    def prepare_messages_for_gpt(self, messages):
        """
        Подготовка сообщений для отправки в Yandex GPT
        
        Args:
            messages: Список объектов сообщений
            
        Returns:
            str: Подготовленный текст сообщений
        """
        # Проверяем, что все сообщения из одного чата
        chat_ids = set(message.chat_id for message in messages)
        if len(chat_ids) > 1:
            logger.warning(f"Подготовка сообщений из разных чатов! {chat_ids}")
        
        prepared_text = []
        for message in messages:
            name = message.first_name
            if message.last_name:
                name += f" {message.last_name}"
            
            # Формат: [Время] Имя: Текст
            time_str = message.date.strftime("%H:%M:%S")
            prepared_text.append(f"[{time_str}] {name}: {message.text}")
        
        return "\n".join(prepared_text)
    
    def call_yandex_gpt(self, prompt):
        """
        Отправка запроса к Yandex GPT API с повторными попытками

        Args:
            prompt: Текст запроса

        Returns:
            str: Ответ от API
        """
        for attempt in range(RETRY_ATTEMPTS):
            try:
                payload = {
                    "model": YANDEX_GPT_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "text": "Ты - аналитик чатов. Твоя задача - создать краткое саммари сообщений из группового чата. Включи в саммари: 1) Основные темы обсуждения, 2) Ключевые выводы или решения, 3) Самые активные дискуссии. Формат ответа должен быть в Markdown."
                        },
                        {
                            "role": "user",
                            "text": f"Проанализируй следующие сообщения из группового чата и создай краткое саммари:\n\n{prompt}"
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 800
                }

                response = requests.post(YANDEX_GPT_API_URL, headers=self.headers, json=payload, timeout=30)
                response.raise_for_status()

                result = response.json()
                if "result" in result and "alternatives" in result["result"] and len(result["result"]["alternatives"]) > 0:
                    return result["result"]["alternatives"][0]["message"]["text"]
                else:
                    logger.error(f"Неожиданный формат ответа от Yandex GPT: {result}")

                    if attempt < RETRY_ATTEMPTS - 1:
                        logger.info(f"Повторная попытка {attempt+1}/{RETRY_ATTEMPTS} через {RETRY_DELAY} секунд...")
                        time.sleep(RETRY_DELAY)
                    else:
                        return None
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка при вызове Yandex GPT API (попытка {attempt+1}/{RETRY_ATTEMPTS}): {str(e)}")

                if attempt < RETRY_ATTEMPTS - 1:
                    logger.info(f"Повторная попытка через {RETRY_DELAY} секунд...")
                    time.sleep(RETRY_DELAY)
                else:
                    return None
            except Exception as e:
                logger.error(f"Неожиданная ошибка при вызове Yandex GPT API: {str(e)}")
                return None

        return None
    
    def create_summary(self, messages):
        """
        Создает саммари на основе сообщений, используя Yandex GPT

        Args:
            messages: Список объектов сообщений

        Returns:
            str: Текст саммари
        """
        if not messages:
            return "Нет сообщений для анализа."

        message_count = len(messages)

        # Создаем базовую статистику
        basic_stats = self.create_basic_stats(messages)

        # Подготавливаем сообщения для отправки в Yandex GPT
        prepared_messages = self.prepare_messages_for_gpt(messages)

        # Получаем саммари от Yandex GPT
        gpt_summary = self.call_yandex_gpt(prepared_messages)

        if gpt_summary:
            # Объединяем статистику с саммари от GPT
            full_summary = f"{basic_stats}\n\n*Анализ Yandex GPT:*\n{gpt_summary}"
            return full_summary
        else:
            # Если GPT не сработал, используем резервный метод
            logger.warning("Не удалось получить саммари от Yandex GPT, использую резервный метод")
            return self.create_fallback_summary(messages, basic_stats)
    
    def create_basic_stats(self, messages):
        """
        Создает базовую статистику по сообщениям
        
        Args:
            messages: Список объектов сообщений
            
        Returns:
            str: Текст статистики
        """
        if not messages:
            return "Нет данных для статистики."

        # Подсчитываем количество сообщений по часам
        hour_counts = Counter()
        for message in messages:
            hour_counts[message.date.hour] += 1

        # Находим самый активный час
        most_active_hour = max(hour_counts.items(), key=lambda x: x[1])

        # Формируем статистику
        stats = "*📊 Статистика чата:*\n"
        stats += f"💬 Всего сообщений: {len(messages)}\n"
        stats += f"👥 Уникальных отправителей: {len(set(m.id for m in messages))}\n"
        stats += f"❓ Вопросов: {sum(1 for m in messages if m.is_question)}\n"
        stats += f"📷 Медиа-сообщений: {sum(1 for m in messages if m.has_media)}\n"
        stats += f"\n*Самый активный час:* {most_active_hour[0]}:00 ({most_active_hour[1]} сообщений)"
        
        return stats
    
    def create_fallback_summary(self, messages, basic_stats):
        """
        Резервный метод создания саммари, если Yandex GPT недоступен
        
        Args:
            messages: Список объектов сообщений
            basic_stats: Базовая статистика
            
        Returns:
            str: Текст саммари
        """
        # Анализ ключевых слов
        all_text = " ".join([message.text for message in messages]).lower()
        words = re.findall(r'\b[а-яёa-z]{4,}\b', all_text)
        words = [word for word in words if word not in self.stop_words]
        
        word_counter = Counter(words)
        top_words = word_counter.most_common(10)
        
        # Добавляем анализ ключевых слов к базовой статистике
        summary = f"{basic_stats}\n\n"
        
        summary += "*Популярные темы обсуждения:*\n"
        if top_words:
            for word, count in top_words:
                summary += f"• {word} ({count})\n"
        else:
            summary += "Не найдены ключевые слова\n"
        
        return summary
