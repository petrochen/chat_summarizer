from telegram import Update
from telegram.ext import ContextTypes
from chat_database import ChatDatabase
from config import MIN_MESSAGES
from datetime import datetime, timedelta

class CommandHandlers:
    def __init__(self, db: ChatDatabase):
        self.db = db

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        await update.message.reply_text(
            "Привет! Я бот для создания саммари чатов. "
            "Добавьте меня в чат, и я буду создавать саммари каждые 24 часа."
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = (
            "Я бот для создания саммари чатов.\n\n"
            "Команды:\n"
            "/start - Начать работу с ботом\n"
            "/help - Показать это сообщение\n"
            "/stats - Показать статистику чата\n"
            "/summary - Создать саммари вручную\n"
            "/settings - Настройки бота"
        )
        await update.message.reply_text(help_text)

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stats"""
        chat_id = update.effective_chat.id
        stats = self.db.get_chat_statistics(chat_id)
        
        if not stats:
            await update.message.reply_text("Нет данных для отображения статистики.")
            return

        stats_text = (
            f"Статистика чата за последние {stats['period_days']} дней:\n\n"
            f"Всего сообщений: {stats['total_messages']}\n"
            f"Активных пользователей: {stats['active_users']}\n"
            f"Медиа-сообщений: {stats['media_messages']}\n"
            f"Вопросов: {stats['questions']}"
        )
        await update.message.reply_text(stats_text)

    async def summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /summary"""
        chat_id = update.effective_chat.id
        messages = self.db.get_messages_for_last_day(chat_id)
        
        if not messages:
            await update.message.reply_text("Нет новых сообщений для создания саммари.")
            return

        if len(messages) < MIN_MESSAGES:
            await update.message.reply_text(
                f"Недостаточно сообщений для создания саммари. "
                f"Минимум: {MIN_MESSAGES}, текущее количество: {len(messages)}"
            )
            return

        # TODO: Добавить логику создания саммари
        await update.message.reply_text("Создание саммари...")

    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /settings"""
        settings_text = (
            "Настройки бота:\n\n"
            f"Минимальное количество сообщений для саммари: {MIN_MESSAGES}\n"
            "Интервал создания саммари: 24 часа"
        )
        await update.message.reply_text(settings_text) 