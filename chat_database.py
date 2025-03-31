import logging
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float, JSON, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from config import DATABASE_URI, RETRY_ATTEMPTS, RETRY_DELAY
import time

logger = logging.getLogger(__name__)
engine = create_engine(DATABASE_URI)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Chat(Base):
    """Модель для хранения информации о чатах"""
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, unique=True, nullable=False)
    title = Column(String(255), nullable=True)
    type = Column(String(50), nullable=True)  # private, group, supergroup, channel
    description = Column(Text, nullable=True)
    member_count = Column(Integer, nullable=True)
    join_date = Column(DateTime, default=datetime.now)
    last_activity = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Chat(id={self.id}, chat_id={self.chat_id}, title={self.title})>"

class User(Base):
    """Модель для хранения информации о пользователях"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    is_bot = Column(Boolean, default=False)
    language_code = Column(String(10), nullable=True)
    is_premium = Column(Boolean, default=False)
    first_seen = Column(DateTime, default=datetime.now)
    last_seen = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<User(id={self.id}, user_id={self.user_id}, username={self.username})>"

class Message(Base):
    """Модель для хранения сообщений"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, nullable=False)
    chat_id = Column(Integer, ForeignKey("chats.chat_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    reply_to_message_id = Column(Integer, nullable=True)
    forward_from_user_id = Column(Integer, nullable=True)
    forward_from_chat_id = Column(Integer, nullable=True)
    text = Column(Text, nullable=True)

    # Медиа-контент
    has_media = Column(Boolean, default=False)
    media_type = Column(String(50), nullable=True)  # photo, video, document, etc.
    media_file_id = Column(String(255), nullable=True)
    media_file_name = Column(String(255), nullable=True)
    caption = Column(Text, nullable=True)

    # Мета-данные
    date = Column(DateTime, nullable=False)
    edit_date = Column(DateTime, nullable=True)
    has_mentions = Column(Boolean, default=False)
    has_hashtags = Column(Boolean, default=False)
    entities = Column(JSON, nullable=True)  # JSON с entities из Telegram

    # Флаги для анализа
    is_question = Column(Boolean, default=False)
    is_command = Column(Boolean, default=False)
    summarized = Column(Boolean, default=False)

    # Отношения
    user = relationship("User", foreign_keys=[user_id])
    chat = relationship("Chat", foreign_keys=[chat_id])

    def __repr__(self):
        preview = self.text[:20] if self.text else f"[{self.media_type}]"
        return f"<Message(id={self.id}, chat_id={self.chat_id}, content={preview}...)>"

class Reaction(Base):
    """Модель для хранения реакций на сообщения"""
    __tablename__ = "reactions"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    emoji = Column(String(50), nullable=False)
    date = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Reaction(id={self.id}, message_id={self.message_id}, emoji={self.emoji})>"

class Summary(Base):
    """Модель для хранения созданных саммари"""
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.chat_id"), nullable=False)
    text = Column(Text, nullable=False)
    message_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    published = Column(Boolean, default=False)
    published_at = Column(DateTime, nullable=True)

    chat = relationship("Chat", foreign_keys=[chat_id])

    def __repr__(self):
        return f"<Summary(id={self.id}, chat_id={self.chat_id}, created_at={self.created_at})>"

class ChatDatabase:
    """Класс для работы с базой данных чатов"""
    
    def __init__(self):
        """Инициализация подключения к базе данных"""
        self.engine = create_engine(DATABASE_URI)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def _execute_with_retry(self, func, *args, **kwargs):
        """Выполнение функции с повторными попытками при ошибке"""
        for attempt in range(RETRY_ATTEMPTS):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt < RETRY_ATTEMPTS - 1:
                    logger.warning(f"Ошибка при выполнении запроса (попытка {attempt+1}/{RETRY_ATTEMPTS}): {str(e)}")
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Ошибка при выполнении запроса после {RETRY_ATTEMPTS} попыток: {str(e)}")
                    raise

    def get_or_create_chat(self, chat_id, title=None, chat_type=None, description=None, member_count=None):
        """Получение или создание записи о чате"""
        with self.Session() as db:
            try:
                chat = db.query(Chat).filter(Chat.chat_id == chat_id).first()

                if not chat:
                    chat = Chat(
                        chat_id=chat_id,
                        title=title,
                        type=chat_type,
                        description=description,
                        member_count=member_count
                    )
                    db.add(chat)
                    db.commit()
                else:
                    # Обновляем данные чата
                    chat.last_activity = datetime.now()
                    if title and chat.title != title:
                        chat.title = title
                    if chat_type:
                        chat.type = chat_type
                    if description:
                        chat.description = description
                    if member_count:
                        chat.member_count = member_count
                    db.commit()

                return chat
            except Exception as e:
                db.rollback()
                logger.error(f"Ошибка при получении/создании чата: {str(e)}")
                return None

    def get_or_create_user(self, user_id, username=None, first_name=None, last_name=None, is_bot=False, language_code=None, is_premium=False):
        """Получение или создание записи о пользователе"""
        with self.Session() as db:
            try:
                user = db.query(User).filter(User.user_id == user_id).first()

                if not user:
                    user = User(
                        user_id=user_id,
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        is_bot=is_bot,
                        language_code=language_code,
                        is_premium=is_premium
                    )
                    db.add(user)
                    db.commit()
                else:
                    # Обновляем данные пользователя и время последней активности
                    user.last_seen = datetime.now()
                    if username:
                        user.username = username
                    if first_name:
                        user.first_name = first_name
                    if last_name:
                        user.last_name = last_name
                    if language_code:
                        user.language_code = language_code
                    if is_premium:
                        user.is_premium = is_premium
                    db.commit()

                return user
            except Exception as e:
                db.rollback()
                logger.error(f"Ошибка при получении/создании пользователя: {str(e)}")
                return None

    def store_message(self, message_id, chat_id, user_id, text=None, date=None, reply_to_message_id=None,
                     forward_from_user_id=None, forward_from_chat_id=None,
                     has_media=False, media_type=None, media_file_id=None, media_file_name=None,
                     caption=None, edit_date=None, has_mentions=False, has_hashtags=False,
                     entities=None, is_question=False, is_command=False):
        """Сохранение сообщения в базе данных"""
        def _store():
            with self.Session() as db:
                try:
                    # Проверяем, существует ли уже такое сообщение
                    existing_message = db.query(Message).filter(
                        Message.message_id == message_id,
                        Message.chat_id == chat_id
                    ).first()

                    if existing_message:
                        # Если сообщение существует и было отредактировано
                        if edit_date and (not existing_message.edit_date or existing_message.edit_date < edit_date):
                            existing_message.text = text
                            existing_message.edit_date = edit_date
                            if entities:
                                existing_message.entities = entities
                            db.commit()
                        return existing_message

                    # Создаем новое сообщение
                    message = Message(
                        message_id=message_id,
                        chat_id=chat_id,
                        user_id=user_id,
                        text=text,
                        date=date or datetime.now(),
                        reply_to_message_id=reply_to_message_id,
                        forward_from_user_id=forward_from_user_id,
                        forward_from_chat_id=forward_from_chat_id,
                        has_media=has_media,
                        media_type=media_type,
                        media_file_id=media_file_id,
                        media_file_name=media_file_name,
                        caption=caption,
                        edit_date=edit_date,
                        has_mentions=has_mentions,
                        has_hashtags=has_hashtags,
                        entities=entities,
                        is_question=is_question,
                        is_command=is_command
                    )

                    db.add(message)
                    db.commit()
                    return message
                except Exception as e:
                    db.rollback()
                    logger.error(f"Ошибка при сохранении сообщения: {str(e)}")
                    return None

        return self._execute_with_retry(_store)

    def store_reaction(self, message_id, user_id, emoji):
        """Сохранение реакции на сообщение"""
        with self.Session() as db:
            try:
                # Проверяем, существует ли уже такая реакция
                existing_reaction = db.query(Reaction).filter(
                    Reaction.message_id == message_id,
                    Reaction.user_id == user_id,
                    Reaction.emoji == emoji
                ).first()

                if existing_reaction:
                    return existing_reaction

                # Создаем новую реакцию
                reaction = Reaction(
                    message_id=message_id,
                    user_id=user_id,
                    emoji=emoji
                )

                db.add(reaction)
                db.commit()
                return reaction
            except Exception as e:
                db.rollback()
                logger.error(f"Ошибка при сохранении реакции: {str(e)}")
                return None

    def get_messages_for_last_day(self, chat_id, hours=24, thread_id=None):
        """
        Получение сообщений за последние N часов из определенного чата

        Args:
            chat_id: ID чата
            hours: Количество часов для выборки
            thread_id: ID темы (если None, то выбираются сообщения из всех тем)

        Returns:
            list: Список сообщений
        """
        with self.Session() as db:
            try:
                start_time = datetime.now() - timedelta(hours=hours)
                query = db.query(Message).filter(
                    Message.chat_id == chat_id,
                    Message.date >= start_time,
                    Message.summarized == False
                )

                # Если указан ID темы, фильтруем сообщения только из этой темы
                if thread_id is not None:
                    query = query.filter(Message.message_thread_id == thread_id)

                messages = query.order_by(Message.date).all()
                return messages
            except Exception as e:
                logger.error(f"Ошибка при получении сообщений: {str(e)}")
                return []

    def get_all_chat_ids(self):
        """Получение списка всех чатов, из которых есть сообщения"""
        with self.Session() as db:
            try:
                result = db.query(Chat.chat_id).filter(Chat.is_active == True).all()
                return [r[0] for r in result]
            except Exception as e:
                logger.error(f"Ошибка при получении списка чатов: {str(e)}")
                return []

    def get_chats_with_enough_messages(self, min_messages=5, hours=24):
        """Получение чатов с достаточным количеством сообщений для анализа"""
        with self.Session() as db:
            try:
                start_time = datetime.now() - timedelta(hours=hours)

                # Запрос для подсчета новых сообщений в каждом чате
                result = db.query(
                    Message.chat_id,
                    func.count(Message.id).label('message_count')
                ).filter(
                    Message.date >= start_time,
                    Message.summarized == False
                ).group_by(Message.chat_id).having(
                    func.count(Message.id) >= min_messages
                ).all()

                # Получаем информацию о чатах
                chat_ids = [r[0] for r in result]
                chats = db.query(Chat).filter(Chat.chat_id.in_(chat_ids)).all()

                return chats
            except Exception as e:
                logger.error(f"Ошибка при получении чатов с сообщениями: {str(e)}")
                return []

    def get_chat_threads(self, chat_id, hours=24, min_messages=3):
        """
        Получение списка тем в чате с достаточным количеством сообщений

        Args:
            chat_id: ID чата
            hours: Количество часов для выборки
            min_messages: Минимальное количество сообщений в теме

        Returns:
            list: Список кортежей (thread_id, message_count)
        """
        with self.Session() as db:
            try:
                start_time = datetime.now() - timedelta(hours=hours)

                # Запрос для подсчета сообщений в каждой теме
                result = db.query(
                    Message.message_thread_id,
                    func.count(Message.id).label('message_count')
                ).filter(
                    Message.chat_id == chat_id,
                    Message.date >= start_time,
                    Message.summarized == False,
                    Message.message_thread_id != None  # Только сообщения из тем
                ).group_by(Message.message_thread_id).having(
                    func.count(Message.id) >= min_messages
                ).all()

                return result
            except Exception as e:
                logger.error(f"Ошибка при получении тем чата: {str(e)}")
                return []

    def mark_messages_as_summarized(self, messages):
        """Отметить сообщения как обработанные"""
        if not messages:
            return

        with self.Session() as db:
            try:
                for message in messages:
                    message.summarized = True
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Ошибка при обновлении сообщений: {str(e)}")

    def store_summary(self, chat_id, text, message_count):
        """Сохранение созданного саммари в базе данных"""
        with self.Session() as db:
            try:
                summary = Summary(
                    chat_id=chat_id,
                    text=text,
                    message_count=message_count,
                    created_at=datetime.now()
                )
                db.add(summary)
                db.commit()
                return summary
            except Exception as e:
                db.rollback()
                logger.error(f"Ошибка при сохранении саммари: {str(e)}")
                return None

    def mark_summary_as_published(self, summary_id):
        """Отметить саммари как опубликованное"""
        with self.Session() as db:
            try:
                summary = db.query(Summary).filter(Summary.id == summary_id).first()
                if summary:
                    summary.published = True
                    summary.published_at = datetime.now()
                    db.commit()
                    return True
                return False
            except Exception as e:
                db.rollback()
                logger.error(f"Ошибка при обновлении статуса саммари: {str(e)}")
                return False

    def get_chat_statistics(self, chat_id, days=7):
        """Получение статистики по чату за указанный период"""
        with self.Session() as db:
            try:
                start_time = datetime.now() - timedelta(days=days)

                # Общее количество сообщений
                total_messages = db.query(func.count(Message.id)).filter(
                    Message.chat_id == chat_id,
                    Message.date >= start_time
                ).scalar() or 0

                # Количество активных пользователей
                active_users = db.query(func.count(func.distinct(Message.user_id))).filter(
                    Message.chat_id == chat_id,
                    Message.date >= start_time
                ).scalar() or 0

                # Количество медиа-сообщений
                media_messages = db.query(func.count(Message.id)).filter(
                    Message.chat_id == chat_id,
                    Message.date >= start_time,
                    Message.has_media == True
                ).scalar() or 0

                # Количество вопросов
                questions = db.query(func.count(Message.id)).filter(
                    Message.chat_id == chat_id,
                    Message.date >= start_time,
                    Message.is_question == True
                ).scalar() or 0

                return {
                    "total_messages": total_messages,
                    "active_users": active_users,
                    "media_messages": media_messages,
                    "questions": questions,
                    "period_days": days
                }
            except Exception as e:
                logger.error(f"Ошибка при получении статистики чата: {str(e)}")
                return {}
