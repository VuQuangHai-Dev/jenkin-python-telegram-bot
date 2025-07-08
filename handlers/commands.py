# handlers/commands.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import jenkins

import database
import security

logger = logging.getLogger(__name__)

# Định nghĩa các trạng thái
GET_URL, GET_USERID, GET_TOKEN = range(3)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gửi tin nhắn chào mừng tùy theo trạng thái đăng nhập."""
    user = update.effective_user
    logger.info(f"Received /start command from {user.first_name} (ID: {user.id})")
    if database.is_user_logged_in(user.id):
        welcome_message = (
            f"Hi {user.mention_html()}! You are already logged in.\n\n"
            "You can use these commands:\n"
            "  /setup - (In a group) Link a group to a Jenkins job\n"
            "  /build - (In a group) Start a new build\n"
            "  /logout - Disconnect your Jenkins account\n"
            "  /help - Show this message again"
        )
    else:
        welcome_message = (
            f"Hi {user.mention_html()}! Welcome to the Jenkins Bot.\n\n"
            "Please use /login to connect your Jenkins account."
        )
    await update.message.reply_html(welcome_message)

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gửi tin nhắn trợ giúp."""
    user = update.effective_user
    logger.info(f"Received /help command from {user.first_name} (ID: {user.id})")
    await start_handler(update, context)

async def logout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Đăng xuất người dùng."""
    user = update.effective_user
    logger.info(f"Received /logout command from {user.first_name} (ID: {user.id})")
    if update.message.chat.type != "private":
        await update.message.reply_text("Please use this command in a private chat with me.")
        return

    user_id = update.effective_user.id
    if database.is_user_logged_in(user_id):
        database.delete_user(user_id)
        await update.message.reply_text("You have been successfully logged out.")
    else:
        await update.message.reply_text("You are not logged in.")

# --- Login Conversation ---

async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bắt đầu cuộc hội thoại login."""
    user = update.effective_user
    logger.info(f"Received /login command from {user.first_name} (ID: {user.id})")
    user_id = update.effective_user.id
    if update.message.chat.type != "private":
        await update.message.reply_text("Please use this command in a private chat with me for security.")
        return ConversationHandler.END

    if database.is_user_logged_in(user_id):
        await update.message.reply_text("You are already logged in. Use /logout first to switch accounts.")
        return ConversationHandler.END

    await update.message.reply_text("What is your Jenkins server URL? (e.g., https://jenkins.example.com)")
    return GET_URL

async def get_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lưu URL và hỏi User ID."""
    context.user_data['jenkins_url'] = update.message.text.strip()
    await update.message.reply_text("What's your Jenkins User ID?")
    return GET_USERID

async def get_userid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lưu User ID và hỏi API Token."""
    context.user_data['jenkins_userid'] = update.message.text.strip()
    await update.message.reply_text("What's your Jenkins API Token?")
    return GET_TOKEN

async def get_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xác thực và lưu thông tin đăng nhập."""
    jenkins_url = context.user_data.get('jenkins_url')
    jenkins_userid = context.user_data.get('jenkins_userid')
    jenkins_token = update.message.text.strip()
    
    await update.message.reply_text("Verifying credentials...")
    try:
        server = jenkins.Jenkins(jenkins_url, username=jenkins_userid, password=jenkins_token, timeout=10)
        user_info = server.get_whoami()
        encrypted_token = security.encrypt_data(jenkins_token)
        database.save_user(update.effective_user.id, jenkins_url, jenkins_userid, encrypted_token)
        await update.message.reply_text(f"✅ Success! Connected as '{user_info.get('fullName', 'Unknown User')}'.")
    except Exception as e:
        await update.message.reply_text(f"❌ Authentication failed: {e}. Please use /login to try again.")
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Hủy cuộc hội thoại."""
    await update.message.reply_text("Process canceled.")
    context.user_data.clear()
    return ConversationHandler.END
