import logging
import asyncio
from datetime import datetime, time

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ChatMemberHandler, TypeHandler
from telegram.constants import ChatAction, ParseMode

from data_storage import save_update_data, save_raw_update # Импортируем функции сохранения

logger = logging.getLogger(__name__)

class ChatDataCollectorBot:
    def __init__(self, token, channel_id):
        self.token = token
        # channel_id пока не используется, но оставим на будущее
        self.channel_id = channel_id 
        # self.database = ChatDatabase() # Убираем БД
        # self.summarizer = YandexGPTSummarizer() # Убираем саммаризатор
        self.app = Application.builder().token(token).build()
        
        # Регистрируем обработчики
        self.register_handlers()
    
    async def save_all_updates(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохраняет любое необработанное обновление в raw_updates."""
        if update:
            save_raw_update(update.to_dict())
            
    def register_handlers(self):
        """Регистрация обработчиков"""
        # Обработчик для сохранения всех сырых обновлений (вызывается первым)
        self.app.add_handler(TypeHandler(Update, self.save_all_updates), group=-1)
        
        # Основные обработчики для структурированного сохранения
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        # Убираем команду summarize, так как убрали саммаризатор
        # self.app.add_handler(CommandHandler("summarize", self.manual_summarize))
        # Используем широкий фильтр для сохранения всех типов сообщений
        self.app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), self.store_message_update))
        self.app.add_handler(ChatMemberHandler(self.track_chats_update))
        # Можно добавить обработчики для других типов обновлений, если нужно
        # self.app.add_handler(CallbackQueryHandler(self.button_handler))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        await update.message.reply_text(
            "Привет! Я бот для сбора данных из чатов. Просто добавьте меня в чат."
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        await update.message.reply_text(
            "Я собираю данные из чатов для последующего анализа.\n"
            "Доступные команды:\n"
            "/start - Начать работу с ботом\n"
            "/help - Показать справку"
        )

    # Убираем метод manual_summarize
    # async def manual_summarize(self, update: Update, context: ContextTypes.DEFAULT_TYPE): ...

    # Убираем метод _create_and_send_thread_summary
    # async def _create_and_send_thread_summary(...): ...
    
    async def track_chats_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохраняет обновление об изменении статуса участника чата."""
        if update.chat_member:
            save_update_data('chat_member', update.to_dict())
            # Логируем важное событие
            chat = update.chat_member.chat
            user = update.chat_member.from_user
            new_status = update.chat_member.new_chat_member.status
            old_status = update.chat_member.old_chat_member.status
            if new_status == "member" and old_status != "member":
                 logger.info(f"Бот добавлен в чат: {chat.title} ({chat.id}) пользователем {user.username or user.id}")
            elif new_status != "member" and old_status == "member":
                 logger.info(f"Бот удален/изменен статус в чате: {chat.title} ({chat.id})")

    async def store_message_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохраняет обновление с сообщением."""
        # Сохраняем все сообщение как есть
        if update.effective_message:
             save_update_data('message', update.to_dict())
             # Можно добавить логирование, если нужно
             # chat = update.effective_chat
             # user = update.effective_user
             # logger.debug(f"Сообщение от {user.username or user.id} в чате {chat.title or chat.id}")

    # Убираем метод create_and_send_summary
    # async def create_and_send_summary(...): ...
    
    def run(self):
        """Запуск бота"""
        logger.info("Chat Data Collector Bot запущен")
        self.app.run_polling()
