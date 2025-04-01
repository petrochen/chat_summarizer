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

from database import SessionLocal, get_db # Import session and dependency
import crud # Import CRUD functions
import models # Import models (for type hinting)
# If summarization is needed, uncomment:
# from yandex_gpt_summarizer import YandexGPTSummarizer
from config import BOT_TOKEN, CHANNEL_ID, MIN_MESSAGES, SUMMARY_TIME # Add SUMMARY_TIME

logger = logging.getLogger(__name__)

# --- Helper function to get session --- 
def get_session() -> Session:
    """Creates and returns a new SQLAlchemy session."""
    return SessionLocal()

class ChatSummarizerBot:
    def __init__(self, token, channel_id):
        self.token = token
        self.channel_id = channel_id
        # self.summarizer = YandexGPTSummarizer() # If summarization is needed
        self.app = Application.builder().token(token).build()
        self.job_queue: JobQueue = self.app.job_queue
        
        self.register_handlers()
        # self.schedule_daily_summary() # If automatic summarization is needed
            
    def register_handlers(self):
        """Register handlers"""
        # Commands
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("summarize", self.manual_summarize))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        
        # Messages and events
        self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.new_member_handler))
        self.app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, self.left_member_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.store_message_handler))
        self.app.add_handler(MessageHandler(filters.CAPTION & (~filters.COMMAND), self.store_message_handler))
        # Using common ATTACHMENT filter for all attachments
        # media_filters: BaseFilter = filters.PHOTO | filters.VIDEO | filters.DOCUMENT | filters.AUDIO | filters.STICKER | filters.ANIMATION
        # self.app.add_handler(MessageHandler(media_filters, self.store_message_handler))
        # Or add separate handlers for each type if ATTACHMENT is not suitable:
        self.app.add_handler(MessageHandler(filters.ATTACHMENT, self.store_message_handler))
        # self.app.add_handler(MessageHandler(filters.PHOTO, self.store_message_handler))
        # self.app.add_handler(MessageHandler(filters.VIDEO, self.store_message_handler))
        # self.app.add_handler(MessageHandler(filters.AUDIO, self.store_message_handler))
        # self.app.add_handler(MessageHandler(filters.Sticker(), self.store_message_handler)) # Sticker may be a class
        # self.app.add_handler(MessageHandler(filters.ANIMATION, self.store_message_handler))
        
        # Update type filters
        # Replace with existing method or create a stub
        # self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.new_members_handler))
        
        # Tracking message edits - using the correct filter in version 22.0
        self.app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE, self.store_edited_message_handler))
        
        # Tracking message reactions - using special reaction handler
        self.app.add_handler(MessageReactionHandler(callback=self.reaction_handler))
        
        # Handler for bot status changes in chat
        self.app.add_handler(ChatMemberHandler(self.track_chats_handler, ChatMemberHandler.MY_CHAT_MEMBER))
    
    # --- Command handlers ---
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Hi! I'm a chat summary bot. Add me to a chat.")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Commands: /start, /help, /summarize [optional days], /stats")
        
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Shows chat statistics."""
        if not update.effective_chat: return
        chat_id = update.effective_chat.id
        # TODO: Implement statistics collection and display from DB
        await update.message.reply_text(f"Statistics for chat {chat_id} not implemented yet.")

    async def manual_summarize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create summary manually."""
        if not update.effective_chat or not update.effective_user: return
        
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        # Permissions check (optional, can be allowed for all)
        # member = await context.bot.get_chat_member(chat_id, user_id)
        # if member.status not in ["administrator", "creator"]:
        #     await update.message.reply_text("Only administrators can create summaries.")
        #     return
            
        days = 1 # Default: 1 day
        if context.args:
            try:
                days = int(context.args[0])
                if days <= 0:
                    await update.message.reply_text("Number of days must be positive.")
                    return
            except ValueError:
                await update.message.reply_text("Invalid number of days format.")
                return

        await update.message.reply_text(f"Creating summary for the last {days} days...")
        await self.create_and_send_summary_job(context, chat_id=chat_id, days=days)

    # --- Message and event handlers ---
    
    def _get_data_from_update(self, update: Update):
        """Extracts basic data (chat, user, message) from update."""
        message = update.effective_message
        chat = update.effective_chat
        user = update.effective_user
        return message, chat, user

    async def store_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes and stores a new message."""
        message, chat, user = self._get_data_from_update(update)
        if not message or not chat or not user:
            # logger.debug("Skipping update without message/chat/user")
            return
        
        # Convert Telegram objects to dictionaries
        message_dict = message.to_dict()
        # Add chat and from inside message dictionary for create_message
        message_dict['chat'] = chat.to_dict()
        message_dict['from'] = user.to_dict()
        
        db = get_session()
        try:
            created_msg = crud.create_message(db, message_dict)
            if created_msg:
                # logger.debug(f"Message {created_msg.internal_id} saved.")
                pass
        finally:
            db.close()
    
    async def store_edited_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes and updates an edited message."""
        # Get data from update
        message = update.edited_message
        chat = update.effective_chat
        user = update.effective_user
        
        if not message or not chat or not user:
            # logger.debug("Skipping update without message/chat/user")
            return
            
        # Convert Telegram objects to dictionaries
        message_dict = message.to_dict()
        # Add chat and from inside message dictionary for update_message
        message_dict['chat'] = chat.to_dict()
        message_dict['from'] = user.to_dict()
        
        db = get_session()
        try:
            # Update message in database
            updated_msg = crud.update_message(db, message_dict)
            if updated_msg:
                # logger.debug(f"Message {updated_msg.internal_id} updated.")
                pass
        finally:
            db.close()

    async def reaction_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes reaction updates."""
        if update.message_reaction:
            db = get_session()
            try:
                crud.update_reactions(db, update.message_reaction.to_dict())
                # logger.debug("Reactions updated.")
            finally:
                db.close()

    async def track_chats_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Tracks bot addition/removal from chats."""
        if not update.my_chat_member: return
        
        result = update.my_chat_member
        chat = result.chat
        new_status = result.new_chat_member.status
        old_status = result.old_chat_member.status
        user_who_changed = result.from_user # User who changed bot's status
        
        db = get_session()
        try:
            # Ensure the user who changed status exists
            if user_who_changed:
                 crud.get_or_create_user(db, user_who_changed.to_dict())
                 
            if new_status in ["member", "administrator"] and old_status not in ["member", "administrator"]:
                logger.info(f"Bot added to chat: {chat.title} ({chat.id})")
                # Try to get member_count, but don't fail if unable
                member_count = None
                try:
                    member_count = await context.bot.get_chat_member_count(chat.id)
                except Exception as e:
                    logger.warning(f"Failed to get member_count for chat {chat.id}: {e}")
                chat_data = chat.to_dict()
                chat_data['member_count'] = member_count # Add member_count if received
                crud.get_or_create_chat(db, chat_data)
            elif new_status in ["left", "kicked"] and old_status not in ["left", "kicked"]:
                logger.info(f"Bot removed/blocked from chat: {chat.title} ({chat.id})")
                crud.deactivate_chat(db, chat.id)
            else:
                # Other status changes (e.g., promotion to admin) - update chat
                 logger.info(f"Bot status changed in chat: {chat.title} ({chat.id}) -> {new_status}")
                 crud.get_or_create_chat(db, chat.to_dict())
        finally:
            db.close()
            
    async def new_member_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes new members added to chat."""
        if update.message and update.message.new_chat_members:
            db = get_session()
            try:
                 chat_data = update.effective_chat.to_dict()
                 crud.get_or_create_chat(db, chat_data)
                 for member_data in update.message.new_chat_members:
                      crud.get_or_create_user(db, member_data.to_dict())
                      logger.info(f"User {member_data.username or member_data.id} added to chat {chat_data.get('id')}")
            finally: 
                db.close()
                
    async def left_member_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes member leaving/removal from chat."""
        if update.message and update.message.left_chat_member:
            db = get_session()
            try:
                 chat_data = update.effective_chat.to_dict()
                 crud.get_or_create_chat(db, chat_data)
                 member_data = update.message.left_chat_member
                 # Don't delete user, just log
                 logger.info(f"User {member_data.username or member_data.id} left/removed from chat {chat_data.get('id')}")
            finally: 
                 db.close()
                 
    def schedule_daily_summary(self):
        """Schedules daily summary generation."""
        if not self.job_queue:
            logger.warning("No JobQueue available, skipping summary scheduling")
            return

        self.job_queue.run_daily(
            callback=self.create_and_send_summary_job,
            time=SUMMARY_TIME,
            chat_id=self.channel_id,  # Will summarize for the channel_id if provided
            name="daily_summary"
        )
        logger.info(f"Daily summary scheduled at {SUMMARY_TIME}")

    async def create_and_send_summary_job(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int | None = None, days: int = 1):
        """Creates and sends summary for a chat - can be called as a job."""
        target_chat_id = chat_id or self.channel_id  # Use provided chat_id or default to channel_id
        if not target_chat_id:
            logger.error("No target chat ID provided for summary")
            return
            
        logger.info(f"Starting summary creation for chat {target_chat_id}, days={days}")
        
        # Get unsummarized messages
        db = get_session()
        try:
            # Get messages from the last N days that haven't been summarized
            # TODO: Implement a more efficient date-based query
            messages = crud.get_unsummarized_messages(db, target_chat_id, limit=1000)
            
            if not messages or len(messages) < MIN_MESSAGES:
                logger.info(f"Not enough messages to create summary for {target_chat_id}: {len(messages) if messages else 0}/{MIN_MESSAGES}")
                return
                
            # Cut to the last N days
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
            messages = [msg for msg in messages if msg.date_ts >= cutoff_date]
            
            # Filter for messages with meaningful content (text or caption)
            text_messages = [msg for msg in messages if msg.text or msg.caption]
            
            if not text_messages or len(text_messages) < MIN_MESSAGES:
                logger.info(f"Not enough text messages to create summary: {len(text_messages) if text_messages else 0}/{MIN_MESSAGES}")
                return
                
            # Create summary
            # summary_text = await self.summarizer.summarize_messages(text_messages)
            summary_text = f"Summary for chat {target_chat_id} coming soon!"
            
            # Save summary to DB
            # first_msg_id = messages[0].internal_id if messages else None
            # last_msg_id = messages[-1].internal_id if messages else None
            # summary = crud.create_summary(
            #     db, 
            #     chat_id=target_chat_id, 
            #     text=summary_text, 
            #     message_count=len(messages),
            #     first_message_internal_id=first_msg_id,
            #     last_message_internal_id=last_msg_id
            # )
            
            # Mark messages as summarized
            # if messages:
            #     crud.mark_messages_as_summarized(db, [msg.internal_id for msg in messages])
            
            # Send summary to the channel or specified chat
            await context.bot.send_message(
                chat_id=self.channel_id,  # Send to channel_id always
                text=summary_text,
                parse_mode=ParseMode.HTML
            )
            
            logger.info(f"Summary created and sent for {target_chat_id}")
        except Exception as e:
            logger.error(f"Error creating summary: {e}")
        finally:
            db.close()
    
    def run(self):
        """Starts the bot."""
        self.app.run_polling()
