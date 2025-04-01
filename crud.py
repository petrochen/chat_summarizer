import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import update, delete, select, and_, desc

from models import Chat, User, Message, Reaction, Summary
from database import SessionLocal # Using session factory

logger = logging.getLogger(__name__)

# --- Functions for working with chats --- 

def get_chat(db: Session, chat_id: int) -> Chat | None:
    """Gets a chat object by its chat_id."""
    return db.query(Chat).filter(Chat.chat_id == chat_id).first()

def get_or_create_chat(db: Session, chat_data: dict) -> Chat | None:
    """Gets an existing chat or creates a new one."""
    chat_id = chat_data.get('id')
    if not chat_id:
        logger.error("Cannot create/get chat without ID")
        return None
        
    chat = get_chat(db, chat_id)
    now = datetime.now()
    
    if chat:
        # Update existing chat
        update_stmt = (
            update(Chat)
            .where(Chat.chat_id == chat_id)
            .values(
                title=chat_data.get('title', chat.title),
                type=chat_data.get('type', chat.type),
                description=chat_data.get('description', chat.description),
                member_count=chat_data.get('member_count', chat.member_count),
                last_activity_ts=now,
                is_active=True, # Consider active if we received data about it
                raw_data=chat_data
            )
        )
        db.execute(update_stmt)
        db.commit()
        # Return updated object (may require .refresh(chat))
        return get_chat(db, chat_id) # Re-read to get updated data
    else:
        # Create new chat
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
             logger.error(f"IntegrityError when creating chat {chat_id}: {e}")
             db.rollback()
             return get_chat(db, chat_id) # Try to get it in case of race condition
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemy error when creating chat {chat_id}: {e}")
            db.rollback()
            return None

def deactivate_chat(db: Session, chat_id: int):
    update_stmt = update(Chat).where(Chat.chat_id == chat_id).values(is_active=False)
    db.execute(update_stmt)
    db.commit()
    logger.info(f"Chat {chat_id} deactivated")

# --- Functions for working with users ---

def get_user(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.user_id == user_id).first()

def get_or_create_user(db: Session, user_data: dict) -> User | None:
    user_id = user_data.get('id')
    if not user_id:
        logger.error("Cannot create/get user without ID")
        return None

    user = get_user(db, user_id)
    now = datetime.now()
    
    if user:
        # Update existing user
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
        # Remove None values to avoid overwriting existing values with None during update
        update_values = {k: v for k, v in update_values.items() if v is not None}
        
        update_stmt = update(User).where(User.user_id == user_id).values(**update_values)
        db.execute(update_stmt)
        db.commit()
        return get_user(db, user_id)
    else:
        # Create new user
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
             logger.error(f"IntegrityError when creating user {user_id}: {e}")
             db.rollback()
             return get_user(db, user_id)
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemy error when creating user {user_id}: {e}")
            db.rollback()
            return None

# --- Functions for working with messages ---

def get_message(db: Session, chat_id: int, message_id: int) -> Message | None:
    return db.query(Message).filter(Message.chat_id == chat_id, Message.message_id == message_id).first()

def get_message_by_internal_id(db: Session, internal_id: int) -> Message | None:
    return db.query(Message).filter(Message.internal_id == internal_id).first()

