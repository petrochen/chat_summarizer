from telegram import Update
from telegram.ext import ContextTypes
from chat_database import ChatDatabase
from config import MIN_MESSAGES
from datetime import datetime, timedelta

class CommandHandlers:
    def __init__(self, db: ChatDatabase):
        self.db = db

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /start command"""
        await update.message.reply_text(
            "Hello! I'm a chat summary bot. "
            "Add me to a chat, and I'll create summaries every 24 hours."
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /help command"""
        help_text = (
            "I'm a chat summary bot.\n\n"
            "Commands:\n"
            "/start - Start working with the bot\n"
            "/help - Show this message\n"
            "/stats - Show chat statistics\n"
            "/summary - Create a summary manually\n"
            "/settings - Bot settings"
        )
        await update.message.reply_text(help_text)

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /stats command"""
        chat_id = update.effective_chat.id
        stats = self.db.get_chat_statistics(chat_id)
        
        if not stats:
            await update.message.reply_text("No data available to display statistics.")
            return

        stats_text = (
            f"Chat statistics for the last {stats['period_days']} days:\n\n"
            f"Total messages: {stats['total_messages']}\n"
            f"Active users: {stats['active_users']}\n"
            f"Media messages: {stats['media_messages']}\n"
            f"Questions: {stats['questions']}"
        )
        await update.message.reply_text(stats_text)

    async def summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /summary command"""
        chat_id = update.effective_chat.id
        messages = self.db.get_messages_for_last_day(chat_id)
        
        if not messages:
            await update.message.reply_text("No new messages to create a summary.")
            return

        if len(messages) < MIN_MESSAGES:
            await update.message.reply_text(
                f"Not enough messages to create a summary. "
                f"Minimum: {MIN_MESSAGES}, current count: {len(messages)}"
            )
            return

        # TODO: Add summary creation logic
        await update.message.reply_text("Creating summary...")

    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /settings command"""
        settings_text = (
            "Bot settings:\n\n"
            f"Minimum message count for summary: {MIN_MESSAGES}\n"
            "Summary creation interval: 24 hours"
        )
        await update.message.reply_text(settings_text) 