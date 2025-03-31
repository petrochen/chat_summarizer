from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Chat(Base):
    """Модель для хранения информации о чатах"""
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, unique=True, nullable=False)
    title = Column(String)
    type = Column(String)
    description = Column(String)
    member_count = Column(Integer)
    is_active = Column(Boolean, default=True)
    last_activity = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)

    messages = relationship("Message", back_populates="chat")
    summaries = relationship("Summary", back_populates="chat")

class User(Base):
    """Модель для хранения информации о пользователях"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    is_bot = Column(Boolean, default=False)
    language_code = Column(String)
    is_premium = Column(Boolean, default=False)
    last_seen = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)

    messages = relationship("Message", back_populates="user")
    reactions = relationship("Reaction", back_populates="user")

class Message(Base):
    """Модель для хранения сообщений"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, nullable=False)
    chat_id = Column(Integer, ForeignKey("chats.chat_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    text = Column(String)
    date = Column(DateTime, nullable=False)
    message_thread_id = Column(Integer)
    reply_to_message_id = Column(Integer)
    forward_from_user_id = Column(Integer)
    forward_from_chat_id = Column(Integer)
    has_media = Column(Boolean, default=False)
    media_type = Column(String)
    media_file_id = Column(String)
    media_file_name = Column(String)
    caption = Column(String)
    edit_date = Column(DateTime)
    has_mentions = Column(Boolean, default=False)
    has_hashtags = Column(Boolean, default=False)
    entities = Column(JSON)
    is_question = Column(Boolean, default=False)
    is_command = Column(Boolean, default=False)
    summarized = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

    chat = relationship("Chat", back_populates="messages")
    user = relationship("User", back_populates="messages")
    reactions = relationship("Reaction", back_populates="message")

class Reaction(Base):
    """Модель для хранения реакций на сообщения"""
    __tablename__ = "reactions"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    emoji = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    message = relationship("Message", back_populates="reactions")
    user = relationship("User", back_populates="reactions")

class Summary(Base):
    """Модель для хранения созданных саммари"""
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.chat_id"), nullable=False)
    text = Column(String, nullable=False)
    message_count = Column(Integer, nullable=False)
    published = Column(Boolean, default=False)
    published_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)

    chat = relationship("Chat", back_populates="summaries") 