def create_or_update_topic_message(db: Session, chat_id: int, thread_id: int, topic_data: dict, user_data: dict, 
                                   date_ts: datetime, raw_data: dict = None) -> Message | None:
    """
    Creates or updates a topic message.
    
    Args:
        db: Database session
        chat_id: Chat ID
        thread_id: Topic ID (and message_id of the first message in the topic)
        topic_data: Topic data (from forum_topic_created)
        user_data: Data about the user who created the topic
        date_ts: Topic creation date
        raw_data: Raw message data if available
    
    Returns:
        Message: Created or updated topic message
    """
    # Check if topic message exists
    topic_message = get_message(db, chat_id, thread_id)
    
    # Get topic name
    topic_name = topic_data.get('name', 'Unknown topic')
    icon_color = topic_data.get('icon_color')
    topic_text = f"[Created topic: {topic_name}]"
    
    # If message exists, just update topic information
    if topic_message:
        # Update only if this message does not have text or has topic message format
        if not topic_message.text or topic_message.text.startswith('[Created topic:'):
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
                logger.info(f"Updated topic information for '{topic_name}' (ID: {thread_id}) in chat {chat_id}")
                return get_message_by_internal_id(db, topic_message.internal_id)
            except SQLAlchemyError as e:
                logger.error(f"SQLAlchemy error when updating topic {thread_id} in chat {chat_id}: {e}")
                db.rollback()
                return topic_message
        return topic_message
    
    # If message does not exist, create "virtual" message
    # First, ensure user exists
    user_id = user_data.get('id')
    user = get_or_create_user(db, user_data)
    if not user:
        logger.error(f"Failed to get/create user ({user_id}) for topic {thread_id}")
        return None
    
    # Create topic message
    new_topic_message = Message(
        message_id=thread_id,
        chat_id=chat_id,
        user_id=user_id,
        date_ts=date_ts,
        text=topic_text,
        message_thread_id=thread_id,  # Topic refers to itself
        has_media=False,
        raw_data=raw_data
    )
    
    db.add(new_topic_message)
    try:
        db.commit()
        db.refresh(new_topic_message)
        logger.info(f"Created virtual record for topic '{topic_name}' (ID: {thread_id}) in chat {chat_id}")
        return new_topic_message
    except IntegrityError as e:
        logger.warning(f"Topic {thread_id} in chat {chat_id}, probably already exists: {e}")
        db.rollback()
        return get_message(db, chat_id, thread_id)
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy error when creating topic {thread_id} in chat {chat_id}: {e}")
        db.rollback()
        return None

def create_message(db: Session, message_data: dict) -> Message | None:
    chat_data = message_data.get('chat')
    user_data = message_data.get('from')
    message_id = message_data.get('message_id')
    
    if not chat_data or not user_data or not message_id:
        logger.error(f"Not enough data to create message: {message_data.get('update_id')}")
        return None
        
    chat_id = chat_data.get('id')
    user_id = user_data.get('id')
    
    # Ensure chat and user exist
    chat = get_or_create_chat(db, chat_data)
    user = get_or_create_user(db, user_data)
    if not chat or not user:
        logger.error(f"Failed to get/create chat ({chat_id}) or user ({user_id}) for message {message_id}")
        return None

    # Handle reply
    reply_to_internal_id = None
    reply_data = message_data.get('reply_to_message')
    if reply_data:
        reply_msg_id = reply_data.get('message_id')
        reply_chat_id = reply_data.get('chat', {}).get('id')
        if reply_msg_id and reply_chat_id == chat_id: # Ensure reply is in the same chat
            original_msg = get_message(db, chat_id, reply_msg_id)
            
            # If this is a reply to a topic message and it doesn't exist in the database, create virtual record
            if not original_msg and reply_data.get('forum_topic_created') and message_data.get('is_topic_message'):
                topic_data = reply_data.get('forum_topic_created')
                reply_user_data = reply_data.get('from')
                reply_date_ts = datetime.fromtimestamp(reply_data.get('date'))
                
                # Create virtual message for topic
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
                logger.warning(f"Original message ({reply_msg_id}) not found for reply in message {message_id} chat {chat_id}")
    
    # Check if message is part of topic but not first message in topic
    # If yes and topic message is missing, try to restore it
    if message_data.get('is_topic_message') and message_data.get('message_thread_id'):
        thread_id = message_data.get('message_thread_id')
        
        # If message is not topic creator
        if message_id != thread_id:
            topic_message = get_message(db, chat_id, thread_id)
            
            # If topic information is missing and there's reply_to_message with forum_topic_created
            if not topic_message and reply_data and reply_data.get('forum_topic_created'):
                # This case should be handled above when processing reply
                pass
            # If we don't have created information but there's thread_id, create basic record
            elif not topic_message:
                # Create minimal record for topic
                default_topic_data = {'name': f'Topic #{thread_id}'}
                default_date_ts = datetime.fromtimestamp(message_data.get('date', int(datetime.now().timestamp())))
                
                create_or_update_topic_message(
                    db=db,
                    chat_id=chat_id,
                    thread_id=thread_id,
                    topic_data=default_topic_data,
                    user_data=user_data,  # Use current user as creator (though it may not be him)
                    date_ts=default_date_ts,
                    raw_data=None
                )
    
    # Handle forwarding
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
             logger.error(f"Error converting forward_date {forward_date_raw}: {e}")
    
    # Handle media
    has_media = False
    media_type = None
    media_file_id = None
    media_file_unique_id = None
    photo = message_data.get('photo')
    video = message_data.get('video')
    # ... add other media types ...
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
        # file_name = video.get('file_name') # Can add field to model

    # Create message object
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
        logger.warning(f"Message {message_id} in chat {chat_id}, probably already exists: {e}")
        db.rollback()
        return get_message(db, chat_id, message_id) # Return existing
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy error when creating message {message_id} in chat {chat_id}: {e}")
        db.rollback()
        return None

