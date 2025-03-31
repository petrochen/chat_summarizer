import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import update, delete, select, and_, desc

from models import Chat, User, Message, Reaction, Summary
from database import SessionLocal # Используем фабрику сессий

logger = logging.getLogger(__name__)

# --- Функции для работы с чатами --- 

def get_chat(db: Session, chat_id: int) -> Chat | None:
    """Получает объект чата по его chat_id."""
    return db.query(Chat).filter(Chat.chat_id == chat_id).first()

def get_or_create_chat(db: Session, chat_data: dict) -> Chat | None:
    """Получает существующий чат или создает новый."""
    chat_id = chat_data.get('id')
    if not chat_id:
        logger.error("Невозможно создать/получить чат без ID")
        return None
        
    chat = get_chat(db, chat_id)
    now = datetime.now()
    
    if chat:
        # Обновляем существующий чат
        update_stmt = (
            update(Chat)
            .where(Chat.chat_id == chat_id)
            .values(
                title=chat_data.get('title', chat.title),
                type=chat_data.get('type', chat.type),
                description=chat_data.get('description', chat.description),
                member_count=chat_data.get('member_count', chat.member_count),
                last_activity_ts=now,
                is_active=True, # Считаем активным, если получили о нем данные
                raw_data=chat_data
            )
        )
        db.execute(update_stmt)
        db.commit()
        # Возвращаем обновленный объект (может потребоваться .refresh(chat))
        return get_chat(db, chat_id) # Перечитываем, чтобы получить обновленные данные
    else:
        # Создаем новый чат
        chat = Chat(
            chat_id=chat_id,
            title=chat_data.get('title'),
            type=chat_data.get('type'),
            description=chat_data.get('description'),
            member_count=chat_data.get('member_count'),
            first_seen_ts=now,
            last_activity_ts=now,
            is_active=True,
            raw_data=chat_data
        )
        db.add(chat)
        try:
            db.commit()
            db.refresh(chat)
            return chat
        except IntegrityError as e:
             logger.error(f"Ошибка IntegrityError при создании чата {chat_id}: {e}")
             db.rollback()
             return get_chat(db, chat_id) # Попробуем получить, вдруг гонка состояний
        except SQLAlchemyError as e:
            logger.error(f"Ошибка SQLAlchemy при создании чата {chat_id}: {e}")
            db.rollback()
            return None

def deactivate_chat(db: Session, chat_id: int):
    update_stmt = update(Chat).where(Chat.chat_id == chat_id).values(is_active=False)
    db.execute(update_stmt)
    db.commit()
    logger.info(f"Чат {chat_id} деактивирован")

# --- Функции для работы с пользователями ---

def get_user(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.user_id == user_id).first()

