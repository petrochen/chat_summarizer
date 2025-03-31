import datetime
from typing import Optional
from sqlalchemy import (Column, Integer, String, Boolean, DateTime, 
                        ForeignKey, JSON, Text, BigInteger, UniqueConstraint)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from database import Base

# Используем новый синтаксис Mapped для типизации

class Chat(Base):
    __tablename__ = "chats"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True) # Telegram ID могут быть большими
    type: Mapped[str] = mapped_column(String(50), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_seen_ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    last_activity_ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Отношения
    messages: Mapped[list["Message"]] = relationship(back_populates="chat", foreign_keys="[Message.chat_id]")
    summaries: Mapped[list["Summary"]] = relationship(back_populates="chat")

    def __repr__(self):
        return f"<Chat(chat_id={self.chat_id}, title='{self.title}')>"

class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True) # Telegram ID могут быть большими
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    is_premium: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    first_seen_ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    last_seen_ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Отношения
    messages: Mapped[list["Message"]] = relationship(back_populates="user", foreign_keys="[Message.user_id]")
    reactions: Mapped[list["Reaction"]] = relationship(back_populates="user")

    def __repr__(self):
        return f"<User(user_id={self.user_id}, username='{self.username}')>"

class Message(Base):
    __tablename__ = "messages"

    internal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.chat_id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    date_ts: Mapped[datetime.datetime] = mapped_column(DateTime)
    edit_date_ts: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    
    reply_to_internal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("messages.internal_id"), nullable=True)
    
    forward_from_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    forward_from_chat_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("chats.chat_id"), nullable=True)
    forward_date_ts: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    
    message_thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    
    media_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    media_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    media_file_unique_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    has_media: Mapped[bool] = mapped_column(Boolean, default=False)

    # Доп флаги для анализа (можно убрать, если анализ будет внешним)
    # is_question: Mapped[bool] = mapped_column(Boolean, default=False)
    # is_command: Mapped[bool] = mapped_column(Boolean, default=False)
    summarized: Mapped[bool] = mapped_column(Boolean, default=False, index=True) # Индекс для поиска необработанных
    
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Отношения
    chat: Mapped["Chat"] = relationship(back_populates="messages", foreign_keys=[chat_id])
    user: Mapped["User"] = relationship(back_populates="messages", foreign_keys=[user_id])
    forward_from_user: Mapped["User | None"] = relationship("User", foreign_keys=[forward_from_user_id])
    forward_from_chat: Mapped["Chat | None"] = relationship("Chat", foreign_keys=[forward_from_chat_id])
    reply_to_message: Mapped[Optional["Message"]] = relationship(remote_side=[internal_id])
    reactions: Mapped[list["Reaction"]] = relationship(back_populates="message", cascade="all, delete-orphan")

    # Уникальный индекс для message_id в рамках chat_id
    __table_args__ = (UniqueConstraint('chat_id', 'message_id', name='uq_chat_message'),)

    def __repr__(self):
        preview = (self.text or self.caption or f"[{self.media_type or 'media'}]")[:30]
        return f"<Message(id={self.internal_id}, msg_id={self.message_id}, chat={self.chat_id}, text='{preview}...')>"

class Reaction(Base):
    __tablename__ = "reactions"

    internal_message_id: Mapped[int] = mapped_column(Integer, ForeignKey("messages.internal_id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), primary_key=True)
    emoji: Mapped[str] = mapped_column(String(50), primary_key=True) # Эмодзи или custom_emoji_id
    added_ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())

    # Отношения
    message: Mapped["Message"] = relationship(back_populates="reactions")
    user: Mapped["User"] = relationship(back_populates="reactions")

    def __repr__(self):
        return f"<Reaction(msg={self.internal_message_id}, user={self.user_id}, emoji='{self.emoji}')>"

class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.chat_id"))
    text: Mapped[str] = mapped_column(Text)
    message_count: Mapped[int] = mapped_column(Integer)
    first_message_internal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("messages.internal_id"), nullable=True)
    last_message_internal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("messages.internal_id"), nullable=True)
    created_ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    published_ts: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False)

    # Отношения
    chat: Mapped["Chat"] = relationship(back_populates="summaries")
    # Можно добавить связи с first/last message, если нужно
    # first_message: Mapped["Message" | None] = relationship(foreign_keys=[first_message_internal_id])
    # last_message: Mapped["Message" | None] = relationship(foreign_keys=[last_message_internal_id])

    def __repr__(self):
        return f"<Summary(id={self.id}, chat={self.chat_id}, messages={self.message_count})>"

# Опционально: Таблица для сырых обновлений
# class RawUpdate(Base):
#     __tablename__ = "raw_updates"
#     update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
#     received_ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
#     update_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
#     raw_data: Mapped[dict] = mapped_column(JSON) 