def update_message(db: Session, message_data: dict) -> Message | None:
    chat_data = message_data.get('chat')
    message_id = message_data.get('message_id')
    edit_date_raw = message_data.get('edit_date')

    if not chat_data or not message_id or not edit_date_raw:
        logger.error(f"Not enough data to update message: {message_data.get('update_id')}")
        return None

    chat_id = chat_data.get('id')
    existing_message = get_message(db, chat_id, message_id)

    if not existing_message:
        logger.warning(f"Attempting to update non-existing message: chat={chat_id}, msg={message_id}")
        # Can try to create it if this is edited_message
        if message_data.get('message'): # If this is full message from edited_message
             return create_message(db, message_data.get('message'))
        return None

    # Update only if edit_date is newer
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
                raw_data=message_data # Update raw_data
            )
        )
        db.execute(update_stmt)
        try:
            db.commit()
            return get_message_by_internal_id(db, existing_message.internal_id)
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemy error when updating message {message_id} in chat {chat_id}: {e}")
            db.rollback()
            return None
    else:
        # logger.debug(f"Skipping message update {message_id} in chat {chat_id}: edit_date not newer.")
        return existing_message

def get_unsummarized_messages(db: Session, chat_id: int, limit: int = 1000) -> list[Message]:
    """Gets last N unprocessed messages from chat."""
    return (
        db.query(Message)
        .filter(Message.chat_id == chat_id, Message.summarized == False)
        .order_by(Message.date_ts.asc()) # From old to new for summarization
        .limit(limit)
        .all()
    )

def mark_messages_as_summarized(db: Session, internal_ids: list[int]):
    """Marks messages as processed by their internal_id."""
    if not internal_ids:
        return
    update_stmt = (
        update(Message)
        .where(Message.internal_id.in_(internal_ids))
        .values(summarized=True)
    )
    db.execute(update_stmt)
    db.commit()

# --- Functions for working with reactions ---

