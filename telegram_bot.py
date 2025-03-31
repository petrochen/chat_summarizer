import logging
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from chat_database import ChatDatabase
from yandex_gpt_summarizer import YandexGPTSummarizer

logger = logging.getLogger(__name__)

class ChatSummarizerBot:
    def __init__(self, token, channel_id):
        self.token = token
        self.channel_id = channel_id
        self.database = ChatDatabase()
        self.summarizer = YandexGPTSummarizer()
        self.app = Application.builder().token(token).build()
        
        # Регистрируем обработчики команд
        self.register_handlers()
    
    def register_handlers(self):
        """Регистрация обработчиков команд и сообщений"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("summarize", self.manual_summarize))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.store_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        await update.message.reply_text(
            "Привет! Я бот для создания саммари чатов. Добавьте меня в групповой чат, "
            "и я буду создавать сводки сообщений по запросу в указанном канале."
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        await update.message.reply_text(
            "Доступные команды:\n"
            "/start - Начать работу с ботом\n"
            "/help - Показать справку\n"
            "/summarize - Создать саммари для всего чата\n"
            "/summarize [ID темы] - Создать саммари для конкретной темы"
        )

    async def manual_summarize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Создание саммари вручную по команде"""
        chat_id = update.effective_chat.id

        # Проверяем, имеет ли пользователь права администратора
        chat_member = await context.bot.get_chat_member(chat_id, update.effective_user.id)
        if chat_member.status not in ["administrator", "creator"]:
            await update.message.reply_text("Только администраторы могут запускать создание саммари вручную.")
            return

        # Проверяем, указан ли ID темы в команде
        thread_id = None
        if context.args and len(context.args) > 0:
            try:
                thread_id = int(context.args[0])
                await update.message.reply_text(f"Создаю саммари для темы {thread_id}...")
            except ValueError:
                await update.message.reply_text("Неверный формат ID темы. Использование: /summarize [ID темы]")
                return
        else:
            await update.message.reply_text("Создаю саммари для всего чата...")

        await self.create_and_send_summary(chat_id, thread_id)

    async def _create_and_send_thread_summary(self, chat_id, chat_title, thread_id, messages, chat_stats):
        """
        Создание и отправка саммари для конкретной темы

        Args:
            chat_id: ID чата
            chat_title: Название чата
            thread_id: ID темы (None для сообщений вне тем)
            messages: Список сообщений
            chat_stats: Статистика по чату
        """
        if not messages:
            logger.info(f"Нет сообщений в теме {thread_id} чата {chat_title}")
            return

        # Получаем название темы, если возможно
        thread_name = f"Тема {thread_id}" if thread_id else "Основной чат"

        # Для первого сообщения в теме можно попытаться получить его текст как название темы
        if thread_id:
            first_message = min(messages, key=lambda m: m.date) if messages else None
            if first_message and first_message.text:
                thread_name = first_message.text[:30] + "..." if len(first_message.text) > 30 else first_message.text

        logger.info(f"Создаю саммари для {thread_name} в чате '{chat_title}' на основе {len(messages)} сообщений")

        # Создаем саммари
        summary_text = self.summarizer.create_summary(messages)

        # Формируем заголовок
        if thread_id:
            header = f"📌 *Саммари темы: {thread_name}*\n"
            header += f"📊 Чат: {chat_title}\n"
        else:
            header = f"📊 *Саммари основного чата: {chat_title}*\n"

        header += f"🗓 {datetime.now().strftime('%d.%m.%Y')}\n"
        header += f"💬 Проанализировано сообщений: {len(messages)}\n"

        # Добавляем статистику активности
        if chat_stats:
            header += f"👥 Активных пользователей: {chat_stats.get('active_users', 0)}\n"

            # Добавляем процент медиа-контента
            media_count = sum(1 for m in messages if m.has_media)
            if messages:
                media_percent = (media_count / len(messages)) * 100
                header += f"📷 Медиа-контент: {media_count} ({media_percent:.1f}%)\n"

        header += "\n"

        full_text = f"{header}{summary_text}"

        # Сохраняем саммари в базу данных
        summary = self.database.store_summary(
            chat_id=chat_id,
            text=summary_text,
            message_count=len(messages)
        )

        # Публикуем саммари в канал
        try:
            await self.app.bot.send_message(
                chat_id=self.channel_id,
                text=full_text,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )

            # Отмечаем саммари как опубликованное
            if summary:
                self.database.mark_summary_as_published(summary.id)

        except Exception as e:
            logger.error(f"Ошибка при отправке саммари в канал: {str(e)}")

            # Если сообщение слишком длинное, разбиваем его на части
            if "message is too long" in str(e).lower():
                logger.info("Сообщение слишком длинное, разбиваю на части")

                # Отправляем заголовок
                await self.app.bot.send_message(
                    chat_id=self.channel_id,
                    text=header,
                    parse_mode="Markdown"
                )

                # Разбиваем основной текст на части по 4000 символов
                max_length = 4000
                for i in range(0, len(summary_text), max_length):
                    part = summary_text[i:i+max_length]
                    part_header = f"*Часть {i//max_length + 1}*\n\n" if i > 0 else ""

                    await self.app.bot.send_message(
                        chat_id=self.channel_id,
                        text=f"{part_header}{part}",
                        parse_mode="Markdown",
                        disable_web_page_preview=True
                    )
                    await asyncio.sleep(0.5)  # Небольшая пауза между отправками

        # Отмечаем сообщения как обработанные
        self.database.mark_messages_as_summarized(messages)

        logger.info(f"Саммари для {thread_name} в чате '{chat_title}' успешно создано и опубликовано")
    
    async def store_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохранение сообщений из чата в базу данных"""
        message = update.message
        chat_id = update.effective_chat.id
        user = message.from_user

        # Сохраняем информацию о чате и пользователе
        self.database.get_or_create_chat(
            chat_id=chat_id,
            title=update.effective_chat.title,
            chat_type=update.effective_chat.type
        )

        self.database.get_or_create_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            is_bot=user.is_bot,
            language_code=user.language_code,
            is_premium=getattr(user, 'is_premium', False)
        )

        # Определяем, является ли сообщение вопросом
        text = message.text or ""
        is_question = "?" in text or any(text.lower().startswith(q)
                                     for q in ["кто", "что", "где", "когда", "почему", "как", "сколько"])

        # Сохраняем сообщение в БД
        self.database.store_message(
            message_id=message.message_id,
            chat_id=chat_id,
            user_id=user.id,
            text=text,
            date=message.date,
            is_question=is_question
        )
    
    async def create_and_send_summary(self, chat_id=None, thread_id=None):
        """
        Создание и публикация саммари в канал

        Args:
            chat_id: ID чата (если None, то для всех чатов)
            thread_id: ID темы (если None, то для всех тем или отдельно для каждой темы)
        """
        try:
            # Если не указан конкретный чат, создаем саммари для всех чатов с достаточным количеством сообщений
            if chat_id:
                chat_ids = [chat_id]
                chats = [self.database.get_or_create_chat(chat_id=chat_id)]
            else:
                # Получаем чаты с достаточным количеством сообщений
                chats = self.database.get_chats_with_enough_messages()
                chat_ids = [chat.chat_id for chat in chats]

            if not chat_ids:
                logger.info("Нет чатов для создания саммари")
                return

            # Если есть несколько чатов, отправляем сначала вводное сообщение
            if len(chat_ids) > 1:
                intro_text = f"📋 *Ежедневные саммари по {len(chat_ids)} чатам*\n\n"
                await self.app.bot.send_message(
                    chat_id=self.channel_id,
                    text=intro_text,
                    parse_mode="Markdown"
                )

            for i, chat in enumerate(chats):
                chat_id = chat.chat_id
                chat_title = chat.title or f"Чат {chat_id}"

                # Получаем статистику по чату
                chat_stats = self.database.get_chat_statistics(chat_id, days=1)

                # Проверяем, есть ли в чате темы с достаточным количеством сообщений
                threads = self.database.get_chat_threads(chat_id)

                # Если указан конкретный thread_id, обрабатываем только его
                if thread_id is not None:
                    # Получаем сообщения только из указанной темы
                    messages = self.database.get_messages_for_last_day(chat_id, thread_id=thread_id)
                    if messages:
                        await self._create_and_send_thread_summary(chat_id, chat_title, thread_id, messages, chat_stats)
                    else:
                        logger.info(f"Нет сообщений в теме {thread_id} чата {chat_title}")
                    continue

                # Если в чате есть темы, создаем саммари для каждой темы отдельно
                if threads:
                    logger.info(f"Найдено {len(threads)} тем в чате {chat_title}")

                    # Отправляем вводное сообщение для тем чата
                    thread_intro = f"📋 *Саммари по темам чата: {chat_title}*\n"
                    thread_intro += f"🗓 {datetime.now().strftime('%d.%m.%Y')}\n"
                    thread_intro += f"📌 Количество активных тем: {len(threads)}\n\n"

                    await self.app.bot.send_message(
                        chat_id=self.channel_id,
                        text=thread_intro,
                        parse_mode="Markdown"
                    )

                    # Обрабатываем каждую тему отдельно
                    for thread_id, message_count in threads:
                        messages = self.database.get_messages_for_last_day(chat_id, thread_id=thread_id)
                        await self._create_and_send_thread_summary(chat_id, chat_title, thread_id, messages, chat_stats)
                        await asyncio.sleep(1)  # Пауза между отправками

                    # Также создаем общее саммари для сообщений вне тем
                    messages_no_thread = self.database.get_messages_for_last_day(chat_id, thread_id=None)
                    if messages_no_thread:
                        await self._create_and_send_thread_summary(chat_id, chat_title, None, messages_no_thread, chat_stats)
                else:
                    # Если тем нет, обрабатываем все сообщения чата вместе
                    messages = self.database.get_messages_for_last_day(chat_id)

                    if not messages:
                        logger.info(f"Нет сообщений за последний день в чате {chat_title}")
                        continue

                    logger.info(f"Создаю саммари для чата '{chat_title}' на основе {len(messages)} сообщений")

                    # Создаем саммари только для сообщений этого чата
                    summary_text = self.summarizer.create_summary(messages)

                    # Добавляем четкую отметку, из какого чата это саммари
                    header = f"📊 *Саммари чата: {chat_title}*\n"
                    header += f"🗓 {datetime.now().strftime('%d.%m.%Y')}\n"
                    header += f"💬 Проанализировано сообщений: {len(messages)}\n"

                    # Добавляем статистику активности
                    if chat_stats:
                        header += f"👥 Активных пользователей: {chat_stats.get('active_users', 0)}\n"

                        # Добавляем процент медиа-контента
                        media_percent = 0
                        if chat_stats.get('total_messages', 0) > 0:
                            media_percent = (chat_stats.get('media_messages', 0) / chat_stats.get('total_messages', 0)) * 100
                        header += f"📷 Медиа-контент: {chat_stats.get('media_messages', 0)} ({media_percent:.1f}%)\n"

                    header += "\n"

                    full_text = f"{header}{summary_text}"

                    # Сохраняем саммари в базу данных
                    summary = self.database.store_summary(
                        chat_id=chat_id,
                        text=summary_text,
                        message_count=len(messages)
                    )

                # Публикуем саммари в канал с четким обозначением чата
                try:
                    await self.app.bot.send_message(
                        chat_id=self.channel_id,
                        text=full_text,
                        parse_mode="Markdown",
                        disable_web_page_preview=True
                    )

                    # Отмечаем саммари как опубликованное
                    if summary:
                        self.database.mark_summary_as_published(summary.id)

                except Exception as e:
                    logger.error(f"Ошибка при отправке саммари в канал: {str(e)}")

                    # Если сообщение слишком длинное, разбиваем его на части
                    if "message is too long" in str(e).lower():
                        logger.info("Сообщение слишком длинное, разбиваю на части")

                        # Отправляем заголовок
                        await self.app.bot.send_message(
                            chat_id=self.channel_id,
                            text=header,
                            parse_mode="Markdown"
                        )

                        # Разбиваем основной текст на части по 4000 символов
                        max_length = 4000
                        for i in range(0, len(summary_text), max_length):
                            part = summary_text[i:i+max_length]
                            part_header = f"*Часть {i//max_length + 1}*\n\n" if i > 0 else ""

                            await self.app.bot.send_message(
                                chat_id=self.channel_id,
                                text=f"{part_header}{part}",
                                parse_mode="Markdown",
                                disable_web_page_preview=True
                            )
                            await asyncio.sleep(0.5)  # Небольшая пауза между отправками

                # Отмечаем сообщения из этого чата как обработанные
                self.database.mark_messages_as_summarized(messages)

                logger.info(f"Саммари для чата '{chat_title}' успешно создано и опубликовано")

                # Если саммари несколько, добавляем небольшую паузу между отправками
                if i < len(chats) - 1:
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Ошибка при создании саммари: {str(e)}")
    
    def run(self):
        """Запуск бота"""
        self.app.run_polling()
