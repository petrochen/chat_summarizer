import os
import json
import logging
import asyncio
import datetime
from sqlalchemy.orm import Session

from telegram import Update, Bot, Message
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackContext,
    ContextTypes, ChatMemberHandler, filters, 
    MessageReactionHandler, JobQueue
)
from telegram.ext.filters import BaseFilter
from telegram.constants import ChatAction, ParseMode

from database import SessionLocal, get_db # Импортируем сессию и зависимость
import crud # Импортируем функции CRUD
import models # Импортируем модели (для type hinting)
# Если саммаризация нужна, раскомментируйте:
# from yandex_gpt_summarizer import YandexGPTSummarizer
from config import BOT_TOKEN, CHANNEL_ID, MIN_MESSAGES, SUMMARY_TIME # Добавим SUMMARY_TIME

logger = logging.getLogger(__name__)

# --- Вспомогательная функция для получения сессии --- 
def get_session() -> Session:
    """Создает и возвращает новую сессию SQLAlchemy."""
    return SessionLocal()

class ChatSummarizerBot:
    def __init__(self, token, channel_id):
        self.token = token
        self.channel_id = channel_id
        # self.summarizer = YandexGPTSummarizer() # Если саммаризация нужна
        self.app = Application.builder().token(token).build()
        self.job_queue: JobQueue = self.app.job_queue
        
        self.register_handlers()
        # self.schedule_daily_summary() # Если нужна автоматическая саммаризация
            
    def register_handlers(self):
        """Регистрация обработчиков"""
        # Команды
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("summarize", self.manual_summarize))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        
        # Сообщения и события
        self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.new_member_handler))
        self.app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, self.left_member_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.store_message_handler))
        self.app.add_handler(MessageHandler(filters.CAPTION & (~filters.COMMAND), self.store_message_handler))
        # Используем общий фильтр ATTACHMENT для всех вложений
        # media_filters: BaseFilter = filters.PHOTO | filters.VIDEO | filters.DOCUMENT | filters.AUDIO | filters.STICKER | filters.ANIMATION
        # self.app.add_handler(MessageHandler(media_filters, self.store_message_handler))
        # Или можно добавить отдельные обработчики для каждого типа, если ATTACHMENT не подходит:
        self.app.add_handler(MessageHandler(filters.ATTACHMENT, self.store_message_handler))
        # self.app.add_handler(MessageHandler(filters.PHOTO, self.store_message_handler))
        # self.app.add_handler(MessageHandler(filters.VIDEO, self.store_message_handler))
        # self.app.add_handler(MessageHandler(filters.AUDIO, self.store_message_handler))
        # self.app.add_handler(MessageHandler(filters.Sticker(), self.store_message_handler)) # Sticker может быть классом
        # self.app.add_handler(MessageHandler(filters.ANIMATION, self.store_message_handler))
        
        # Фильтры типов обновлений
        # Заменяем на существующий метод или создаем заглушку
        # self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.new_members_handler))
        
        # Отслеживание изменений сообщений - используем правильный фильтр в версии 22.0 
        self.app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE, self.store_edited_message_handler))
        
        # Отслеживание реакций на сообщения - используем специальный обработчик реакций
        self.app.add_handler(MessageReactionHandler(callback=self.reaction_handler))
        
        # Обработчик изменений статуса бота в чате
        self.app.add_handler(ChatMemberHandler(self.track_chats_handler, ChatMemberHandler.MY_CHAT_MEMBER))
    
    # --- Обработчики команд ---
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Привет! Я бот для создания саммари. Добавьте меня в чат.")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Команды: /start, /help, /summarize [опционально дни], /stats")
        
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает статистику по чату."""
        if not update.effective_chat: return
        chat_id = update.effective_chat.id
        # TODO: Реализовать сбор и отображение статистики из БД
        await update.message.reply_text(f"Статистика для чата {chat_id} пока не реализована.")

    async def manual_summarize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Создание саммари вручную."""
        if not update.effective_chat or not update.effective_user: return
        
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        # Проверка прав (опционально, можно разрешить всем)
        # member = await context.bot.get_chat_member(chat_id, user_id)
        # if member.status not in ["administrator", "creator"]:
        #     await update.message.reply_text("Только администраторы могут запустить саммари.")
        #     return
            
        days = 1 # По умолчанию за 1 день
        if context.args:
            try:
                days = int(context.args[0])
                if days <= 0:
                    await update.message.reply_text("Количество дней должно быть положительным.")
                    return
            except ValueError:
                await update.message.reply_text("Неверный формат количества дней.")
                return

        await update.message.reply_text(f"Создаю саммари за последние {days} дней...")
        await self.create_and_send_summary_job(context, chat_id=chat_id, days=days)

    # --- Обработчики сообщений и событий ---
    
    def _get_data_from_update(self, update: Update):
        """Извлекает основные данные (чат, пользователь, сообщение) из обновления."""
        message = update.effective_message
        chat = update.effective_chat
        user = update.effective_user
        return message, chat, user

    async def store_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает и сохраняет новое сообщение."""
        message, chat, user = self._get_data_from_update(update)
        if not message or not chat or not user:
            # logger.debug("Пропуск обновления без сообщения/чата/пользователя")
            return
        
        # Преобразуем объекты Telegram в словари
        message_dict = message.to_dict()
        # Добавляем chat и from внутрь словаря сообщения для create_message
        message_dict['chat'] = chat.to_dict()
        message_dict['from'] = user.to_dict()
        
        db = get_session()
        try:
            created_msg = crud.create_message(db, message_dict)
            if created_msg:
                # logger.debug(f"Сообщение {created_msg.internal_id} сохранено.")
                pass
        finally:
            db.close()
    
    async def store_edited_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает и обновляет отредактированное сообщение."""
        # Получаем данные из обновления
        message = update.edited_message
        chat = update.effective_chat
        user = update.effective_user
        
        if not message or not chat or not user:
            # logger.debug("Пропуск обновления без сообщения/чата/пользователя")
            return
            
        # Преобразуем объекты Telegram в словари
        message_dict = message.to_dict()
        # Добавляем chat и from внутрь словаря сообщения для update_message
        message_dict['chat'] = chat.to_dict()
        message_dict['from'] = user.to_dict()
        
        db = get_session()
        try:
            # Обновляем сообщение в базе данных
            updated_msg = crud.update_message(db, message_dict)
            if updated_msg:
                # logger.debug(f"Сообщение {updated_msg.internal_id} обновлено.")
                pass
        finally:
            db.close()

    async def reaction_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает обновление реакций."""
        if update.message_reaction:
            db = get_session()
            try:
                crud.update_reactions(db, update.message_reaction.to_dict())
                # logger.debug("Реакции обновлены.")
            finally:
                db.close()

    async def track_chats_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отслеживает добавление/удаление бота из чатов."""
        if not update.my_chat_member: return
        
        result = update.my_chat_member
        chat = result.chat
        new_status = result.new_chat_member.status
        old_status = result.old_chat_member.status
        user_who_changed = result.from_user # Пользователь, который изменил статус бота
        
        db = get_session()
        try:
            # Гарантируем наличие пользователя, который изменил статус
            if user_who_changed:
                 crud.get_or_create_user(db, user_who_changed.to_dict())
                 
            if new_status in ["member", "administrator"] and old_status not in ["member", "administrator"]:
                logger.info(f"Бот добавлен в чат: {chat.title} ({chat.id})")
                # Пытаемся получить member_count, но не падаем, если не удается
                member_count = None
                try:
                    member_count = await context.bot.get_chat_member_count(chat.id)
                except Exception as e:
                    logger.warning(f"Не удалось получить member_count для чата {chat.id}: {e}")
                chat_data = chat.to_dict()
                chat_data['member_count'] = member_count # Добавляем member_count, если получили
                crud.get_or_create_chat(db, chat_data)
            elif new_status in ["left", "kicked"] and old_status not in ["left", "kicked"]:
                logger.info(f"Бот удален/заблокирован из чата: {chat.title} ({chat.id})")
                crud.deactivate_chat(db, chat.id)
            else:
                # Другие изменения статуса (например, повышение до админа) - обновим чат
                 logger.info(f"Статус бота изменен в чате: {chat.title} ({chat.id}) -> {new_status}")
                 crud.get_or_create_chat(db, chat.to_dict())
        finally:
            db.close()
            
    async def new_member_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает добавление новых участников в чат."""
        if update.message and update.message.new_chat_members:
            db = get_session()
            try:
                 chat_data = update.effective_chat.to_dict()
                 crud.get_or_create_chat(db, chat_data)
                 for member_data in update.message.new_chat_members:
                      crud.get_or_create_user(db, member_data.to_dict())
                      logger.info(f"Пользователь {member_data.username or member_data.id} добавлен в чат {chat_data.get('id')}")
            finally: 
                db.close()
                
    async def left_member_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выход/удаление участника из чата."""
        if update.message and update.message.left_chat_member:
            db = get_session()
            try:
                 chat_data = update.effective_chat.to_dict()
                 crud.get_or_create_chat(db, chat_data)
                 member_data = update.message.left_chat_member
                 # Пользователя не удаляем, просто логируем
                 logger.info(f"Пользователь {member_data.username or member_data.id} покинул/удален из чата {chat_data.get('id')}")
            finally: 
                 db.close()

    # --- Логика саммаризации (если нужна) ---
    
    def schedule_daily_summary(self):
        """Планирует ежедневное создание саммари."""
        try:
            # Разбираем время из конфига
            summary_h, summary_m = map(int, SUMMARY_TIME.split(':'))
            run_time = datetime.time(hour=summary_h, minute=summary_m, tzinfo=datetime.timezone.utc)
            self.job_queue.run_daily(self.create_and_send_summary_job, time=run_time, name="daily_summary")
            logger.info(f"Ежедневная задача саммаризации запланирована на {SUMMARY_TIME} UTC")
        except ValueError:
            logger.error(f"Неверный формат SUMMARY_TIME: {SUMMARY_TIME}. Используйте HH:MM.")
        except Exception as e:
            logger.error(f"Ошибка при планировании задачи саммаризации: {e}")

    async def create_and_send_summary_job(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int | None = None, days: int = 1):
        """Задача для создания и отправки саммари (может вызываться планировщиком или вручную)."""
        logger.info(f"Запуск задачи создания саммари (chat_id={chat_id}, days={days})")
        db = get_session()
        try:
            target_chats = []
            if chat_id:
                chat = crud.get_chat(db, chat_id)
                if chat and chat.is_active:
                    target_chats.append(chat)
                else:
                     logger.warning(f"Чат {chat_id} не найден или неактивен для саммари.")
            else:
                # TODO: Получить все активные чаты из БД
                # target_chats = crud.get_active_chats(db)
                logger.warning("Автоматическая саммаризация для всех чатов пока не реализована.")
                return # Пока выходим, если chat_id не указан

            for chat in target_chats:
                # TODO: Реализовать получение сообщений за N дней
                # messages = crud.get_unsummarized_messages_for_period(db, chat.chat_id, days=days)
                messages = crud.get_unsummarized_messages(db, chat.chat_id, limit=500) # Пока берем необработанные

                if not messages or len(messages) < MIN_MESSAGES:
                    logger.info(f"Недостаточно сообщений ({len(messages)}/{MIN_MESSAGES}) для саммари в чате {chat.title} ({chat.chat_id})")
                    continue

                logger.info(f"Создание саммари для чата '{chat.title}' ({chat.chat_id}) из {len(messages)} сообщений...")
                
                # ---- Здесь должна быть логика вызова саммаризатора ----
                # summary_text = self.summarizer.create_summary(messages)
                # ---- Временно ставим заглушку ----
                summary_text = f"Это заглушка саммари для {len(messages)} сообщений."
                # ---------------------------------
                
                if not summary_text:
                    logger.error(f"Саммаризатор вернул пустой текст для чата {chat.chat_id}")
                    continue
                    
                first_msg_id = messages[0].internal_id
                last_msg_id = messages[-1].internal_id

                # Сохраняем саммари в БД
                summary_db = crud.create_summary(
                    db=db,
                    chat_id=chat.chat_id,
                    text=summary_text,
                    message_count=len(messages),
                    first_message_internal_id=first_msg_id,
                    last_message_internal_id=last_msg_id
                )
                
                if not summary_db:
                    logger.error(f"Не удалось сохранить саммари для чата {chat.chat_id} в БД.")
                    continue

                # Формируем сообщение для канала
                header = f"📊 *Саммари чата: {chat.title}*\n"
                header += f"🗓 За период: последние {len(messages)} сообщ. (до {messages[-1].date_ts.strftime('%Y-%m-%d %H:%M')})\n\n"
                full_text = f"{header}{summary_text}"

                # Отправляем в канал
                try:
                    # TODO: Проверить длину сообщения и разбить при необходимости
                    await context.bot.send_message(
                        chat_id=self.channel_id,
                        text=full_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    # Отмечаем саммари как опубликованное
                    crud.mark_summary_as_published(db, summary_db.id)
                    # Отмечаем сообщения как обработанные
                    internal_ids = [m.internal_id for m in messages]
                    crud.mark_messages_as_summarized(db, internal_ids)
                    logger.info(f"Саммари для чата '{chat.title}' ({chat.chat_id}) успешно создано и опубликовано.")
                except Exception as e:
                    logger.error(f"Ошибка при отправке саммари для чата {chat.chat_id} в канал: {e}")
                    # Важно не падать, если отправка не удалась
                
                await asyncio.sleep(1) # Небольшая пауза между чатами

        except Exception as e:
            logger.exception(f"Критическая ошибка в задаче создания саммари: {e}")
        finally:
            db.close()
            logger.info("Задача создания саммари завершена.")

    def run(self):
        """Запуск бота"""
        logger.info("Chat Summarizer Bot (DB version) запущен")
        self.app.run_polling()