def update_reactions(db: Session, reaction_data: dict):
    chat_data = reaction_data.get('chat')
    user_data = reaction_data.get('user')
    message_id = reaction_data.get('message_id')
    old_reactions_raw = reaction_data.get('old_reaction', [])
    new_reactions_raw = reaction_data.get('new_reaction', [])
    
    if not chat_data or not user_data or not message_id:
        logger.error(f"Not enough data to update reactions: {reaction_data}")
        return

    chat_id = chat_data.get('id')
    user_id = user_data.get('id')

    # Get internal ID of message
    message = get_message(db, chat_id, message_id)
    if not message:
        logger.warning(f"Message {message_id} in chat {chat_id} not found for updating reactions.")
        return
    internal_message_id = message.internal_id

    # Ensure user exists
    user = get_or_create_user(db, user_data)
    if not user:
        logger.error(f"Failed to get/create user ({user_id}) for updating reactions")
        return

    # Get old and new emojis
    old_emojis = set(r.get('emoji') for r in old_reactions_raw if r.get('type') == 'emoji')
    new_emojis = set(r.get('emoji') for r in new_reactions_raw if r.get('type') == 'emoji')
    
    emojis_to_remove = old_emojis - new_emojis
    emojis_to_add = new_emojis - old_emojis
    
    now = datetime.now()
    
    try:
        # Remove old reactions
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
            
        # Add new reactions
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
        logger.error(f"SQLAlchemy error when updating reactions for message {internal_message_id}, user {user_id}: {e}")
        db.rollback()

# --- Functions for working with summaries ---

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
        logger.error(f"SQLAlchemy error when creating summary for chat {chat_id}: {e}")
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

def get_latest_summary(db: Session, chat_id: int) -> Summary | None:
    """Gets the latest summary for a chat."""
    return (
        db.query(Summary)
        .filter(Summary.chat_id == chat_id)
        .order_by(Summary.created_ts.desc())
        .first()
    )

def get_chat_stats(db: Session, chat_id: int) -> dict:
    """Gets statistics for a chat."""
    # Check if chat exists
    chat = get_chat(db, chat_id)
    if not chat:
        return {
            "exists": False,
            "total_messages": 0,
            "active_users": 0,
            "media_count": 0,
            "questions_count": 0
        }
    
    # Get total messages
    total_messages = db.query(Message).filter(Message.chat_id == chat_id).count()
    
    # Get number of active users (those who wrote messages)
    active_users = db.query(Message.user_id).filter(Message.chat_id == chat_id).distinct().count()
    
    # Count media messages
    media_count = db.query(Message).filter(
        Message.chat_id == chat_id,
        Message.has_media == True
    ).count()
    
    # Count questions (message ends with ?)
    questions_count = db.query(Message).filter(
        Message.chat_id == chat_id,
        Message.text.like('%?')
    ).count()
    
    return {
        "exists": True,
        "total_messages": total_messages,
        "active_users": active_users,
        "media_count": media_count,
        "questions_count": questions_count
    }

def get_messages_by_date_range(db: Session, chat_id: int, 
                              start_date: datetime = None, 
                              end_date: datetime = None,
                              limit: int = 1000,
                              thread_id: int = None) -> list[Message]:
    """
    Gets messages from a chat within a specific date range.
    
    Args:
        db: Database session
        chat_id: Chat ID
        start_date: Start date for message range (inclusive)
        end_date: End date for message range (inclusive)
        limit: Maximum number of messages to return
        thread_id: Optional topic ID to filter messages
    
    Returns:
        List of messages
    """
    query = db.query(Message).filter(Message.chat_id == chat_id)
    
    # Apply date filters if specified
    if start_date:
        query = query.filter(Message.date_ts >= start_date)
    if end_date:
        query = query.filter(Message.date_ts <= end_date)
    
    # Filter by topic if specified
    if thread_id:
        query = query.filter(Message.message_thread_id == thread_id)
    
    # Order by date (ascending)
    query = query.order_by(Message.date_ts.asc())
    
    # Apply limit
    if limit > 0:
        query = query.limit(limit)
    
    return query.all()