def get_or_create_user(db: Session, user_data: dict) -> User | None:
    user_id = user_data.get('id')
    if not user_id:
        logger.error("Невозможно создать/получить пользователя без ID")
        return None

    user = get_user(db, user_id)
    now = datetime.now()
    
    if user:
        # Обновляем существующего пользователя
        update_values = {
            "username": user_data.get('username', user.username),
            "first_name": user_data.get('first_name', user.first_name),
            "last_name": user_data.get('last_name', user.last_name),
            "is_bot": user_data.get('is_bot', user.is_bot),
            "is_premium": user_data.get('is_premium', user.is_premium),
            "language_code": user_data.get('language_code', user.language_code),
            "last_seen_ts": now,
            "raw_data": user_data
        }
        # Удаляем None значения, чтобы не перезаписывать существующие значения на None при обновлении
        update_values = {k: v for k, v in update_values.items() if v is not None}
        
        update_stmt = update(User).where(User.user_id == user_id).values(**update_values)
        db.execute(update_stmt)
        db.commit()
        return get_user(db, user_id)
    else:
        # Создаем нового пользователя
        user = User(
            user_id=user_id,
            username=user_data.get('username'),
            first_name=user_data.get('first_name'),
            last_name=user_data.get('last_name'),
            is_bot=user_data.get('is_bot', False),
            is_premium=user_data.get('is_premium'),
            language_code=user_data.get('language_code'),
            first_seen_ts=now,
            last_seen_ts=now,
            raw_data=user_data
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
            return user
        except IntegrityError as e:
             logger.error(f"Ошибка IntegrityError при создании пользователя {user_id}: {e}")
             db.rollback()
             return get_user(db, user_id)
        except SQLAlchemyError as e:
            logger.error(f"Ошибка SQLAlchemy при создании пользователя {user_id}: {e}")
            db.rollback()
            return None

# --- Функции для работы с сообщениями ---

def get_message(db: Session, chat_id: int, message_id: int) -> Message | None:
    return db.query(Message).filter(Message.chat_id == chat_id, Message.message_id == message_id).first()

def get_message_by_internal_id(db: Session, internal_id: int) -> Message | None:
    return db.query(Message).filter(Message.internal_id == internal_id).first()

def create_or_update_topic_message(db: Session, chat_id: int, thread_id: int, topic_data: dict, user_data: dict, 
                                   date_ts: datetime, raw_data: dict = None) -> Message | None:
    """
    Создает или обновляет сообщение-создатель топика.
    
    Args:
        db: Сессия базы данных
        chat_id: ID чата
        thread_id: ID топика (и message_id первого сообщения в топике)
        topic_data: Данные о топике (из forum_topic_created)
        user_data: Данные о пользователе, создавшем топик
        date_ts: Дата создания топика
        raw_data: Сырые данные сообщения, если доступны
    
    Returns:
        Message: Созданное или обновленное сообщение-топик
    """
    # Проверяем, существует ли сообщение-создатель топика
    topic_message = get_message(db, chat_id, thread_id)
    
    # Получаем имя топика
    topic_name = topic_data.get('name', 'Неизвестный топик')
    icon_color = topic_data.get('icon_color')
    topic_text = f"[Создан топик: {topic_name}]"
    
    # Если сообщение существует, просто обновляем информацию о топике
    if topic_message:
        # Обновляем только если это сообщение не имеет текста или имеет формат сообщения топика
        if not topic_message.text or topic_message.text.startswith('[Создан топик:'):
            update_stmt = (
                update(Message)
                .where(Message.internal_id == topic_message.internal_id)
                .values(
                    text=topic_text,
                    message_thread_id=thread_id
                )
            )
            if raw_data and not topic_message.raw_data:
                update_stmt = update_stmt.values(raw_data=raw_data)
            
            db.execute(update_stmt)
            try:
                db.commit()
                logger.info(f"Обновлена информация о топике '{topic_name}' (ID: {thread_id}) в чате {chat_id}")
                return get_message_by_internal_id(db, topic_message.internal_id)
            except SQLAlchemyError as e:
                logger.error(f"Ошибка SQLAlchemy при обновлении топика {thread_id} в чате {chat_id}: {e}")
                db.rollback()
                return topic_message
        return topic_message
    
    # Если сообщение не существует, создаем "виртуальное" сообщение
    # Сначала убедимся, что пользователь существует
    user_id = user_data.get('id')
    user = get_or_create_user(db, user_data)
    if not user:
        logger.error(f"Не удалось получить/создать пользователя ({user_id}) для топика {thread_id}")
        return None
    
    # Создаем сообщение-топик
    new_topic_message = Message(
        message_id=thread_id,
        chat_id=chat_id,
        user_id=user_id,
        date_ts=date_ts,
        text=topic_text,
        message_thread_id=thread_id,  # Топик ссылается сам на себя
        has_media=False,
        raw_data=raw_data
    )
    
    db.add(new_topic_message)
    try:
        db.commit()
        db.refresh(new_topic_message)
        logger.info(f"Создана виртуальная запись для топика '{topic_name}' (ID: {thread_id}) в чате {chat_id}")
        return new_topic_message
    except IntegrityError as e:
        logger.warning(f"Топик {thread_id} в чате {chat_id}, вероятно, уже существует: {e}")
        db.rollback()
        return get_message(db, chat_id, thread_id)
    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при создании топика {thread_id} в чате {chat_id}: {e}")
        db.rollback()
        return None

def create_message(db: Session, message_data: dict) -> Message | None:
    chat_data = message_data.get('chat')
    user_data = message_data.get('from')
    message_id = message_data.get('message_id')
    
    if not chat_data or not user_data or not message_id:
        logger.error(f"Недостаточно данных для создания сообщения: {message_data.get('update_id')}")
        return None
        
    chat_id = chat_data.get('id')
    user_id = user_data.get('id')
    
    # Гарантируем наличие чата и пользователя
    chat = get_or_create_chat(db, chat_data)
    user = get_or_create_user(db, user_data)
    if not chat or not user:
        logger.error(f"Не удалось получить/создать чат ({chat_id}) или пользователя ({user_id}) для сообщения {message_id}")
        return None

    # Обработка ответа
    reply_to_internal_id = None
    reply_data = message_data.get('reply_to_message')
    if reply_data:
        reply_msg_id = reply_data.get('message_id')
        reply_chat_id = reply_data.get('chat', {}).get('id')
        if reply_msg_id and reply_chat_id == chat_id: # Убеждаемся, что ответ в том же чате
            original_msg = get_message(db, chat_id, reply_msg_id)
            
            # Если это ответ на сообщение-создатель топика, и его нет в базе, создаем виртуальную запись
            if not original_msg and reply_data.get('forum_topic_created') and message_data.get('is_topic_message'):
                topic_data = reply_data.get('forum_topic_created')
                reply_user_data = reply_data.get('from')
                reply_date_ts = datetime.fromtimestamp(reply_data.get('date'))
                
                # Создаем виртуальное сообщение для топика
                original_msg = create_or_update_topic_message(
                    db=db, 
                    chat_id=chat_id, 
                    thread_id=reply_msg_id, 
                    topic_data=topic_data, 
                    user_data=reply_user_data, 
                    date_ts=reply_date_ts, 
                    raw_data=reply_data
                )
            
            if original_msg:
                reply_to_internal_id = original_msg.internal_id
            else:
                logger.warning(f"Не найдено оригинальное сообщение ({reply_msg_id}) для ответа в сообщении {message_id} чата {chat_id}")
    
    # Проверяем, является ли сообщение частью топика, но не первым сообщением в топике
    # Если да и сообщение-создатель топика отсутствует, пытаемся его восстановить
    if message_data.get('is_topic_message') and message_data.get('message_thread_id'):
        thread_id = message_data.get('message_thread_id')
        
        # Если сообщение не является само создателем топика
        if message_id != thread_id:
            topic_message = get_message(db, chat_id, thread_id)
            
            # Если информация о топике отсутствует и есть reply_to_message с forum_topic_created
            if not topic_message and reply_data and reply_data.get('forum_topic_created'):
                # Используем информацию из reply_to_message для создания сообщения-топика
                # (этот случай должен быть обработан выше при обработке reply)
                pass
            # Если у нас нет информации о created, но есть thread_id, создаем базовую запись
            elif not topic_message:
                # Создаем минимальную запись о топике
                default_topic_data = {'name': f'Топик #{thread_id}'}
                default_date_ts = datetime.fromtimestamp(message_data.get('date', int(datetime.now().timestamp())))
                
                create_or_update_topic_message(
                    db=db,
                    chat_id=chat_id,
                    thread_id=thread_id,
                    topic_data=default_topic_data,
                    user_data=user_data,  # Используем текущего пользователя в качестве создателя (хотя это может быть не он)
                    date_ts=default_date_ts,
                    raw_data=None
                )
    
    # Обработка пересылки
    forward_from_user_id = None
    forward_from_chat_id = None
    forward_date_ts = None
    forward_user_data = message_data.get('forward_from')
    forward_chat_data = message_data.get('forward_from_chat')
    forward_date_raw = message_data.get('forward_date')
    if forward_user_data:
        fw_user = get_or_create_user(db, forward_user_data)
        if fw_user:
            forward_from_user_id = fw_user.user_id
    if forward_chat_data:
        fw_chat = get_or_create_chat(db, forward_chat_data)
        if fw_chat:
            forward_from_chat_id = fw_chat.chat_id
    if forward_date_raw:
        try:
            forward_date_ts = datetime.fromtimestamp(forward_date_raw)
        except Exception as e:
             logger.error(f"Ошибка преобразования forward_date {forward_date_raw}: {e}")
    
    # Обработка медиа
    has_media = False
    media_type = None
    media_file_id = None
    media_file_unique_id = None
    photo = message_data.get('photo')
    video = message_data.get('video')
    # ... добавить другие типы медиа ...
    if photo:
        has_media = True
        media_type = "photo"
        if isinstance(photo, list) and photo:
            media_file_id = photo[-1].get('file_id')
            media_file_unique_id = photo[-1].get('file_unique_id')
    elif video:
        has_media = True
        media_type = "video"
        media_file_id = video.get('file_id')
        media_file_unique_id = video.get('file_unique_id')
        # file_name = video.get('file_name') # Можно добавить поле в модель

    # Создаем объект сообщения
    new_message = Message(
        message_id=message_id,
        chat_id=chat_id,
        user_id=user_id,
        date_ts=datetime.fromtimestamp(message_data.get('date')),
        edit_date_ts=datetime.fromtimestamp(message_data.get('edit_date')) if message_data.get('edit_date') else None,
        text=message_data.get('text'),
        caption=message_data.get('caption'),
        entities=message_data.get('entities'),
        reply_to_internal_id=reply_to_internal_id,
        forward_from_user_id=forward_from_user_id,
        forward_from_chat_id=forward_from_chat_id,
        forward_date_ts=forward_date_ts,
        message_thread_id=message_data.get('message_thread_id'),
        has_media=has_media,
        media_type=media_type,
        media_file_id=media_file_id,
        media_file_unique_id=media_file_unique_id,
        raw_data=message_data
    )
    
    db.add(new_message)
    try:
        db.commit()
        db.refresh(new_message)
        return new_message
    except IntegrityError as e:
        logger.warning(f"Сообщение {message_id} в чате {chat_id}, вероятно, уже существует: {e}")
        db.rollback()
        return get_message(db, chat_id, message_id) # Возвращаем существующее
    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при создании сообщения {message_id} в чате {chat_id}: {e}")
        db.rollback()
        return None

def update_message(db: Session, message_data: dict) -> Message | None:
    chat_data = message_data.get('chat')
    message_id = message_data.get('message_id')
    edit_date_raw = message_data.get('edit_date')

    if not chat_data or not message_id or not edit_date_raw:
        logger.error(f"Недостаточно данных для обновления сообщения: {message_data.get('update_id')}")
        return None

    chat_id = chat_data.get('id')
    existing_message = get_message(db, chat_id, message_id)

    if not existing_message:
        logger.warning(f"Попытка обновить несуществующее сообщение: chat={chat_id}, msg={message_id}")
        # Можно попробовать создать его, если это edited_message
        if message_data.get('message'): # Если это полное сообщение из edited_message
             return create_message(db, message_data.get('message'))
        return None

    # Обновляем только если дата редактирования новее
    edit_date_ts = datetime.fromtimestamp(edit_date_raw)
    if not existing_message.edit_date_ts or edit_date_ts > existing_message.edit_date_ts:
        update_stmt = (
            update(Message)
            .where(Message.internal_id == existing_message.internal_id)
            .values(
                text=message_data.get('text', existing_message.text),
                caption=message_data.get('caption', existing_message.caption),
                entities=message_data.get('entities', existing_message.entities),
                edit_date_ts=edit_date_ts,
                raw_data=message_data # Обновляем raw_data
            )
        )
        db.execute(update_stmt)
        try:
            db.commit()
            return get_message_by_internal_id(db, existing_message.internal_id)
        except SQLAlchemyError as e:
            logger.error(f"Ошибка SQLAlchemy при обновлении сообщения {message_id} в чате {chat_id}: {e}")
            db.rollback()
            return None
    else:
        # logger.debug(f"Пропуск обновления сообщения {message_id} в чате {chat_id}: edit_date не новее.")
        return existing_message

def get_unsummarized_messages(db: Session, chat_id: int, limit: int = 1000) -> list[Message]:
    """Получает последние N необработанных сообщений из чата."""
    return (
        db.query(Message)
        .filter(Message.chat_id == chat_id, Message.summarized == False)
        .order_by(Message.date_ts.asc()) # От старых к новым для саммари
        .limit(limit)
        .all()
    )

def mark_messages_as_summarized(db: Session, internal_ids: list[int]):
    """Отмечает сообщения как обработанные по их internal_id."""
    if not internal_ids:
        return
    update_stmt = (
        update(Message)
        .where(Message.internal_id.in_(internal_ids))
        .values(summarized=True)
    )
    db.execute(update_stmt)
    db.commit()

# --- Функции для работы с реакциями ---

def update_reactions(db: Session, reaction_data: dict):
    chat_data = reaction_data.get('chat')
    user_data = reaction_data.get('user')
    message_id = reaction_data.get('message_id')
    old_reactions_raw = reaction_data.get('old_reaction', [])
    new_reactions_raw = reaction_data.get('new_reaction', [])
    
    if not chat_data or not user_data or not message_id:
        logger.error(f"Недостаточно данных для обновления реакций: {reaction_data}")
        return

    chat_id = chat_data.get('id')
    user_id = user_data.get('id')

    # Получаем внутренний ID сообщения
    message = get_message(db, chat_id, message_id)
    if not message:
        logger.warning(f"Сообщение {message_id} в чате {chat_id} не найдено для обновления реакций.")
        return
    internal_message_id = message.internal_id

    # Гарантируем наличие пользователя
    user = get_or_create_user(db, user_data)
    if not user:
        logger.error(f"Не удалось получить/создать пользователя ({user_id}) для обновления реакций")
        return

    # Получаем старые и новые эмодзи
    old_emojis = set(r.get('emoji') for r in old_reactions_raw if r.get('type') == 'emoji')
    new_emojis = set(r.get('emoji') for r in new_reactions_raw if r.get('type') == 'emoji')
    
    emojis_to_remove = old_emojis - new_emojis
    emojis_to_add = new_emojis - old_emojis
    
    now = datetime.now()
    
    try:
        # Удаляем старые реакции
        if emojis_to_remove:
            delete_stmt = (
                delete(Reaction)
                .where(
                    Reaction.internal_message_id == internal_message_id,
                    Reaction.user_id == user_id,
                    Reaction.emoji.in_(emojis_to_remove)
                )
            )
            db.execute(delete_stmt)
            
        # Добавляем новые реакции
        if emojis_to_add:
            new_reaction_objects = [
                Reaction(
                    internal_message_id=internal_message_id,
                    user_id=user_id,
                    emoji=emoji,
                    added_ts=now
                ) for emoji in emojis_to_add
            ]
            db.add_all(new_reaction_objects)
            
        db.commit()
    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при обновлении реакций для сообщения {internal_message_id}, пользователя {user_id}: {e}")
        db.rollback()

# --- Функции для работы с саммари ---

def create_summary(
    db: Session, 
    chat_id: int, 
    text: str, 
    message_count: int, 
    first_message_internal_id: int | None = None,
    last_message_internal_id: int | None = None
) -> Summary | None:
    summary = Summary(
        chat_id=chat_id,
        text=text,
        message_count=message_count,
        first_message_internal_id=first_message_internal_id,
        last_message_internal_id=last_message_internal_id,
        created_ts=datetime.now()
    )
    db.add(summary)
    try:
        db.commit()
        db.refresh(summary)
        return summary
    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при создании саммари для чата {chat_id}: {e}")
        db.rollback()
        return None

def mark_summary_as_published(db: Session, summary_id: int):
    update_stmt = (
        update(Summary)
        .where(Summary.id == summary_id)
        .values(published=True, published_ts=datetime.now())
    )
    db.execute(update_stmt)
    db.commit() 