def get_recent_messages(db: Session, chat_id: int, days: int = 1, limit: int = 1000, thread_id: int = None) -> list[Message]:
    """
    Gets messages from a chat from the last N days.
    
    Args:
        db: Database session
        chat_id: Chat ID
        days: Number of days to look back
        limit: Maximum number of messages to return
        thread_id: Optional topic ID to filter messages
    
    Returns:
        List of messages
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    return get_messages_by_date_range(
        db=db,
        chat_id=chat_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        thread_id=thread_id
    )

def get_messages_reactions(db: Session, message_ids: list[int]) -> dict:
    """
    Gets all reactions for a list of messages by their internal IDs.
    
    Returns a dictionary where:
    - Keys are message internal IDs
    - Values are dictionaries with emoji as keys and count as values
    """
    if not message_ids:
        return {}
    
    # Get all reactions for these messages
    reactions = db.query(Reaction).filter(Reaction.message_internal_id.in_(message_ids)).all()
    
    results = {}
    for reaction in reactions:
        # Initialize message entry if it doesn't exist
        if reaction.message_internal_id not in results:
            results[reaction.message_internal_id] = {}
        
        # Initialize emoji count if it doesn't exist
        if reaction.emoji not in results[reaction.message_internal_id]:
            results[reaction.message_internal_id][reaction.emoji] = 0
        
        # Increment count
        results[reaction.message_internal_id][reaction.emoji] += 1
    
    return results

# --- Contextual database session management ---

def get_db():
    """
    Creates and returns a new SQLAlchemy session.
    Use this in a FastAPI dependency.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ChatDatabase:
    """
    Database context manager for working with chat data.
    
    Example usage:
    ```
    with ChatDatabase() as db:
        db.get_or_create_chat(chat_data)
    ```
    """
    
    def __init__(self):
        self.db = None
    
    def __enter__(self):
        self.db = SessionLocal()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()
    
    # --- Chat methods ---
    def get_chat(self, chat_id: int) -> Chat | None:
        return get_chat(self.db, chat_id)
    
    def get_or_create_chat(self, chat_data: dict) -> Chat | None:
        return get_or_create_chat(self.db, chat_data)
    
    def deactivate_chat(self, chat_id: int) -> None:
        return deactivate_chat(self.db, chat_id)
    
    # --- User methods ---
    def get_user(self, user_id: int) -> User | None:
        return get_user(self.db, user_id)
    
    def get_or_create_user(self, user_data: dict) -> User | None:
        return get_or_create_user(self.db, user_data)
    
    # --- Message methods ---
    def get_message(self, chat_id: int, message_id: int) -> Message | None:
        return get_message(self.db, chat_id, message_id)
    
    def create_message(self, message_data: dict) -> Message | None:
        return create_message(self.db, message_data)
    
    def update_message(self, message_data: dict) -> Message | None:
        return update_message(self.db, message_data)
    
    def get_message_by_internal_id(self, internal_id: int) -> Message | None:
        return get_message_by_internal_id(self.db, internal_id)
    
    def get_unsummarized_messages(self, chat_id: int, limit: int = 1000) -> list[Message]:
        return get_unsummarized_messages(self.db, chat_id, limit)
    
    def mark_messages_as_summarized(self, internal_ids: list[int]) -> None:
        return mark_messages_as_summarized(self.db, internal_ids)
    
    def get_recent_messages(self, chat_id: int, days: int = 1, limit: int = 1000, thread_id: int = None) -> list[Message]:
        return get_recent_messages(self.db, chat_id, days, limit, thread_id)
    
    # --- Reaction methods ---
    def update_reactions(self, reaction_data: dict) -> None:
        return update_reactions(self.db, reaction_data)
    
    def get_messages_reactions(self, message_ids: list[int]) -> dict:
        return get_messages_reactions(self.db, message_ids)
    
    # --- Summary methods ---
    def create_summary(self, chat_id: int, text: str, message_ids: list[int]) -> Summary | None:
        return create_summary(self.db, chat_id, text, message_ids)
    
    def get_latest_summary(self, chat_id: int) -> Summary | None:
        return get_latest_summary(self.db, chat_id)
    
    # --- Stats methods ---
    def get_chat_stats(self, chat_id: int) -> dict:
        return get_chat_stats(self.db, chat_id) 